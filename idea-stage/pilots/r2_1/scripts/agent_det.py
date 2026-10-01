# Greedy (temperature 0) ReAct text-to-SQL agent run under several "equivalent execution" conditions:
# the same tasks against the original or a physically permuted copy of each database, DuckDB with 1 or 8
# threads, and observations rendered either raw (first 20 rows as returned) or with OBSERVE k.
# All conversations of all conditions advance turn by turn in one batched vLLM generate call per turn.
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import db_path, schema_text, execute_with_timeout, canon_rows  # noqa: E402
from agent_c3 import SYSTEM, USER, parse_response, observation  # noqa: E402
import observe as ob  # noqa: E402

PERM_DIR = os.environ["PROJECT_ROOT"] + "/data/pilot_r2_1"
CONDITIONS = [  # name, variant, duckdb threads, observation mode
    ("raw_orig_t1", "orig", 1, "raw"),
    ("raw_perm_t1", "perm", 1, "raw"),
    ("obs_orig_t1", "orig", 1, "observe"),
    ("obs_perm_t1", "perm", 1, "observe"),
    ("raw_orig_t8", "orig", 8, "raw"),
    ("raw_orig_t8b", "orig", 8, "raw"),
    ("obs_orig_t8", "orig", 8, "observe"),
]


def run_statement(con, sql, mode, timeout):
    """Execute one statement under an observation mode; returns (result, executed_sql, observation text, meta).
    mode 'raw': first 20 rows as returned (the C3 tool); 'observe': canonical OBSERVE v2 (observe.observe_v2)."""
    if mode == "raw":
        r = execute_with_timeout(con, sql, timeout)
        return r, sql, observation(r, ob.K), {"path": "raw"}
    r, _, text, meta = ob.observe_v2(con, sql, lambda c, q: execute_with_timeout(c, q, timeout))
    return r, meta.get("exec_sql") or sql, text, meta


