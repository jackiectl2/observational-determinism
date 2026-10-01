# Collect all replay summaries, accuracy, and headline numbers into one pilot_results.json.
import json
import os
import sys

from summarize_c3 import summarize, accuracy

R = os.environ["PROJECT_ROOT"] + "/runs/pilot_c3"
K8 = f"{R}/agent_qwen3_8b"
K16 = f"{R}/agent_qwen3_8b_k16"
REPLAYS = [
    ("k8", "sf1", f"{R}/replay/k8_sf1.jsonl", K8),
    ("k8", "sf10", f"{R}/replay/k8_sf10.jsonl", K8),
    ("k8", "sf100_5db", f"{R}/replay/k8_sf100_part.jsonl", K8),
    ("k8", "sf30_codebase", f"{R}/replay/k8_sf30_codebase.jsonl", K8),
    ("k8", "sf10_v2", f"{R}/replay/k8_sf10_v2.jsonl", K8),
    ("k8", "sf100_5db_v2", f"{R}/replay/k8_sf100_part_v2.jsonl", K8),
    ("k8", "sf30_codebase_v2", f"{R}/replay/k8_sf30_codebase_v2.jsonl", K8),
    ("k8", "sf10_threads1", f"{R}/replay/k8_sf10_t1.jsonl", K8),
    ("k8", "sf100_5db_threads1", f"{R}/replay/k8_sf100_part_t1.jsonl", K8),
    ("k8", "sf30_codebase_threads1", f"{R}/replay/k8_sf30_codebase_t1.jsonl", K8),
] + [(f"k16_sub{k}", "sf10", f"{R}/replay/k16_sub{k}_sf10.jsonl", K16) for k in (2, 4, 8, 16)]


def headline(s):
    c = s["costs"]
    return {
        "n_statements": s["n_statements"], "n_tasks": s["n_tasks"], "n_attempts": s["n_attempts"],
        "class_frac": {k: round(v, 4) for k, v in s["class_frac"].items()},
        "rows": {k: c["rows_scanned"][k] for k in ("a", "b_exact", "b", "c")},
        "bytes": {k: c["bytes"][k] for k in ("a", "b_exact", "b", "c")},
        "engine_s": {k: round(c["exec_s"][k], 4) for k in ("a", "b_exact", "b", "c")},
        "reads_removed_c_vs_b": round(c["rows_scanned"]["removed_c_vs_b"], 4),
        "bytes_removed_c_vs_b": round(c["bytes"]["removed_c_vs_b"], 4),
        "reads_removed_c_vs_exact_only": round(c["rows_scanned"]["removed_c_vs_b_exact"], 4),
        "engine_time_saved_c_vs_b": round(c["exec_s"]["removed_c_vs_b"], 4),
        "cpu_s": {k: round(c["cpu_s"][k], 4) for k in ("a", "b_exact", "b", "c")} if c["cpu_s"]["available"] else None,
        "cpu_speedup_b_over_c": round(c["cpu_s"]["speedup_b_over_c"], 4) if c["cpu_s"]["available"] and c["cpu_s"]["c"] else None,
        "engine_speedup_b_over_c": round(c["exec_s"]["speedup_b_over_c"], 4),
        "engine_speedup_a_over_c": round(c["exec_s"]["speedup_a_over_c"], 4),
        "engine_s_c_free_materialization": round(c["exec_s"]["c_free_materialization"], 4) if c["exec_s"]["has_mat_field"] else None,
        "engine_speedup_b_over_free_materialization": round(c["exec_s"]["speedup_b_over_free_mat"], 4) if c["exec_s"]["has_mat_field"] else None,
        "engine_s_c_oracle_zero_cost_reuse": round(c["exec_s"]["c_oracle_zero_cost_reuse"], 4),
        "engine_speedup_b_over_oracle": round(c["exec_s"]["speedup_b_over_oracle"], 4),
        "engine_top1pct_share_of_b": round(c["exec_s"]["top1pct_share_of_b"], 4),
        "engine_speedup_b_over_c_trimmed_top1pct": round(c["exec_s"]["speedup_b_over_c_trimmed_top1pct"], 4),
        "engine_per_task_geomean_b_over_c": round(c["exec_s"]["per_task_geomean_b_over_c"], 4),
        "tasks_with_beyond_exact_reuse": round(s["tasks_with_beyond_exact_reuse"], 4),
        "tasks_with_read_reduction_ge_25pct": round(s["tasks_with_read_reduction_ge_25pct"], 4),
        "beyond_exact_cross_attempt_frac": round(s["beyond_exact_cross_attempt_frac"], 4),
        "validation": s["validation"],
    }


FIVE = {"thrombosis_prediction", "formula_1", "debit_card_specializing", "california_schools", "card_games"}


