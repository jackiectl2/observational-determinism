# Summarize replay ledgers against the predeclared C3 criteria.
import argparse
import collections
import json
import re

BEYOND = ("containment", "unit_materialize", "unit_reuse", "scan_subst")
NONDET = re.compile(r"\blimit\b|row_number|array_agg|string_agg|group_concat|\blist\(|\bany_value\b|\barbitrary\b|\bfirst\(", re.I)


def mech_class(m):
    if m in ("exact", "normalized"):
        return m
    if m.startswith("containment"):
        return "containment"
    if m in ("unit_materialize", "unit_reuse", "scan_subst"):
        return "shared_subexpr"
    return "miss"


def summarize(path, trace_path=None, pk="c", exclude_timeouts=False):
    recs = [json.loads(l) for l in open(path)]
    if exclude_timeouts:
        recs = [r for r in recs if not r["a"]["timeout"]]
    sql = {}
    if trace_path:
        for l in open(trace_path):
            e = json.loads(l)
            sql[e["seq"]] = e["sql"]
    n = len(recs)
    tasks = sorted({r["task_id"] for r in recs})
    out = {"file": path, "policy": pk, "exclude_timeouts": exclude_timeouts, "n_statements": n, "n_tasks": len(tasks),
           "n_attempts": len({(r["task_id"], r["attempt"]) for r in recs}),
           "n_success": sum(r["trace_success"] for r in recs), "scale": recs[0]["scale"] if recs else None}
    cls = collections.Counter(mech_class(r[pk]["mech"]) for r in recs)
    out["class_counts"] = dict(cls)
    out["class_frac"] = {k: v / n for k, v in cls.items()}
    succ = [r for r in recs if r["trace_success"]]
    cls_s = collections.Counter(mech_class(r[pk]["mech"]) for r in succ)
    out["class_frac_success_only"] = {k: v / len(succ) for k, v in cls_s.items()}
    out["mech_counts"] = dict(collections.Counter(r[pk]["mech"] for r in recs))
    nf = [r for r in recs if not r["is_final"]]
    out["class_frac_excluding_final_exec"] = {k: v / len(nf) for k, v in collections.Counter(mech_class(r[pk]["mech"]) for r in nf).items()}
    # analysis-only shared sub-expressions among statements not already exact/normalized/containment
    rest = [r for r in recs if mech_class(r[pk]["mech"]) in ("shared_subexpr", "miss") and r["trace_success"]]
    out["sse_among_rest"] = {"n_rest": len(rest)}
    for k in ("join_bare", "join_bare_x", "join_filt", "join_filt_x", "scan", "scan_x"):
        out["sse_among_rest"][k] = sum(r["sse"][k] for r in rest) / max(1, len(rest))
    out["sse_any_among_all"] = sum((r["sse"]["join_bare"] or r["sse"]["scan"]) and mech_class(r[pk]["mech"]) in ("shared_subexpr", "miss")
                                   and r["trace_success"] for r in recs) / n
    # costs
    def tot(sel, key, pol):
        return sum(r[pol].get(key, 0.0) for r in recs if sel(r))
    costs = {}
    for key in ("rows_scanned", "bytes", "exec_s", "fetch_s", "cpu_s"):
        a = tot(lambda r: True, key, "a")
        b_exact = tot(lambda r: r[pk]["mech"] != "exact", key, "a")  # exact-text cache only (Halo-style)
        b = tot(lambda r: r["b"]["hit"] is None, key, "a")
        c = tot(lambda r: True, key, pk)
        costs[key] = {"a": a, "b_exact": b_exact, "b": b, "c": c}
    for key in ("rows_scanned", "bytes", "exec_s", "cpu_s"):
        x = costs[key]
        x["removed_c_vs_b"] = 1 - x["c"] / x["b"] if x["b"] else None
        x["removed_c_vs_b_exact"] = 1 - x["c"] / x["b_exact"] if x["b_exact"] else None
        x["removed_b_vs_a"] = 1 - x["b"] / x["a"] if x["a"] else None
        x["available"] = bool(x["a"])
        x["speedup_b_over_c"] = x["b"] / x["c"] if x["c"] else None
        x["speedup_a_over_c"] = x["a"] / x["c"] if x["c"] else None
    # bounds: engine time if materializations were free (by-product of execution), and if every
    # beyond-exact reusable statement were free (oracle)
    free_mat = sum(r[pk]["exec_s"] - r[pk].get("mat_exec_s", 0.0)
                   - r[pk].get("wasted_materialization", {}).get("exec_s", 0.0) for r in recs)
    oracle = sum(r["a"]["exec_s"] for r in recs if mech_class(r[pk]["mech"]) == "miss")
    costs["exec_s"]["c_free_materialization"] = free_mat
    costs["exec_s"]["c_oracle_zero_cost_reuse"] = oracle
    costs["exec_s"]["speedup_b_over_free_mat"] = costs["exec_s"]["b"] / free_mat if free_mat else None
    costs["exec_s"]["speedup_b_over_oracle"] = costs["exec_s"]["b"] / oracle if oracle else None
    costs["exec_s"]["has_mat_field"] = any("mat_exec_s" in r[pk] for r in recs)
    e2e = {pol: costs["exec_s"][pol] + costs["fetch_s"][pol] for pol in ("a", "b_exact", "b", "c")}
    e2e["speedup_b_over_c"] = e2e["b"] / e2e["c"] if e2e["c"] else None
    costs["exec_plus_fetch_s"] = e2e
    # heavy tail: share of (b) engine time in the top 1% statements by (a) time; speedup without them;
    # per-task geometric mean of t_b / t_c
    bstm = sorted((r for r in recs if r["b"]["hit"] is None), key=lambda r: -r["a"]["exec_s"])
    ntop = max(1, len(bstm) // 100)
    top = {r["seq"] for r in bstm[:ntop]}
    tb_all = sum(r["a"]["exec_s"] for r in bstm)
    costs["exec_s"]["top1pct_share_of_b"] = sum(r["a"]["exec_s"] for r in bstm[:ntop]) / tb_all if tb_all else None
    tb_trim = sum(r["a"]["exec_s"] for r in bstm if r["seq"] not in top)
    tc_trim = sum(r[pk]["exec_s"] for r in recs if r["seq"] not in top)
    costs["exec_s"]["b_trimmed_top1pct"] = tb_trim
    costs["exec_s"]["c_trimmed_top1pct"] = tc_trim
    costs["exec_s"]["speedup_b_over_c_trimmed_top1pct"] = tb_trim / tc_trim if tc_trim else None
    import math
    pt = collections.defaultdict(lambda: [0.0, 0.0])
    for r in recs:
        if r["b"]["hit"] is None:
            pt[r["task_id"]][0] += r["a"]["exec_s"]
        pt[r["task_id"]][1] += r[pk]["exec_s"]
    ratios = [b_ / c_ for b_, c_ in pt.values() if b_ > 0 and c_ > 0]
    costs["exec_s"]["per_task_geomean_b_over_c"] = math.exp(sum(math.log(x) for x in ratios) / len(ratios)) if ratios else None
    out["costs"] = costs
    # per-mechanism net savings relative to charging the statement its (a) cost
    mech_sav = collections.defaultdict(lambda: {"n": 0, "rows_a": 0, "rows_c": 0, "time_a": 0.0, "time_c": 0.0})
    for r in recs:
        m = mech_class(r[pk]["mech"]) if not r[pk]["mech"].startswith("containment") else r[pk]["mech"]
        d = mech_sav[m]
        d["n"] += 1
        d["rows_a"] += r["a"]["rows_scanned"]
        d["rows_c"] += r[pk]["rows_scanned"]
        d["time_a"] += r["a"]["exec_s"]
        d["time_c"] += r[pk]["exec_s"]
    out["per_mechanism"] = dict(mech_sav)
    # wasted materializations (charged to statements that still missed)
    out["wasted_materializations"] = sum(1 for r in recs if "wasted_materialization" in r[pk])
    out["wasted_materialization_time_s"] = sum(r[pk]["wasted_materialization"]["exec_s"] for r in recs if "wasted_materialization" in r[pk])
    # task coverage
    per_task = collections.defaultdict(lambda: {"beyond": 0, "rows_b": 0, "rows_c": 0, "t_b": 0.0, "t_c": 0.0})
    for r in recs:
        d = per_task[r["task_id"]]
        d["beyond"] += mech_class(r[pk]["mech"]) in ("containment", "shared_subexpr")
        if r["b"]["hit"] is None:
            d["rows_b"] += r["a"]["rows_scanned"]
            d["t_b"] += r["a"]["exec_s"]
        d["rows_c"] += r[pk]["rows_scanned"]
        d["t_c"] += r[pk]["exec_s"]
    out["tasks_with_beyond_exact_reuse"] = sum(d["beyond"] > 0 for d in per_task.values()) / len(per_task)
    out["tasks_with_read_reduction"] = sum(d["rows_c"] < d["rows_b"] for d in per_task.values()) / len(per_task)
    out["tasks_with_read_reduction_ge_25pct"] = sum(d["rows_b"] > 0 and d["rows_c"] <= 0.75 * d["rows_b"] for d in per_task.values()) / len(per_task)
    out["tasks_with_time_increase"] = sum(d["t_c"] > d["t_b"] for d in per_task.values()) / len(per_task)
    # cross-attempt share of beyond-exact reuse
    bey = [r for r in recs if mech_class(r[pk]["mech"]) in ("containment", "shared_subexpr")]
    out["beyond_exact_cross_attempt_frac"] = sum(bool(r[pk]["cross_attempt"]) for r in bey) / max(1, len(bey))
    # validation of reuse-served results against (a)
    served = [r for r in recs if mech_class(r[pk]["mech"]) in ("containment", "shared_subexpr")]
    val = collections.Counter(str(r[pk]["valid"]) for r in served)
    bad = [r for r in served if r[pk]["valid"] is False]
    bad_nondet = [r for r in bad if sql and NONDET.search(sql.get(r["seq"], "") + " " + (r[pk].get("comp_sql") or ""))]
    out["validation"] = {"served": len(served), "counts": dict(val), "mismatch_nondeterministic_construct": len(bad_nondet),
                         "mismatch_other_seqs": [r["seq"] for r in bad if r not in bad_nondet]}
    # per DB
    per_db = {}
    for db in sorted({r["db_id"] for r in recs}):
        rr = [r for r in recs if r["db_id"] == db]
        rb = sum(r["a"]["rows_scanned"] for r in rr if r["b"]["hit"] is None)
        rc = sum(r[pk]["rows_scanned"] for r in rr)
        tb = sum(r["a"]["exec_s"] for r in rr if r["b"]["hit"] is None)
        tc = sum(r[pk]["exec_s"] for r in rr)
        ta = sum(r["a"]["exec_s"] for r in rr)
        per_db[db] = {"n": len(rr), "tasks": len({r["task_id"] for r in rr}),
                      "classes": dict(collections.Counter(mech_class(r[pk]["mech"]) for r in rr)),
                      "rows_b": rb, "rows_c": rc, "rows_removed": (1 - rc / rb) if rb else None,
                      "time_a": ta, "time_b": tb, "time_c": tc, "speedup_b_over_c": tb / tc if tc else None}
    out["per_db"] = per_db
    return out


def accuracy(attempts_path, max_attempts=0):
    at = [json.loads(l) for l in open(attempts_path)]
    if max_attempts:
        at = [a for a in at if a["attempt"] < max_attempts]
    bytask = collections.defaultdict(list)
    for a in at:
        bytask[a["task_id"]].append(a)
    maj = 0
    for v in bytask.values():
        cnt = collections.Counter(x["final_result_hash"] for x in v if x["final_result_hash"])
        if cnt:
            h = cnt.most_common(1)[0][0]
            maj += any(x["correct"] for x in v if x["final_result_hash"] == h)
    return {"n_tasks": len(bytask), "n_attempts": len(at), "attempt_acc": sum(a["correct"] for a in at) / len(at),
            "majority_acc": maj / len(bytask), "pass_at_k": sum(any(x["correct"] for x in v) for v in bytask.values()) / len(bytask)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", nargs="+", required=True)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--attempts", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    res = {"replays": []}
    for p in args.replays:
        pols = [k for k in ("c", "c_contain", "c_cost") if k in json.loads(open(p).readline())]
        for pk in pols:
            for ex in (False, True):
                res["replays"].append(summarize(p, args.trace, pk, ex))
    if args.attempts:
        res["accuracy"] = accuracy(args.attempts)
    json.dump(res, open(args.out, "w"), indent=1, default=str)
    for s in res["replays"]:
        c = s["costs"]
        print(f"== {s['file'].split('/')[-1]} policy={s['policy']} excl_timeouts={s['exclude_timeouts']} scale={s['scale']} stmts={s['n_statements']} tasks={s['n_tasks']} attempts={s['n_attempts']}")
        print("  classes:", {k: round(v, 3) for k, v in s["class_frac"].items()})
        for key in ("rows_scanned", "bytes", "exec_s", "cpu_s"):
            x = c[key]
            if not x["available"]:
                continue
            print(f"  {key}: a={x['a']:.4g} b_exact={x['b_exact']:.4g} b={x['b']:.4g} c={x['c']:.4g} "
                  f"removed(c vs b)={x['removed_c_vs_b']:.3f} speedup b/c={x['speedup_b_over_c']:.3f} a/c={x['speedup_a_over_c']:.3f}")
        x = c["exec_s"]
        print(f"  time tail: top1% share of b={x['top1pct_share_of_b']:.3f} trimmed b/c={x['speedup_b_over_c_trimmed_top1pct']:.3f} "
              f"per-task geomean b/c={x['per_task_geomean_b_over_c']:.3f}")
        print("  tasks with beyond-exact reuse:", round(s["tasks_with_beyond_exact_reuse"], 3),
              "tasks with read reduction >=25%:", round(s["tasks_with_read_reduction_ge_25pct"], 3))
        print("  validation:", s["validation"])
    if "accuracy" in res:
        print("accuracy:", res["accuracy"])


if __name__ == "__main__":
    main()
