"""E4 analysis: per-policy stability across equivalent physical executions, attribution, and paired accuracy.

Stability groups (same model, same prompts, same tasks): for each policy, the three 1-thread instances
(original, permuted seed 42, permuted seed 7), and the thread pair (original, 1 vs 8 threads).
A task changes if the compared runs differ. Divergence is attributable when, for every pair of runs whose
SQL sequences differ, an earlier tool observation already differed (identical prompts share one generation).
Confidence intervals: task-clustered percentile bootstrap (2,000 resamples, seed 0).

Usage: python analyze3.py <out_dir> <tasks.json>
"""
import itertools
import json
import random
import sys
from collections import defaultdict

GROUPS = {
    "raw_phys": ["raw_orig_t1", "raw_p42_t1", "raw_p7_t1"],
    "slx_phys": ["slx_orig_t1", "slx_p42_t1", "slx_p7_t1"],
    "cer_phys": ["cer_orig_t1", "cer_p42_t1", "cer_p7_t1"],
    "str_phys": ["str_orig_t1", "str_p42_t1", "str_p7_t1"],
    "raw_threads": ["raw_orig_t1", "raw_orig_t8"],
    "cer_threads": ["cer_orig_t1", "cer_orig_t8"],
    "str_threads": ["str_orig_t1", "str_orig_t8"],
}
PAIRS = [("cer", "raw"), ("slx", "raw"), ("cer", "slx"), ("str", "raw"), ("str", "cer")]
VARIANTS = ["orig_t1", "p42_t1", "p7_t1"]


def load(out_dir):
    att = {}
    for line in open(f"{out_dir}/attempts.jsonl"):
        a = json.loads(line)
        att[(a["cond"], a["task_id"])] = a
    steps = defaultdict(list)
    for line in open(f"{out_dir}/trace.jsonl"):
        r = json.loads(line)
        # statement kind: the certified verdict or the policy path; failed executions are runtime errors, whose
        # messages may quote the first offending value (outside the contract, which covers successful executions)
        src = ("refused" if r["meta"].get("refused") else "runtime-error" if not r["success"]
               else "count-failure" if r["truncated"] else r["meta"].get("verdict") or r["meta"].get("path"))
        steps[(r["cond"], r["task_id"])].append((r["turn"], r["is_final"], r["sql"], r["obs_sha1"], src))
    for k in steps:
        steps[k].sort()
    return att, steps


def final_value(a):
    """Comparable final outcome, or None when it was not materialized (>1,000 rows): such comparisons are censored."""
    st = a.get("final_status")
    if st == "ok":
        return json.dumps(sorted(json.dumps(r, default=str) for r in a["final_rows"]))
    return {"error": "ERROR", None: "NO_ANSWER"}.get(st)


def task_flags(conds, t, att, steps):
    runs = [steps[(c, t)] for c in conds]
    sqls = [tuple(s[2] for s in r) for r in runs]
    fv = [final_value(att[(c, t)]) for c in conds]
    f = {"traj_changed": len(set(sqls)) > 1,
         "final_sql_changed": len({att[(c, t)]["final_sql"] for c in conds}) > 1,
         "final_result_changed": None if any(v is None for v in fv) else len(set(fv)) > 1,
         "correctness_changed": len({att[(c, t)]["correct"] for c in conds}) > 1}
    obs_same_sql, unattributed, sources = False, False, set()
    for i, j in itertools.combinations(range(len(conds)), 2):
        a, b = runs[i], runs[j]
        n = min(len(a), len(b))
        for x in range(n):
            if a[x][2] == b[x][2] and a[x][3] != b[x][3]:
                obs_same_sql = True
                # which kind of statement showed different observations ("runtime-error" if either run failed)
                bad = [k for k in ("runtime-error", "count-failure") if k in (a[x][4], b[x][4])]
                sources.add(bad[0] if bad else a[x][4])
        if sqls[i] != sqls[j]:
            k = next((x for x in range(n) if a[x][2] != b[x][2]), n)
            if not any(a[x][3] != b[x][3] for x in range(k)):
                unattributed = True
    f["obs_diverged_same_sql"] = obs_same_sql
    f["unattributed_divergence"] = unattributed
    f["attributable_traj_changed"] = f["traj_changed"] and not unattributed
    return f, sources


def boot(values, reps=2000, seed=0):
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return [round(means[int(0.025 * reps)], 3), round(means[int(0.975 * reps) - 1], 3)]