def group_costs(path, dbs, pk, excl_timeouts=True):
    """Reads / bytes / engine time of (a), (b), (c=pk) restricted to a DB group (same statements at every scale)."""
    recs = [json.loads(l) for l in open(path)]
    recs = [r for r in recs if r["db_id"] in dbs and not (excl_timeouts and r["a"]["timeout"])]
    def tot(sel, key, pol):
        return sum(r[pol].get(key, 0.0) for r in recs if sel(r))
    out = {"n": len(recs), "timeouts_excluded": excl_timeouts}
    for key in ("rows_scanned", "bytes", "exec_s", "cpu_s"):
        a = tot(lambda r: True, key, "a")
        b = tot(lambda r: r["b"]["hit"] is None, key, "a")
        c = tot(lambda r: True, key, pk)
        out[key] = {"a": a, "b": b, "c": c, "removed_c_vs_b": 1 - c / b if b else None, "b_over_c": b / c if c else None}
    return out


def trace_summary(tdir):
    import collections
    tr = [json.loads(l) for l in open(f"{tdir}/trace.jsonl")]
    at = [json.loads(l) for l in open(f"{tdir}/attempts.jsonl")]
    stats = [json.loads(l) for l in open(f"{tdir}/turn_stats.jsonl")]
    return {
        "n_tasks": len({e["task_id"] for e in tr}), "n_attempts": len(at), "n_statements": len(tr),
        "n_success": sum(e["success"] for e in tr), "n_final_exec": sum(e["is_final"] for e in tr),
        "n_timeouts_sf1": sum(e["timeout"] for e in tr),
        "statements_per_db": dict(collections.Counter(e["db_id"] for e in tr)),
        "tasks_per_db": dict(collections.Counter(t.split(":")[0] for t in {e["task_id"] for e in tr})),
        "statements_per_turn": dict(sorted(collections.Counter(e["turn"] for e in tr).items())),
        "final_kinds": dict(collections.Counter(a["final_kind"] for a in at)),
        "sf1_statement_runtime_total_s": sum(e["runtime"] for e in tr),
        "llm_prompt_tokens": sum(x["prompt_tokens"] for x in stats), "llm_gen_tokens": sum(x["gen_tokens"] for x in stats),
        "llm_gen_seconds": sum(x["gen_s"] for x in stats),
    }


def main():
    out = {"accuracy": {"k8_run": accuracy(f"{K8}/attempts.jsonl")},
           "trace_summary": {"k8": trace_summary(K8), "k16": trace_summary(K16)},
           "replays": {}, "full_summaries": [], "scale_trend": {}}
    trend_files = {("five_dbs", "sf1"): f"{R}/replay/k8_sf1.jsonl", ("five_dbs", "sf10"): f"{R}/replay/k8_sf10.jsonl",
                   ("five_dbs", "sf100"): f"{R}/replay/k8_sf100_part.jsonl",
                   ("codebase", "sf1"): f"{R}/replay/k8_sf1.jsonl", ("codebase", "sf10"): f"{R}/replay/k8_sf10.jsonl",
                   ("codebase", "sf30"): f"{R}/replay/k8_sf30_codebase.jsonl"}
    for (grp, scale), path in trend_files.items():
        v2 = path.replace(".jsonl", "_v2.jsonl")
        path = v2 if os.path.exists(v2) else path
        if not os.path.exists(path):
            continue
        dbs = FIVE if grp == "five_dbs" else {"codebase_community"}
        for pk in ("c", "c_contain", "c_cost"):
            out["scale_trend"][f"{grp}|{scale}|{pk}"] = group_costs(path, dbs, pk)
    for k in (2, 4, 8, 16):
        out["accuracy"][f"k16_run_first{k}"] = accuracy(f"{K16}/attempts.jsonl", k)
    for trace_name, scale, path, tdir in REPLAYS:
        if not os.path.exists(path):
            print("missing", path, file=sys.stderr)
            continue
        for pk in ("c", "c_contain", "c_cost"):
            for ex in (False, True):
                s = summarize(path, f"{tdir}/trace.jsonl", pk, ex)
                key = f"{trace_name}|{scale}|{pk}|{'excl_timeouts' if ex else 'all'}"
                out["replays"][key] = headline(s)
                s["key"] = key
                out["full_summaries"].append(s)
    json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
    for key, h in out["replays"].items():
        print(f"{key:48s} reads-{h['reads_removed_c_vs_b']:.3f} bytes-{h['bytes_removed_c_vs_b']:.3f} "
              f"time b/c {h['engine_speedup_b_over_c']:.3f} trim {h['engine_speedup_b_over_c_trimmed_top1pct']:.3f} gm {h['engine_per_task_geomean_b_over_c']:.3f} "
              f"freemat {h['engine_speedup_b_over_free_materialization']} oracle {h['engine_speedup_b_over_oracle']:.3f} "
              f"eng a={h['engine_s']['a']:.2f} b={h['engine_s']['b']:.2f} c={h['engine_s']['c']:.2f} "
              f"tasks {h['tasks_with_beyond_exact_reuse']:.2f} valid {h['validation']['counts']}")
    for key, g in out["scale_trend"].items():
        print(f"{key:36s} n={g['n']} reads-{g['rows_scanned']['removed_c_vs_b']:.3f} bytes-{g['bytes']['removed_c_vs_b']:.3f} "
              f"time b={g['exec_s']['b']:.2f} c={g['exec_s']['c']:.2f} b/c={g['exec_s']['b_over_c']:.3f}")
    print(json.dumps(out["accuracy"], indent=1))


if __name__ == "__main__":
    main()
