"""E2: certificate distribution over natural agent probes.

(1) verdict shares overall and by probe class (distinct probes and occurrence-weighted); (2) tie-break width of
the certified rewrite vs smart-lex (which appends every output column); (3) ablation without declared keys
(every table keyless); (4) measured raw divergence per verdict (DET must be 0); (5) verdicts of the statements
issued in the E4 certified conditions, per model.

Usage: python distribution.py <cert_probes.jsonl> <catalog.json> <out.json> [<e4_run_dir> ...]
"""
import json
import os
import sys
from collections import Counter, defaultdict

import sqlglot
from sqlglot import exp

from certify import certify

VERDICTS = ["DET", "NARROW", "ALL", "UNSUPPORTED"]


def probe_class(info):
    if info.get("has_limit") or info.get("has_offset"):
        return "ORDER BY + LIMIT" if info.get("has_order") else "LIMIT, no ORDER BY"
    if info.get("has_order"):
        return "ORDER BY, no LIMIT"
    if info.get("has_distinct"):
        return "DISTINCT"
    if info.get("has_group"):
        return "GROUP BY"
    return "unordered SELECT"


def shares(counter):
    n = sum(counter.values())
    return {v: {"n": counter[v], "pct": round(100 * counter[v] / n, 1) if n else 0.0} for v in VERDICTS} | {"total": n}


def width(p):
    return len(p["tie_break"]) if p["verdict"] in ("NARROW", "ALL") else 0


def output_names(p):
    if "select_names" in p["info"]:
        return p["info"]["select_names"]
    try:  # held-out probes: take the output names from the SQL
        return ["*" if isinstance(e, exp.Star) or isinstance(getattr(e, "this", None), exp.Star) else e.alias_or_name
                for e in sqlglot.parse_one(p["sql"], read="duckdb").expressions]
    except Exception:  # noqa: BLE001
        return ["*"]


def non_output(p):
    """The key tie-break uses a column the query does not output (a star counts as outputting everything)."""
    names = {n.lower() for n in output_names(p)}
    if "*" in names or any(n.endswith(".*") for n in names):
        return False
    return any(t.split(".")[-1].strip('"').lower() not in names for t in p["tie_break"])


def main(cert_path, cat_path, out_path, *e4_dirs):
    probes = [json.loads(l) for l in open(cert_path)]
    probes = [p for p in probes if "exec_error" not in p]
    cat = json.load(open(cat_path))
    res = {"n_probes": len(probes), "n_occurrences": sum(p["occurrences"] for p in probes)}
    res["overall"] = shares(Counter(p["verdict"] for p in probes))
    occ = Counter()
    for p in probes:
        occ[p["verdict"]] += p["occurrences"]
    res["overall_occurrence_weighted"] = shares(occ)
    by_cls = defaultdict(Counter)
    for p in probes:
        by_cls[probe_class(p["info"])][p["verdict"]] += 1
    res["by_class"] = {c: shares(v) for c, v in sorted(by_cls.items())}
    res["unsupported_reasons"] = dict(Counter(p["reason"].split(":")[0] for p in probes if p["verdict"] == "UNSUPPORTED").most_common())
    # tie-break width vs smart-lex (number of appended sort keys) on probes that need a tie-break
    need = [p for p in probes if p["verdict"] in ("NARROW", "ALL")]
    cw = [width(p) for p in need]
    sw = [p["n_out"] for p in need]
    res["tie_break_width"] = {"n": len(need), "certified_hist": dict(sorted(Counter(cw).items())),
                              "certified_mean": round(sum(cw) / len(cw), 2),
                              "smartlex_mean": round(sum(sw) / len(sw), 2),
                              "smartlex_hist": dict(sorted(Counter(sw).items())),
                              "key_tie_break": sum(p["reason"] == "key tie-break" for p in need),
                              "non_output_key": sum(p["reason"] == "key tie-break" and non_output(p) for p in need)}
    # measured raw divergence (pilot R2-1: five equivalent DuckDB executions) per verdict
    dv = defaultdict(Counter)
    for p in probes:
        if "raw_diverged" in p:  # known only for the development probes (pilot replay)
            dv[p["verdict"]][p["raw_diverged"]] += 1
    res["raw_divergence_by_verdict"] = {v: {"diverged": dv[v][True], "total": dv[v][True] + dv[v][False]} for v in VERDICTS}
    # ablation: no declared keys
    nokey = {d: {t: {"columns": v["columns"], "keys": []} for t, v in tabs.items()} for d, tabs in cat.items()}
    trans, abl = Counter(), Counter()
    wid = []
    for p in probes:
        c = certify(p["sql"], nokey[p["db_id"]], "duckdb")
        abl[c.verdict] += 1
        trans[(p["verdict"], c.verdict)] += 1
        if c.verdict in ("NARROW", "ALL"):
            wid.append(len(c.tie_break))
    res["ablation_no_keys"] = {"overall": shares(abl), "transitions": {f"{a}->{b}": n for (a, b), n in sorted(trans.items())},
                               "tie_break_mean": round(sum(wid) / len(wid), 2) if wid else None}
    # E4 statements per model (certified conditions; distinct (db, sql) pairs)
    res["e4_by_model"] = {}
    for d in e4_dirs:
        seen = {}
        for line in open(os.path.join(d, "trace.jsonl")):
            r = json.loads(line)
            if r["cond"].startswith("cer_"):
                v = r["meta"].get("verdict") or "UNSUPPORTED"
                seen[(r["db_id"], r["sql"])] = v
        res["e4_by_model"][os.path.basename(d.rstrip("/"))] = shares(Counter(seen.values()))
    json.dump(res, open(out_path, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("n_probes", "overall", "tie_break_width", "raw_divergence_by_verdict")}, indent=1))
    for c, s in res["by_class"].items():
        print(f"{c:22s} " + " ".join(f"{v}={s[v]['n']}({s[v]['pct']}%)" for v in VERDICTS) + f" total={s['total']}")
    print("no-keys ablation:", res["ablation_no_keys"]["overall"], "mean width", res["ablation_no_keys"]["tie_break_mean"])
    for m, s in res["e4_by_model"].items():
        print(f"E4 {m}: " + " ".join(f"{v}={s[v]['n']}({s[v]['pct']}%)" for v in VERDICTS) + f" total={s['total']}")


if __name__ == "__main__":
    main(*sys.argv[1:])
