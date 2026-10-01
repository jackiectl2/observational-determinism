"""E3 diagnostic: one natural probe on PostgreSQL under the preview + count model with a long timeout (one run per
query, uncensored unless the long timeout is hit), plus the plain EXPLAIN plan of each query.

python pg_probe_diag.py <server> <db> <scale> <probe index> <cert_probes.jsonl> <timeout s> <out.json>
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cost_duck import pc_queries, variants  # noqa: E402
from pg_cost import to_pg  # noqa: E402
from pg_setup import conninfo  # noqa: E402

import psycopg  # noqa: E402


def main(server, db, scale, idx, probes, timeout, out):
    r = [json.loads(line) for line in open(probes)][int(idx)]
    q = {k: to_pg(v) for k, v in pc_queries(variants(r)).items()}
    con = psycopg.connect(conninfo(server, f"{db}_{scale}"), autocommit=True)
    con.execute(f"SET statement_timeout = {int(float(timeout) * 1000)}")
    res = {"probe": int(idx), "db": db, "scale": scale, "verdict": r["verdict"], "timeout_s": float(timeout), "sql": q}
    for k, sql in q.items():
        plan = con.execute("EXPLAIN " + sql).fetchall()
        t0 = time.perf_counter()
        try:
            n = len(con.execute(sql).fetchall())
            st = "ok"
        except psycopg.errors.QueryCanceled:
            n, st = None, "timeout"
        res[k] = {"status": st, "t": round(time.perf_counter() - t0, 3), "rows": n, "plan": [p[0] for p in plan]}
        print(k, st, res[k]["t"], flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:8])
