# ReAct-style text-to-SQL agent with K parallel attempts per task (test-time scaling).
# All attempts of all tasks are advanced turn by turn; each turn is one batched vLLM generate call.
# Every executed SQL is logged to trace.jsonl with (task, attempt, turn, text, success, rows, runtime).
import argparse
import concurrent.futures as cf
import json
import os
import re
import time
import zlib

from common import db_path, open_db, schema_text, execute_with_timeout, canon_rows, bag_hash

SYSTEM = """You are an expert data analyst working with a DuckDB database. Answer the user's question by writing SQL.
You work in turns. In each turn, write a short thought and then exactly one SQL query in a ```sql code block; the query is executed and you see its result (at most {max_rows} rows are shown). Use these turns to inspect data values, check joins, and verify your answer.
When you are confident, write the line FINAL ANSWER followed by one ```sql code block containing the single query whose result answers the question. Return only the columns the question asks for.
You have at most {max_turns} turns.

SQL dialect: DuckDB. Quote identifiers that contain spaces or special characters with double quotes, e.g. "Free Meal Count (K-12)". Use single quotes for string literals.

Database schema:
{schema}"""

USER = "Question: {question}\nEvidence: {evidence}"

SQL_BLOCK = re.compile(r"```(?:sql|duckdb|SQL)?[ \t]*\n?(.*?)```", re.S)
FINAL_RE = re.compile(r"FINAL\s+ANSWER", re.I)


def parse_response(text):
    """Returns (kind, sql, kept_text). kind in {'final', 'query', 'none'}."""
    m_final = FINAL_RE.search(text)
    if m_final:
        m = SQL_BLOCK.search(text, m_final.end())
        if m is None:
            m = SQL_BLOCK.search(text)
        if m is not None and m.group(1).strip():
            return "final", m.group(1).strip(), text[: m.end()]
    m = SQL_BLOCK.search(text)
    if m is not None and m.group(1).strip():
        return "query", m.group(1).strip(), text[: m.end()]
    return "none", None, text


def fmt_cell(v, width=60):
    s = "NULL" if v is None else str(v)
    s = s.replace("\n", " ")
    return s if len(s) <= width else s[: width - 3] + "..."


def observation(res, max_rows, max_chars=3000):
    if not res["success"]:
        return f"Error: {res['error'][:400]}"
    cols = res["columns"]
    lines = [" | ".join(cols)]
    for r in res["rows"][:max_rows]:
        lines.append(" | ".join(fmt_cell(v) for v in r))
    body = "\n".join(lines)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...(output truncated)"
    n = f"more than {res['n_rows']}" if res["truncated"] else str(res["n_rows"])
    return f"Result ({n} rows; showing up to {max_rows}):\n{body}"