def bag_correct(a, gold):
    """Duplicate-sensitive variant of execution accuracy (the main metric compares sets, like BIRD's evaluator)."""
    if a.get("final_status") != "ok":
        return False
    key = lambda rows: sorted(json.dumps(list(r), default=str) for r in rows)  # noqa: E731
    return key(a["final_rows"]) == key(gold)


def summarize(tasks, att, steps, gold):
    res = {"n_tasks": len(tasks), "accuracy": {}, "bag_accuracy": {}, "stability": {}, "paired_accuracy": {}}
    conds = sorted({c for (c, _) in att})
    for c in conds:
        v = [float(att[(c, t)]["correct"]) for t in tasks]
        res["accuracy"][c] = {"mean": round(sum(v) / len(v), 3), "ci95": boot(v)}
        res["bag_accuracy"][c] = round(sum(bag_correct(att[(c, t)], gold[t]) for t in tasks) / len(tasks), 3)
    for g, cs in GROUPS.items():
        if not all((c, tasks[0]) in att for c in cs):
            continue
        both = [task_flags(cs, t, att, steps) for t in tasks]
        per = [b[0] for b in both]
        src = defaultdict(int)
        for f, ss in both:
            for x in ss:
                src[x] += 1
        res.setdefault("divergent_statement_sources", {})[g] = dict(src)  # tasks with a same-SQL observation change, by statement kind
        res["stability"][g] = {}
        for k in per[0]:
            v = [float(p[k]) for p in per if p[k] is not None]
            res["stability"][g][k] = {"count": int(sum(v)), "n": len(v), "censored": len(per) - len(v),
                                      "rate": round(sum(v) / len(v), 3) if v else None, "ci95": boot(v) if v else None}
            if v and not sum(v):  # exact one-sided 95% upper bound for a zero count (Clopper-Pearson)
                res["stability"][g][k]["upper95_if_zero"] = round(1 - 0.05 ** (1 / len(v)), 4)
    for x, y in PAIRS:
        if not all((f"{p}_{v}", tasks[0]) in att for p in (x, y) for v in VARIANTS):
            continue
        d = [sum(att[(f"{x}_{v}", t)]["correct"] - att[(f"{y}_{v}", t)]["correct"] for v in VARIANTS) / len(VARIANTS)
             for t in tasks]
        res["paired_accuracy"][f"{x}-{y}"] = {"mean_diff": round(sum(d) / len(d), 4), "ci95": boot(d)}
    return res


def main(out_dir, tasks_path):
    att, steps = load(out_dir)
    tl = json.load(open(tasks_path))
    split = {t["task_id"]: t.get("split", "pilot") for t in tl}
    gold = {t["task_id"]: t["gold_rows"] for t in tl}
    tasks = sorted({t for (_, t) in att})
    res = {"all": summarize(tasks, att, steps, gold)}
    for s in sorted(set(split[t] for t in tasks)):
        res[s] = summarize([t for t in tasks if split[t] == s], att, steps, gold)
    # verdicts of the statements executed under the certified (hybrid) and strict policies
    vc = defaultdict(lambda: defaultdict(int))
    for line in open(f"{out_dir}/trace.jsonl"):
        r = json.loads(line)
        if r["cond"][:4] in ("cer_", "str_"):
            v = r["meta"].get("verdict", r["meta"].get("path", "?"))
            vc[r["cond"][:3]][v + ("/refused" if r["meta"].get("refused") else "")] += 1
    res["certified_statement_verdicts"] = {k: dict(v) for k, v in vc.items()}
    json.dump(res, open(f"{out_dir}/summary_e4.json", "w"), indent=1)
    a = res["all"]
    print("tasks", a["n_tasks"])
    for g, m in a["stability"].items():
        print(f"{g:12s} " + "  ".join(f"{k}={v['count']}/{v['n']}" + (f"(cens {v['censored']})" if v['censored'] else "")
                                      for k, v in m.items()))
    for c, m in a["accuracy"].items():
        print(f"acc {c:12s} {m['mean']:.3f} {m['ci95']}  bag {a['bag_accuracy'][c]:.3f}")
    for k, m in a["paired_accuracy"].items():
        print(f"paired {k}: {m['mean_diff']:+.4f} {m['ci95']}")
    print("certified statement verdicts", res["certified_statement_verdicts"])
    print("same-SQL observation changes by statement kind:", a.get("divergent_statement_sources"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