class Conv:
    def __init__(self, cond, task, system):
        self.cond = cond
        self.task = task
        self.messages = [{"role": "system", "content": system},
                         {"role": "user", "content": USER.format(question=task["question"],
                                                                 evidence=task["evidence"] or "(none)")}]
        self.done = False
        self.final_sql = None
        self.final_kind = None
        self.last_ok_sql = None
        self.n_turns = 0
        self.final_result = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--max-model-len", type=int, default=16384)
    ap.add_argument("--seed-perm", type=int, default=42)
    ap.add_argument("--limit-tasks", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sql-threads", type=int, default=8)
    ap.add_argument("--sql-timeout", type=float, default=20.0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tasks = json.load(open(args.tasks))
    if args.limit_tasks:
        tasks = tasks[: args.limit_tasks]
    dbs = sorted({t["db_id"] for t in tasks})
    cons = {}
    for _, variant, threads, _ in CONDITIONS:
        for d in dbs:
            key = (variant, threads, d)
            if key not in cons:
                path = db_path(d) if variant == "orig" else f"{PERM_DIR}/{d}_perm{args.seed_perm}.duckdb"
                cons[key] = ob.open_instance(path, threads)  # private instance: own thread setting
    # schema text from the original DB (identical schema in the permuted copy)
    schemas = {d: schema_text(cons[("orig", 1, d)]) for d in dbs}
    for key, con in cons.items():  # record the effective thread setting of every instance
        print("instance", key, con.execute("SELECT current_setting('threads')").fetchone()[0], flush=True)
    convs = []
    for cond in CONDITIONS:
        for t in tasks:
            system = SYSTEM.format(max_rows=ob.K, max_turns=args.max_turns, schema=schemas[t["db_id"]])
            convs.append(Conv(cond, t, system))

    llm = tok = None
    if not args.dry_run:
        from vllm import LLM
        llm = LLM(model=args.model, max_model_len=args.max_model_len, gpu_memory_utilization=0.90,
                  enable_prefix_caching=True, seed=0)
        tok = llm.get_tokenizer()
    trace_f = open(os.path.join(args.out, "trace.jsonl"), "w")
    stats_f = open(os.path.join(args.out, "turn_stats.jsonl"), "w")
    pool = cf.ThreadPoolExecutor(args.sql_threads)
    t_start = time.time()
    seq = [0]

    def run_batch(items):
        futs = [pool.submit(run_statement, cons[(c.cond[1], c.cond[2], c.task["db_id"])], sql,
                            "raw" if is_final else c.cond[3], args.sql_timeout)
                for c, sql, _, is_final in items]
        outs = [f.result() for f in futs]
        for (c, sql, turn, is_final), (r, exec_sql, text, meta) in zip(items, outs):
            rec = {"seq": seq[0], "cond": c.cond[0], "task_id": c.task["task_id"], "db_id": c.task["db_id"],
                   "turn": turn, "is_final": is_final, "sql": sql, "exec_sql": exec_sql, "success": r["success"],
                   "error": r["error"], "n_rows": r["n_rows"], "truncated": r["truncated"], "runtime": r["runtime"],
                   "obs_sha1": hashlib.sha1(text.encode()).hexdigest(), "obs": text, "meta": meta}
            seq[0] += 1
            trace_f.write(json.dumps(rec, default=str) + "\n")
        trace_f.flush()
        return outs

    for turn in range(1, args.max_turns + 1):
        active = [c for c in convs if not c.done]
        if not active:
            break
        t0 = time.time()
        if args.dry_run:
            texts = [f"```sql\n{c.task['gold_sql_duckdb']}\n```" if turn < 2 else
                     f"FINAL ANSWER\n```sql\n{c.task['gold_sql_duckdb']}\n```" for c in active]
            n_prompt_tok = n_gen_tok = 0
            n_unique = len(set(texts))
        else:
            from vllm import SamplingParams
            prompts, keep = [], []
            for c in active:
                p = tok.apply_chat_template(c.messages, tokenize=False, add_generation_prompt=True,
                                            enable_thinking=False)
                if len(tok(p).input_ids) > args.max_model_len - args.max_tokens - 16:
                    c.done = True
                    c.final_kind = "context_exhausted"
                    continue
                prompts.append(p)
                keep.append(c)
            active = keep
            sp = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
            # vLLM greedy decoding is not batch-invariant (run 1: identical turn-1 prompts gave different SQL in
            # 21/66 tasks across conditions), so identical prompts are generated once and share the output.
            uniq = {}
            for p in prompts:
                uniq.setdefault(p, len(uniq))
            order = sorted(uniq, key=uniq.get)
            outs = llm.generate(order, sp, use_tqdm=False) if order else []
            texts = [outs[uniq[p]].outputs[0].text for p in prompts]
            n_prompt_tok = sum(len(o.prompt_token_ids) for o in outs)
            n_gen_tok = sum(len(o.outputs[0].token_ids) for o in outs)
            n_unique = len(order)
        t_gen = time.time() - t0
        to_run = []
        for c, text in zip(active, texts):
            c.n_turns = turn
            kind, sql, kept = parse_response(text)
            if kind == "query" and turn == args.max_turns:
                kind = "final"
            c.messages.append({"role": "assistant", "content": kept})
            if kind == "final":
                c.final_sql, c.final_kind, c.done = sql, "final", True
                to_run.append((c, sql, turn, True))
            elif kind == "query":
                to_run.append((c, sql, turn, False))
            else:
                c.messages.append({"role": "user", "content":
                                   "Please reply with one SQL query in a ```sql code block, or with FINAL ANSWER and the final ```sql block."})
        t1 = time.time()
        outs = run_batch(to_run)
        t_sql = time.time() - t1
        for (c, sql, _, is_final), (r, _, text, _) in zip(to_run, outs):
            if r["success"]:
                c.last_ok_sql = sql
            if is_final:
                c.final_result = r
                continue
            obs = text
            if turn == args.max_turns - 1:
                obs += "\n\nThis was your last exploration turn. Now reply with FINAL ANSWER and the final ```sql block."
            c.messages.append({"role": "user", "content": obs})
        st = {"turn": turn, "active": len(active), "unique_prompts": n_unique, "n_sql": len(to_run), "gen_s": round(t_gen, 1),
              "sql_s": round(t_sql, 1), "prompt_tokens": n_prompt_tok, "gen_tokens": n_gen_tok,
              "elapsed_s": round(time.time() - t_start, 1)}
        print(json.dumps(st), flush=True)
        stats_f.write(json.dumps(st) + "\n")
        stats_f.flush()
    fallback = []
    for c in convs:
        if c.final_sql is None and c.last_ok_sql is not None:
            c.final_sql = c.last_ok_sql
            c.final_kind = (c.final_kind or "no_final") + "_fallback_last_ok"
            fallback.append((c, c.final_sql, c.n_turns + 1, True))
    for (c, _, _, _), (r, _, _, _) in zip(fallback, run_batch(fallback)):
        c.final_result = r
    with open(os.path.join(args.out, "attempts.jsonl"), "w") as f:
        for c in convs:
            r = c.final_result
            correct = False
            if r is not None and r["success"] and not r["truncated"]:
                correct = set(canon_rows(r["rows"])) == set(tuple(x) for x in canon_rows(c.task["gold_rows"]))
            f.write(json.dumps({"cond": c.cond[0], "task_id": c.task["task_id"], "db_id": c.task["db_id"],
                                "final_kind": c.final_kind, "final_sql": c.final_sql, "n_turns": c.n_turns,
                                "correct": bool(correct),
                                "final_rows": [list(x) for x in canon_rows(r["rows"])] if (r and r["success"] and r["n_rows"] <= 1000) else None,
                                "messages": c.messages}, default=str) + "\n")
    trace_f.close()
    stats_f.close()
    print("done in", round(time.time() - t_start, 1), "s", flush=True)


if __name__ == "__main__":
    main()
