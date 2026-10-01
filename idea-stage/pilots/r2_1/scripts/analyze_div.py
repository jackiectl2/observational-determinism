# Analysis of steps 1 + 2 (pilot R2-1): observation divergence across equivalent executions, OBSERVE residual,
# semantic-contract checks, and overhead. Primary population = ELIGIBLE exploratory probes: successful in all
# five DuckDB executions with the complete logical output collected (no 100,000-row truncation); SQLite
# (cross-engine) is reported separately and excluded from the primary numbers.
import argparse
import collections
import json
import statistics

DUCK = ["d1", "d8_run1", "d8_run2", "p1", "p8"]
PAIRS = {"threads_1_vs_8": ("d1", "d8_run1"), "repeat_8_threads": ("d8_run1", "d8_run2"),
         "permuted_order_1_thread": ("d1", "p1"), "permuted_order_8_threads": ("d8_run1", "p8")}
MODES = ["raw", "hash", "lex", "canon"]  # raw tool, OBSERVE v1 (client hash), OBSERVE-lex, OBSERVE v2 (canonical)


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def size_bucket(n):
    return "0 rows" if n == 0 else "1 row" if n == 1 else "2-20 rows" if n <= 20 else ">20 rows"


def weighted_frac(rs, pred):
    w = sum(r["occurrences"] for r in rs)
    return sum(r["occurrences"] for r in rs if pred(r)) / w if w else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--div", required=True)
    ap.add_argument("--timing", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    R = [json.loads(l) for l in open(args.div)]
    elig = [r for r in R if all(r["cfg"][c]["success"] and not r["cfg"][c]["truncated"] for c in DUCK)]
    truncated = [r for r in R if any(r["cfg"][c]["success"] and r["cfg"][c]["truncated"] for c in DUCK)]
    failed = [r for r in R if not all(r["cfg"][c]["success"] for c in DUCK)]
    out = {"n_distinct": len(R), "n_probes": sum(r["occurrences"] for r in R),
           "eligible": {"n_distinct": len(elig), "n_probes": sum(r["occurrences"] for r in elig)},
           "ineligible_truncated": {"n_distinct": len(truncated), "n_probes": sum(r["occurrences"] for r in truncated)},
           "ineligible_failed_in_some_config": {"n_distinct": len(failed)},
           "pairs": {}, "any_perturbation": {}, "by_type": {}, "by_size": {}, "contract": {}, "residual_canon": [],
           "examples": {}, "sqlite_secondary": {}, "tasks": {}}

    def key(mode, measure):
        return f"{mode}_{'sha' if measure == 'text' else 'sig'}"

    for pname, (a, b) in PAIRS.items():
        p = {"n_distinct": len(elig), "n_probes": out["eligible"]["n_probes"]}
        for mode in MODES:
            for measure in ("text", "sig"):
                kk = key(mode, measure)
                dd = [r for r in elig if r["cfg"][a][kk] != r["cfg"][b][kk]]
                p[f"{mode}_{measure}_distinct"] = len(dd)
                p[f"{mode}_{measure}_frac_probes"] = weighted_frac(elig, lambda r, a=a, b=b, kk=kk: r["cfg"][a][kk] != r["cfg"][b][kk])
        rawd = [r for r in elig if r["cfg"][a]["raw_sha"] != r["cfg"][b]["raw_sha"]]
        p["raw_diff_same_multiset"] = sum(r["cfg"][a]["bag"] == r["cfg"][b]["bag"] for r in rawd)
        p["raw_diff_only_float_digits_or_header"] = sum(r["cfg"][a]["raw_sig"] == r["cfg"][b]["raw_sig"] for r in rawd)
        for mode in ("hash", "lex", "canon"):
            nr = p["raw_text_frac_probes"]
            p[f"{mode}_removed_share_probes"] = (1 - p[f"{mode}_text_frac_probes"] / nr) if nr else None
        out["pairs"][pname] = p
    anyd = lambda r, kk: len({r["cfg"][c][kk] for c in DUCK}) > 1
    for mode in MODES:
        for measure in ("text", "sig"):
            kk = key(mode, measure)
            out["any_perturbation"][f"{mode}_{measure}_distinct"] = sum(anyd(r, kk) for r in elig)
            out["any_perturbation"][f"{mode}_{measure}_frac_probes"] = weighted_frac(elig, lambda r, kk=kk: anyd(r, kk))
    base = out["any_perturbation"]["raw_text_frac_probes"]
    for mode in ("hash", "lex", "canon"):
        out["any_perturbation"][f"{mode}_removed_share_probes"] = 1 - out["any_perturbation"][f"{mode}_text_frac_probes"] / base if base else None
        out["any_perturbation"][f"{mode}_removed_share_distinct"] = 1 - out["any_perturbation"][f"{mode}_text_distinct"] / out["any_perturbation"]["raw_text_distinct"]
    # tasks with >= 1 divergent eligible probe
    tasks = sorted({t for r in R for t in r["tasks"]})
    per_task_perm = collections.Counter(t for r in elig if r["cfg"]["d1"]["raw_sha"] != r["cfg"]["p1"]["raw_sha"] for t in r["tasks"])
    per_task_any = collections.Counter(t for r in elig if anyd(r, "raw_sha") for t in r["tasks"])
    out["tasks"] = {"n": len(tasks), "with_divergent_probe_any": len(per_task_any), "with_divergent_probe_permuted": len(per_task_perm),
                    "per_task_divergent_distinct_statements_permuted": dict(per_task_perm),
                    "per_task_divergent_distinct_statements_any": dict(per_task_any)}
    # splits
    for label, fn in (("by_type", lambda r: r["type"]), ("by_size", lambda r: size_bucket(r["cfg"]["d1"]["n_rows"]))):
        groups = collections.defaultdict(list)
        for r in elig:
            groups[fn(r)].append(r)
        for g, rs in sorted(groups.items()):
            out[label][g] = {"n_distinct": len(rs), "n_probes": sum(r["occurrences"] for r in rs)}
            for pname, (a, b) in PAIRS.items():
                out[label][g][f"raw_{pname}"] = weighted_frac(rs, lambda r, a=a, b=b: r["cfg"][a]["raw_sha"] != r["cfg"][b]["raw_sha"])
            for mode in MODES:
                out[label][g][f"{mode}_any"] = weighted_frac(rs, lambda r, kk=key(mode, "text"): anyd(r, kk))
    # semantic contract of canonical OBSERVE (v2): all five DuckDB executions of every eligible statement
    viol, checked, checks_by = collections.Counter(), 0, collections.Counter()
    examples_viol = []
    not_applied = collections.Counter()
    for r in elig:
        for c in DUCK:
            v = r["cfg"][c].get("contract")
            path = r["cfg"][c].get("canon_meta", {}).get("path")
            if path == "unchanged":  # OBSERVE not applied (unparsable / multi-statement / command): raw output,
                not_applied[r["type"]] += 1  # so there is no OBSERVE output to check; counted separately
                continue
            if v is None:
                continue
            checked += 1
            for kk, x in v.items():
                checks_by[kk] += 1
                if x:
                    viol[kk] += 1
                    if len(examples_viol) < 10:
                        examples_viol.append({"cfg": c, "check": kk, "sql": r["sql"][:300]})
    out["contract"] = {"executions_checked": checked, "checks_by_kind": dict(checks_by), "violations": dict(viol),
                       "examples": examples_viol, "executions_observe_not_applied_by_type": dict(not_applied),
                       "distinct_statements_observe_not_applied": sum(r["cfg"]["d1"].get("canon_meta", {}).get("path") == "unchanged" for r in elig)}
    # residual divergence under canonical OBSERVE
    for r in elig:
        if anyd(r, "canon_sha"):
            out["residual_canon"].append({"db_id": r["db_id"], "type": r["type"], "sql": r["sql"][:500],
                                          "bags_differ": len({r["cfg"][c]["bag"] for c in DUCK}) > 1,
                                          "path": r["cfg"]["d1"]["canon_meta"].get("path"),
                                          "configs_distinct_obs": len({r["cfg"][c]["canon_sha"] for c in DUCK})})
    # cross-engine (secondary, not in the primary numbers): SQLite vs DuckDB 1 thread
    sq_ok = [r for r in R if r["cfg"]["d1"]["success"] and r["cfg"].get("sqlite", {}).get("success") and not r["cfg"]["d1"]["truncated"]]
    sq_eq = [r for r in sq_ok if r["cfg"]["d1"]["bag"] == r["cfg"]["sqlite"]["bag"]]
    out["sqlite_secondary"] = {"distinct_ok_both": len(sq_ok), "distinct_same_multiset": len(sq_eq),
                               "raw_text_diff": sum(r["cfg"]["d1"]["raw_sha"] != r["cfg"]["sqlite"]["raw_sha"] for r in sq_eq),
                               "raw_sig_diff": sum(r["cfg"]["d1"]["raw_sig"] != r["cfg"]["sqlite"]["raw_sig"] for r in sq_eq),
                               "hash_sig_diff": sum(r["cfg"]["d1"]["hash_sig"] != r["cfg"]["sqlite"]["hash_sig"] for r in sq_eq),
                               "lex_sig_diff": sum(r["cfg"]["d1"]["lex_sig"] != r["cfg"]["sqlite"]["lex_sig"] for r in sq_eq)}
    # examples of raw divergence under permutation (one per statement type)
    seen = set()
    for r in sorted(elig, key=lambda r: -r["occurrences"]):
        if r["cfg"]["d1"]["raw_sha"] == r["cfg"]["p1"]["raw_sha"] or r["type"] in seen:
            continue
        seen.add(r["type"])
        out["examples"][r["type"]] = {"db_id": r["db_id"], "sql": r["sql"], "occurrences": r["occurrences"],
                                      "d1_raw": (r["cfg"]["d1"]["raw_text"] or "")[:800], "p1_raw": (r["cfg"]["p1"]["raw_text"] or "")[:800],
                                      "d1_canon": (r["cfg"]["d1"]["canon_text"] or "")[:800], "p1_canon": (r["cfg"]["p1"]["canon_text"] or "")[:800]}
    # overhead: divergence-run timings (v1 hash, lex, canonical v2) and the dedicated timing run (v2, v3, v4)
    ov = {}
    for scale in ("1", "10"):
        rs = [r for r in elig if scale in r["timing"] and r["timing"][scale]["raw_ok"] and r["timing"][scale]["raw_s"] > 0]
        o = {"n_distinct": len(rs)}
        for v in ("hash", "lex", "canon"):
            rat = [(r["timing"][scale][f"{v}_engine_s"] + r["timing"][scale][f"{v}_client_s"]) / r["timing"][scale]["raw_s"] - 1 for r in rs]
            ratw = [x for r, x in zip(rs, rat) for _ in range(r["occurrences"])]
            o[v] = {"median": statistics.median(rat), "p95": q(rat, 0.95), "median_probes": statistics.median(ratw), "p95_probes": q(ratw, 0.95),
                    "sum_ratio": sum(r["timing"][scale][f"{v}_engine_s"] + r["timing"][scale][f"{v}_client_s"] for r in rs) / sum(r["timing"][scale]["raw_s"] for r in rs) - 1}
        ov[f"divergence_run_sf{scale}"] = o
    if args.timing:
        T = {(t["db_id"], t["sql"]): t for t in (json.loads(l) for l in open(args.timing))}
        for scale in ("1", "10"):
            rs = [T[(r["db_id"], r["sql"])] for r in elig if (r["db_id"], r["sql"]) in T]
            rs = [t for t in rs if t["timing"][scale]["eligible"] and t["timing"][scale]["raw_s"] > 0]
            o = {"n_distinct": len(rs)}
            for v in ("v2", "v3", "v4"):
                rat = [t["timing"][scale][f"{v}_s"] / t["timing"][scale]["raw_s"] - 1 for t in rs]
                ratw = [x for t, x in zip(rs, rat) for _ in range(t["occurrences"])]
                o[v] = {"median": statistics.median(rat), "p95": q(rat, 0.95), "median_probes": statistics.median(ratw),
                        "p95_probes": q(ratw, 0.95),
                        "sum_ratio": sum(t["timing"][scale][f"{v}_s"] for t in rs) / sum(t["timing"][scale]["raw_s"] for t in rs) - 1}
            ov[f"timing_run_sf{scale}"] = o
        # determinism of v3 / v4 across the five DuckDB executions (eligible statements)
        det = {}
        for v in ("v3", "v4"):
            rs = [T[(r["db_id"], r["sql"])] for r in elig if (r["db_id"], r["sql"]) in T]
            det[v] = {"n_distinct": len(rs), "diverging_distinct": sum(len({t[v][c]["sha"] for c in DUCK}) > 1 for t in rs),
                      "diverging_frac_probes": weighted_frac(rs, lambda t, v=v: len({t[v][c]["sha"] for c in DUCK}) > 1),
                      "paths": dict(collections.Counter(t[v]["d1"]["path"] for t in rs)),
                      "fallbacks": sum(t[v]["d1"]["fallback"] for t in rs)}
        out["determinism_v3_v4"] = det
    out["overhead"] = ov
    json.dump(out, open(args.out, "w"), indent=1, default=str)
    # console summary
    print("distinct", len(R), "eligible", len(elig), "probes", out["n_probes"], "eligible probes", out["eligible"]["n_probes"],
          "truncated(ineligible)", len(truncated), "failed-somewhere", len(failed))
    for pname, p in out["pairs"].items():
        print(f"{pname:26s} raw text {p['raw_text_frac_probes']:.3f} (sig {p['raw_sig_frac_probes']:.3f}) | v1-hash {p['hash_text_frac_probes']:.3f} "
              f"lex {p['lex_text_frac_probes']:.3f} canon {p['canon_text_frac_probes']:.3f} | removed(canon) {p['canon_removed_share_probes']} "
              f"| same-multiset {p['raw_diff_same_multiset']}/{p['raw_text_distinct']}")
    print("any perturbation:", {k: round(v, 4) if isinstance(v, float) else v for k, v in out["any_perturbation"].items()})
    print("tasks:", out["tasks"]["n"], "with divergent probe (any):", out["tasks"]["with_divergent_probe_any"], "(perm):", out["tasks"]["with_divergent_probe_permuted"])
    for g, x in out["by_type"].items():
        print(f"  type {g:24s} n={x['n_probes']:4d} perm {x['raw_permuted_order_1_thread']:.3f} thr {x['raw_threads_1_vs_8']:.3f} rep {x['raw_repeat_8_threads']:.3f} any {x['raw_any']:.3f} -> canon {x['canon_any']:.3f}")
    for g, x in out["by_size"].items():
        print(f"  size {g:10s} n={x['n_probes']:4d} any {x['raw_any']:.3f} -> canon {x['canon_any']:.3f}")
    print("contract:", out["contract"]["executions_checked"], out["contract"]["checks_by_kind"], out["contract"]["violations"])
    print("residual canon:", len(out["residual_canon"]), "sqlite:", out["sqlite_secondary"])
    for k, o in ov.items():
        print(k, {v: {kk: round(vv, 3) for kk, vv in x.items()} if isinstance(x, dict) else x for v, x in o.items()})
    if "determinism_v3_v4" in out:
        print("determinism:", out["determinism_v3_v4"])


if __name__ == "__main__":
    main()
