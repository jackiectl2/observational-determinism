"""Held-out tables after removing statements that equal a development probe up to comments, trailing semicolons
and whitespace (review round 2). Reads the held-out certificates and both replay outputs; prints the DuckDB and
PostgreSQL divergence tables and the verdict distribution of the remaining held-out statements.

Usage: python heldout_dedup.py <dev_cert_probes.jsonl> <cert_heldout_all.jsonl> <sound_heldout.jsonl> <sound_pg_heldout.jsonl>
"""
import json
import re
import sys
from collections import Counter


def norm(sql):
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"\s+", " ", sql).strip().rstrip(";").strip()


def table(path, keep, name):
    summ = Counter()
    for line in open(path):
        r = json.loads(line)
        if (r["db_id"], r["sql"]) not in keep:
            continue
        for pol, v in r.get("policies", {}).items():
            summ[(pol, r["verdict"], v.get("diverged"))] += 1
    print(f"{name}: policy x verdict diverged / complete (censored)")
    for pol in ("raw", "smartlex", "certified"):
        print("  " + pol.ljust(9) + " ".join(
            f"{v}={summ[(pol, v, True)]}/{summ[(pol, v, True)] + summ[(pol, v, False)]}({summ[(pol, v, None)]})"
            for v in ("DET", "NARROW", "ALL", "UNSUPPORTED")))


def main(dev_path, all_path, duck_path, pg_path):
    dev = {(json.loads(l)["db_id"], norm(json.loads(l)["sql"])) for l in open(dev_path)}
    recs = [json.loads(l) for l in open(all_path)]
    cand = [r for r in recs if not r["in_dev"]]
    dup = [r for r in cand if (r["db_id"], norm(r["sql"])) in dev]
    kept = [r for r in cand if (r["db_id"], norm(r["sql"])) not in dev]
    ok = [r for r in kept if "exec_error" not in r]
    print(f"candidates not in dev (exact): {len(cand)}; normalized duplicates of dev probes: {len(dup)}; "
          f"kept: {len(kept)}; executable: {len(ok)}; not executable: {len(kept) - len(ok)}")
    c = Counter(r["verdict"] for r in ok)
    print("verdicts:", {v: f"{c[v]} ({100 * c[v] / len(ok):.1f}%)" for v in ("DET", "NARROW", "ALL", "UNSUPPORTED")})
    rep = [r for r in ok if r["verdict"] in ("NARROW", "ALL")]
    w = [len(r["tie_break"]) for r in rep]
    s = [r["n_out"] for r in rep]
    print(f"repaired {len(rep)}: mean tie-break {sum(w) / len(w):.2f} vs smart-lex {sum(s) / len(s):.2f}")
    keep = {(r["db_id"], r["sql"]) for r in ok}
    table(duck_path, keep, "DuckDB")
    table(pg_path, keep, "PostgreSQL (verdicts in the PostgreSQL dialect)")


if __name__ == "__main__":
    main(*sys.argv[1:5])
