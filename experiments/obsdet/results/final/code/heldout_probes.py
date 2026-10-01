"""Held-out probes: the distinct SQL statements the E4 agents issued (both models, all conditions, 11 databases),
certified with the frozen certifier, in the format of cert_probes.py so that replay_sound.py, replay_pg.py and
distribution.py run on them unchanged. Statements already in the development probe set are flagged (`in_dev`).

Usage: python heldout_probes.py <catalog.json> <dev_cert_probes.jsonl> <duckdb_dir> <out.jsonl> <e4_run_dir> ...
"""
import json
import sys
from collections import Counter, defaultdict

import duckdb
import sqlglot
from sqlglot import exp

from certify import certify, smartlex


def bag(rows):
    return sorted(json.dumps(list(r), default=str) for r in rows)


def info_of(sql):
    try:
        stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except Exception:  # noqa: BLE001
        return {"parse_ok": False}
    if len(stmts) != 1:
        return {"parse_ok": True, "kind": "multi"}
    a = stmts[0]
    return {"parse_ok": True, "kind": a.key, "has_order": a.args.get("order") is not None,
            "has_limit": a.args.get("limit") is not None, "has_offset": a.args.get("offset") is not None,
            "has_distinct": a.args.get("distinct") is not None, "has_group": a.args.get("group") is not None,
            "has_agg": any(True for _ in a.find_all(exp.AggFunc))}


def main(cat_path, dev_path, duck_dir, out_path, *run_dirs):
    cat = json.load(open(cat_path))
    dev = {(json.loads(l)["db_id"], json.loads(l)["sql"]) for l in open(dev_path)}
    occ, models = Counter(), defaultdict(set)
    for d in run_dirs:
        model = d.rstrip("/").split("/")[-1]
        for line in open(f"{d}/trace.jsonl"):
            r = json.loads(line)
            occ[(r["db_id"], r["sql"])] += 1
            models[(r["db_id"], r["sql"])].add(model)
    cons, stats = {}, Counter()
    out = open(out_path, "w")
    for (db, sql), n in sorted(occ.items()):
        cert = certify(sql, cat[db], "duckdb")
        rec = {"db_id": db, "sql": sql, "occurrences": n, "models": sorted(models[(db, sql)]),
               "in_dev": (db, sql) in dev, "verdict": cert.verdict, "reason": cert.reason,
               "tie_break": cert.tie_break, "rewritten": cert.rewritten, "info": info_of(sql)}
        if db not in cons:
            cons[db] = duckdb.connect(f"{duck_dir}/{db}.duckdb", read_only=True)
        con = cons[db]
        try:
            base = con.execute(sql).fetchall()
            rec["n_rows"], rec["n_out"] = len(base), len(con.description)
        except Exception as ex:  # noqa: BLE001
            rec["exec_error"] = str(ex)[:200]
            base = None
        if cert.rewritten and base is not None:
            try:
                rw = con.execute(cert.rewritten).fetchall()
                lim = rec["info"].get("has_limit") or rec["info"].get("has_offset")
                rec["rewrite_ok"] = (len(rw) == len(base)) if lim else (bag(rw) == bag(base))
            except Exception as ex:  # noqa: BLE001
                rec["rewrite_ok"], rec["rewrite_error"] = False, str(ex)[:200]
        if base is not None:
            rec["smartlex"] = smartlex(sql, rec["n_out"], "duckdb")
        stats[(rec["in_dev"], "exec_error" in rec, cert.verdict)] += 1
        if rec.get("rewrite_ok") is False:
            stats["rewrite_failed"] += 1
        out.write(json.dumps(rec, default=str) + "\n")
    out.close()
    print("distinct statements", len(occ), "| in dev set", sum(1 for k in occ if k in dev))
    for k, v in sorted(stats.items(), key=str):
        print(" ", k, v)


if __name__ == "__main__":
    main(*sys.argv[1:])