class Conv:
    def __init__(self, task, attempt, system):
        self.task = task
        self.attempt = attempt
        self.messages = [{"role": "system", "content": system},
                         {"role": "user", "content": USER.format(question=task["question"],
                                                                 evidence=task["evidence"] or "(none)")}]
        self.done = False
        self.final_sql = None
        self.final_kind = None
        self.last_ok_sql = None
        self.n_turns = 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--max-rows", type=int, default=20)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--max-model-len", type=int, default=16384)
    ap.add_argument("--limit-tasks", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="no LLM; answer with gold SQL (pipeline test)")
    ap.add_argument("--sql-threads", type=int, default=8)
    ap.add_argument("--sql-timeout", type=float, default=20.0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    tasks = json.load(open(args.tasks))
    if args.limit_tasks:
        tasks = tasks[: args.limit_tasks]
    dbs = sorted({t["db_id"] for t in tasks})
    cons = {d: open_db(db_path(d), threads=2) for d in dbs}
    schemas = {d: schema_text(cons[d]) for d in dbs}

    convs = []
    for t in tasks:
        system = SYSTEM.format(max_rows=args.max_rows, max_turns=args.max_turns, schema=schemas[t["db_id"]])
        for a in range(args.k):
            convs.append(Conv(t, a, system))

    llm = tok = None
    if not args.dry_run:
        from vllm import LLM, SamplingParams
        llm = LLM(model=args.model, max_model_len=args.max_model_len, gpu_memory_utilization=0.90,
                  enable_prefix_caching=True, seed=0)
        tok = llm.get_tokenizer()

    trace_f = open(os.path.join(args.out, "trace.jsonl"), "w")
    stats_f = open(os.path.join(args.out, "turn_stats.jsonl"), "w")
    pool = cf.ThreadPoolExecutor(args.sql_threads)
    seq = 0
    t_start = time.time()

    def run_batch(items):
        """items: list of (conv, sql, turn, is_final). Executes in parallel, logs, returns results."""
        nonlocal seq
        futs = [pool.submit(execute_with_timeout, cons[c.task["db_id"]], sql, args.sql_timeout) for c, sql, _, _ in items]
        results = [f.result() for f in futs]
        for (c, sql, turn, is_final), r in zip(items, results):
            rec = {"seq": seq, "task_id": c.task["task_id"], "db_id": c.task["db_id"], "attempt": c.attempt,
                   "turn": turn, "is_final": is_final, "sql": sql, "success": r["success"],
                   "error": r["error"], "timeout": r["timeout"], "n_rows": r["n_rows"],
                   "truncated": r["truncated"], "runtime": r["runtime"], "columns": r["columns"],
                   "result_hash": bag_hash(r["rows"]) if r["success"] else None}
            seq += 1
            trace_f.write(json.dumps(rec, default=str) + "\n")
        trace_f.flush()
        return results

    for turn in range(1, args.max_turns + 1):
        active = [c for c in convs if not c.done]
        if not active:
            break
        t0 = time.time()
        if args.dry_run:
            texts = [f"Thought: test.\n```sql\n{c.task['gold_sql_duckdb']}\n```" if turn < 2 else
                     f"FINAL ANSWER\n```sql\n{c.task['gold_sql_duckdb']}\n```" for c in active]
            n_prompt_tok = n_gen_tok = 0
        else:
            from vllm import SamplingParams
            prompts, keep = [], []
            for c in active:
                p = tok.apply_chat_template(c.messages, tokenize=False, add_generation_prompt=True,
                                            enable_thinking=False)
                if len(tok(p).input_ids) > args.max_model_len - args.max_tokens - 16:
                    c.done = True  # context exhausted; falls back to last successful SQL
                    c.final_kind = "context_exhausted"
                    continue
                prompts.append(p)
                keep.append(c)
            active = keep
            sps = [SamplingParams(temperature=args.temperature, top_p=args.top_p, max_tokens=args.max_tokens,
                                  seed=zlib.crc32(f"{c.task['task_id']}|{c.attempt}|{turn}".encode()) % (2 ** 31)) for c in active]
            outs = llm.generate(prompts, sps, use_tqdm=False)
            texts = [o.outputs[0].text for o in outs]
            n_prompt_tok = sum(len(o.prompt_token_ids) for o in outs)
            n_gen_tok = sum(len(o.outputs[0].token_ids) for o in outs)
        t_gen = time.time() - t0

        to_run = []
        for c, text in zip(active, texts):
            c.n_turns = turn
            kind, sql, kept = parse_response(text)
            if kind == "query" and turn == args.max_turns:
                kind = "final"  # last turn: treat the query as the final answer
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
        results = run_batch(to_run)
        t_sql = time.time() - t1
        for (c, sql, _, is_final), r in zip(to_run, results):
            if r["success"]:
                c.last_ok_sql = sql
            if is_final:
                c.final_result = r
                continue
            obs = observation(r, args.max_rows)
            if turn == args.max_turns - 1:
                obs += "\n\nThis was your last exploration turn. Now reply with FINAL ANSWER and the final ```sql block."
            c.messages.append({"role": "user", "content": obs})
        st = {"turn": turn, "active": len(active), "n_sql": len(to_run), "gen_s": round(t_gen, 1),
              "sql_s": round(t_sql, 1), "prompt_tokens": n_prompt_tok, "gen_tokens": n_gen_tok,
              "elapsed_s": round(time.time() - t_start, 1)}
        print(json.dumps(st), flush=True)
        stats_f.write(json.dumps(st) + "\n")
        stats_f.flush()

    # Attempts without an explicit final answer fall back to their last successful query (executed as the answer).
    fallback = []
    for c in convs:
        if c.final_sql is None and c.last_ok_sql is not None:
            c.final_sql = c.last_ok_sql
            c.final_kind = (c.final_kind or "no_final") + "_fallback_last_ok"
            fallback.append((c, c.final_sql, c.n_turns + 1, True))
    for (c, _, _, _), r in zip(fallback, run_batch(fallback)):
        c.final_result = r

    # Accuracy vs gold (set comparison of canonical rows, BIRD-style).
    with open(os.path.join(args.out, "attempts.jsonl"), "w") as f:
        for c in convs:
            r = getattr(c, "final_result", None)
            correct = None
            if r is not None and r["success"] and not r["truncated"]:
                correct = set(canon_rows(r["rows"])) == set(tuple(x) for x in canon_rows(c.task["gold_rows"]))
            elif r is not None:
                correct = False
            f.write(json.dumps({"task_id": c.task["task_id"], "db_id": c.task["db_id"], "attempt": c.attempt,
                                "final_kind": c.final_kind, "final_sql": c.final_sql, "n_turns": c.n_turns,
                                "correct": bool(correct) if correct is not None else False,
                                "final_result_hash": bag_hash(r["rows"]) if (r and r["success"]) else None,
                                "messages": c.messages}, default=str) + "\n")
    trace_f.close()
    stats_f.close()
    print("done in", round(time.time() - t_start, 1), "s", flush=True)


if __name__ == "__main__":
    main()
