# Analysis of step 3: greedy trajectories under equivalent executions, raw vs OBSERVE observations.
import argparse
import collections
import json

PAIRS = {
    "raw: original vs permuted order (1 thread)": ("raw_orig_t1", "raw_perm_t1"),
    "raw: 1 vs 8 threads (original order)": ("raw_orig_t1", "raw_orig_t8"),
    "raw: 8 threads, repeated": ("raw_orig_t8", "raw_orig_t8b"),
    "OBSERVE: original vs permuted order (1 thread)": ("obs_orig_t1", "obs_perm_t1"),
    "OBSERVE: 1 vs 8 threads (original order)": ("obs_orig_t1", "obs_orig_t8"),
}


def compare(ta, tb, aa, ab):
    """ta/tb: statement records of one task under two conditions (sorted); aa/ab: attempt records."""
    sa = [(r["sql"], r["is_final"]) for r in ta]
    sb = [(r["sql"], r["is_final"]) for r in tb]
    first_sql = next((i for i in range(min(len(sa), len(sb))) if sa[i] != sb[i]), None)
    if first_sql is None and len(sa) != len(sb):
        first_sql = min(len(sa), len(sb))
    first_obs = next((i for i in range(min(len(ta), len(tb)))
                      if sa[i] == sb[i] and not ta[i]["is_final"] and ta[i]["obs_sha1"] != tb[i]["obs_sha1"]), None)
    changed = first_sql is not None
    attributable = changed and first_obs is not None and first_obs < first_sql
    fa, fb = aa.get("final_rows"), ab.get("final_rows")
    res_changed = (fa is None) != (fb is None) or (fa is not None and set(map(tuple, fa)) != set(map(tuple, fb)))
    final_sql_changed = aa.get("final_sql") != ab.get("final_sql")
    return {"traj_changed": changed, "obs_diverged_before_change": first_obs is not None and (first_sql is None or first_obs < first_sql),
            "next_action_changed": attributable and first_sql == first_obs + 1,
            "final_sql_or_answer_changed": final_sql_changed or res_changed,
            "obs_diverged_any": first_obs is not None, "attributable": attributable,
            "unexplained_change": changed and not attributable,
            "final_sql_changed": aa.get("final_sql") != ab.get("final_sql"),
            "final_result_changed": res_changed, "correctness_changed": aa["correct"] != ab["correct"],
            "first_sql_div": first_sql, "first_obs_div": first_obs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--div-summary", default="", help="analyze_div output (for the affected-task subset)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-affected", type=int, default=30)
    args = ap.parse_args()
    tr = [json.loads(l) for l in open(f"{args.run}/trace.jsonl")]
    at = [json.loads(l) for l in open(f"{args.run}/attempts.jsonl")]
    by = collections.defaultdict(list)
    for r in tr:
        by[(r["cond"], r["task_id"])].append(r)
    for k in by:
        by[k].sort(key=lambda r: (r["turn"], r["is_final"], r["seq"]))
    att = {(a["cond"], a["task_id"]): a for a in at}
    tasks = sorted({a["task_id"] for a in at})
    conds = sorted({a["cond"] for a in at})
    per_task = json.load(open(args.div_summary))["tasks"]["per_task_divergent_distinct_statements_permuted"] if args.div_summary else {}
    # affected = the tasks whose C3-trace probes diverged most under the physical-order permutation (step 1)
    affected = [t for t, _ in sorted(per_task.items(), key=lambda x: (-x[1], x[0]))][: args.n_affected]
    out = {"n_tasks": len(tasks), "affected_tasks": affected, "accuracy": {}, "pairs": {}, "examples": []}
    for c in conds:
        out["accuracy"][c] = {"all": sum(att[(c, t)]["correct"] for t in tasks) / len(tasks),
                              "affected": sum(att[(c, t)]["correct"] for t in affected) / max(1, len(affected)),
                              "mean_statements": sum(len(by[(c, t)]) for t in tasks) / len(tasks)}
    for pname, (a, b) in PAIRS.items():
        if a not in conds or b not in conds:
            continue
        res = {t: compare(by[(a, t)], by[(b, t)], att[(a, t)], att[(b, t)]) for t in tasks}
        p = {}
        for subset, ts in (("all", tasks), ("affected", affected)):
            n = len(ts)
            if n == 0:
                continue
            p[subset] = {"n": n}
            for key in ("traj_changed", "obs_diverged_any", "obs_diverged_before_change", "attributable",
                        "unexplained_change", "next_action_changed", "final_sql_changed", "final_result_changed",
                        "final_sql_or_answer_changed", "correctness_changed"):
                p[subset][key] = sum(res[t][key] for t in ts) / n
            p[subset]["correct_a"] = sum(att[(a, t)]["correct"] for t in ts) / n
            p[subset]["correct_b"] = sum(att[(b, t)]["correct"] for t in ts) / n
        p["changed_tasks"] = [t for t in tasks if res[t]["traj_changed"]]
        out["pairs"][pname] = p
        # examples: first attributable trajectory change with the two differing observations
        for t in tasks:
            if res[t]["attributable"] and len(out["examples"]) < 4 and pname.startswith("raw: original"):
                i, j = res[t]["first_obs_div"], res[t]["first_sql_div"]
                ra, rb = by[(a, t)], by[(b, t)]
                out["examples"].append({"pair": pname, "task_id": t, "probe": ra[i]["sql"][:300],
                                        "obs_a": ra[i]["obs"][:700], "obs_b": rb[i]["obs"][:700],
                                        "next_sql_a": ra[j]["sql"][:300] if j < len(ra) else None,
                                        "next_sql_b": rb[j]["sql"][:300] if j < len(rb) else None,
                                        "final_a": att[(a, t)]["final_sql"], "final_b": att[(b, t)]["final_sql"],
                                        "correct_a": att[(a, t)]["correct"], "correct_b": att[(b, t)]["correct"]})
    json.dump(out, open(args.out, "w"), indent=1, default=str)
    print("accuracy:", {c: {k: round(v, 3) for k, v in x.items()} for c, x in out["accuracy"].items()})
    for pname, p in out["pairs"].items():
        for subset in ("all", "affected"):
            if subset not in p:
                continue
            x = p[subset]
            print(f"{pname:48s} {subset:8s} n={x['n']:2d} traj {x['traj_changed']:.3f} obsdiv {x['obs_diverged_any']:.3f} "
                  f"attrib {x['attributable']:.3f} next {x['next_action_changed']:.3f} unexpl {x['unexplained_change']:.3f} "
                  f"finalSQL {x['final_sql_changed']:.3f} finalRes {x['final_result_changed']:.3f} finalAny {x['final_sql_or_answer_changed']:.3f} "
                  f"corrChg {x['correctness_changed']:.3f} acc {x['correct_a']:.3f}/{x['correct_b']:.3f}")


if __name__ == "__main__":
    main()
