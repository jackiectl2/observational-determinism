"""Certify the natural agent probes of pilot R2-1 and check the certificates against measured divergence.

For every eligible probe: verdict, reason, rewrite; the rewrite is executed on the SF1 DuckDB copy and its
result bag compared with the raw result (they must be equal when the query has no LIMIT/OFFSET, and the
rewrite must return the same number of rows otherwise). Soundness check available from existing data:
a DET probe runs unchanged, so its raw observation must not have diverged across the five equivalent
DuckDB executions recorded in divergence_v2.jsonl.

Usage: python cert_probes.py <catalog.json> <divergence_v2.jsonl> <duckdb_dir> <out.jsonl>
"""
import json
import sys
from collections import Counter

import duckdb

from certify import certify, smartlex

D = ["d1", "d8_run1", "d8_run2", "p1", "p8"]


def bag(rows):
    return sorted(json.dumps(list(r), default=str) for r in rows)


def main(cat_path, div_path, duck_dir, out_path):
    cat = json.load(open(cat_path))
    rows = [json.loads(l) for l in open(div_path)]
    cons = {}
    out = open(out_path, "w")
    stats, reasons, bad = Counter(), Counter(), []
    for r in rows:
        if not all(r["cfg"][c]["success"] and not r["cfg"][c]["truncated"] for c in D):
            continue
        db, sql = r["db_id"], r["sql"]
        raw_div = len({r["cfg"][c]["raw_sha"] for c in D}) > 1
        cert = certify(sql, cat[db], "duckdb")
        rec = {"db_id": db, "sql": sql, "occurrences": r["occurrences"], "verdict": cert.verdict, "reason": cert.reason,
               "tie_break": cert.tie_break, "rewritten": cert.rewritten, "raw_diverged": raw_div, "info": r["info"]}
        if db not in cons:
            cons[db] = duckdb.connect(f"{duck_dir}/{db}.duckdb", read_only=True)
        con = cons[db]
        try:
            base = con.execute(sql).fetchall()
            n_out = len(con.description)
            rec["n_rows"] = len(base)
            rec["n_out"] = n_out
        except Exception as ex:  # noqa: BLE001
            rec["exec_error"] = str(ex)[:200]
            base, n_out = None, None
        if cert.rewritten and base is not None:
            try:
                rw = con.execute(cert.rewritten).fetchall()
                has_lim = bool(r["info"].get("has_limit") or r["info"].get("has_offset"))
                rec["rewrite_ok"] = (len(rw) == len(base)) if has_lim else (bag(rw) == bag(base))
            except Exception as ex:  # noqa: BLE001
                rec["rewrite_ok"] = False
                rec["rewrite_error"] = str(ex)[:200]
        if n_out:
            rec["smartlex"] = smartlex(sql, n_out, "duckdb")
        stats[cert.verdict] += 1
        if cert.verdict == "UNSUPPORTED":
            reasons[cert.reason.split(":")[0] + (":" + cert.reason.split(":")[1] if ":" in cert.reason else "")] += 1
        if cert.verdict == "DET" and raw_div:
            bad.append(rec)
        if rec.get("rewrite_ok") is False:
            stats["rewrite_failed"] += 1
        out.write(json.dumps(rec, default=str) + "\n")
    out.close()
    n = sum(stats[v] for v in ("DET", "NARROW", "ALL", "UNSUPPORTED"))
    print("probes", n, {k: f"{v} ({100 * v / n:.1f}%)" for k, v in stats.items()})
    print("UNSUPPORTED reasons:", reasons.most_common(15))
    print("DET probes whose raw observation diverged (soundness violations):", len(bad))
    for b in bad[:10]:
        print("  ", b["db_id"], b["sql"][:200], "|", b["reason"])
    div = Counter((json.loads(l)["verdict"], json.loads(l)["raw_diverged"]) for l in open(out_path))
    print("verdict x raw_diverged:", dict(div))


if __name__ == "__main__":
    main(*sys.argv[1:5])
