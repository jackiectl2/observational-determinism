"""Minimal reproductions of the findings of proptest.py on DuckDB and PostgreSQL 16.

Each case gives a catalog (as certify() takes it), rows and a raw query. Per engine the script records the
certificate (verdict, tie-break, ORDER BY columns the certifier resolved, rewritten SQL) and the distinct canonical
observations of the raw and of the certified query over equivalent executions: DuckDB 24 shuffled loads with
threads alternating 1/4; PostgreSQL 3 heap orders x serial/parallel-enabled (as in proptest.py).

Usage: python proptest_repro.py <out.json> [--pg] [--certify <path/to/certify.py>]
       (--pg starts the private server `proptest` of pg_setup.py)
"""
import json
import os
import random
import sys
from decimal import Decimal as D

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from certify import certify  # noqa: E402
from proptest import PARALLEL, certifier_id, observe_duck, observe_pg, use_certifier  # noqa: E402

PGT = {"INTEGER": "integer", "DECIMAL(10,2)": "numeric(10,2)", "VARCHAR": "text", "DOUBLE": "double precision",
       "BIGINT": "bigint", "TIMESTAMP": "timestamp", "TIMESTAMP WITH TIME ZONE": "timestamptz",
       "CHAR(3)": "character(3)"}
SESSION = ["SET TimeZone = 'America/New_York'"]  # PostgreSQL connections (harmless for the other cases)
T_ID = {"columns": {"id": "INTEGER"}, "keys": [["id"]]}
T_IDX = {"columns": {"id": "INTEGER", "x": "INTEGER"}, "keys": [["id"]]}
CASES = [
    {"name": "R1a duplicate output name: ORDER BY 1 is resolved to the other output named g (DET claimed)",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "VARCHAR"}, "keys": [["id"]]}},
     "rows": {"t": [(1, "a"), (2, "a"), (3, "b")]},
     "sql": "SELECT t.g, t.id AS g FROM t ORDER BY 1"},
    {"name": "R1b duplicate output name from two aliases: ORDER BY 1 resolved to b.id, tie-break a.id",
     "tables": {"t": T_ID}, "rows": {"t": [(1,), (2,), (3,)]},
     "sql": "SELECT a.id, b.id FROM t a, t b ORDER BY 1"},
    {"name": "R1c star over a USING join (spec: UNSUPPORTED) expands to two outputs named id",
     "tables": {"t": T_IDX, "u": T_IDX}, "rows": {"t": [(1, 1), (2, 1)], "u": [(1, 1), (2, 1)]},
     "sql": "SELECT * FROM t a JOIN u b USING (x) ORDER BY 1"},
    {"name": "R1d output names equal up to case (\"NAME\" vs name): ORDER BY name bound to the other output",
     "tables": {"t": {"columns": {"id": "INTEGER", "name": "VARCHAR", "x": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, "a", 1), (2, "b", 1), (3, "c", 2)]},
     "sql": "SELECT t.x AS \"NAME\", t.name FROM t ORDER BY name"},
    {"name": "R10 unary plus in ORDER BY: sqlglot drops it, so +1 is taken as ordinal 1; DuckDB sorts by the constant",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "VARCHAR"}, "keys": [["id"]]}},
     "rows": {"t": [(1, "b"), (2, "a"), (3, "c")]},
     "sql": "SELECT t.g FROM t ORDER BY +1"},
    {"name": "R2 SUM over DECIMAL / DECIMAL: typed DECIMAL by the certifier, DOUBLE in DuckDB (DET claimed)",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "INTEGER", "a": "DECIMAL(10,2)", "b": "DECIMAL(10,2)"},
                      "keys": [["id"]]}},
     "rows": {"t": [(1, 1, D("1.00"), D("10.00")), (2, 1, D("2.00"), D("10.00")), (3, 1, D("3.00"), D("10.00"))]},
     "sql": "SELECT t.g, SUM(t.a / t.b) FROM t GROUP BY t.g ORDER BY t.g",
     "probe": "SELECT typeof(t.a / t.b) FROM t LIMIT 1"},
    {"name": "R5 SUM over a scientific-notation literal: 1e-1 typed DECIMAL by the certifier, DOUBLE in DuckDB",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "INTEGER", "x": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 1, 1), (2, 1, 2), (3, 1, 3)]},
     "sql": "SELECT t.g, SUM(t.x * 1e-1) FROM t GROUP BY t.g ORDER BY t.g",
     "probe": "SELECT typeof(1e-1), typeof(t.x * 1e-1) FROM t LIMIT 1"},
    {"name": "R8 typed literal then :: (DECIMAL '0.1'::DOUBLE): sqlglot parses DECIMAL('0.1'::DOUBLE), DuckDB DOUBLE",
     "tables": {"t": {"columns": {"id": "INTEGER", "x": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 1), (2, 2), (3, 3)]},
     "sql": "SELECT SUM(t.x * DECIMAL '0.1'::DOUBLE) FROM t",
     "probe": "SELECT typeof(DECIMAL '0.1'::DOUBLE) FROM t LIMIT 1"},
    {"name": "R9 literal with more than 38 digits: DOUBLE in DuckDB, typed exact by the certifier",
     "tables": {"t": {"columns": {"id": "INTEGER", "x": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 1), (2, 2), (3, 3)]},
     "sql": "SELECT SUM(t.x * 0.1000000000000000000000000000000000000001) FROM t",
     "probe": "SELECT typeof(0.1000000000000000000000000000000000000001) FROM t LIMIT 1"},
    {"name": "R11 BIGINT = e-notation literal compares in DOUBLE (lossy): the constant does not pin the column",
     "tables": {"t": {"columns": {"id": "INTEGER", "big": "BIGINT"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 9007199254740992), (2, 9007199254740993), (3, 7)]},
     "sql": "SELECT t.big FROM t WHERE t.big = 9007199254740992e0 LIMIT 1"},
    {"name": "R12 same, grouped: two groups pass the lossy constant filter",
     "tables": {"t": {"columns": {"id": "INTEGER", "big": "BIGINT"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 9007199254740992), (2, 9007199254740993), (3, 7)]},
     "sql": "SELECT t.big, COUNT(*) FROM t WHERE t.big = 9007199254740992e0 GROUP BY t.big"},
    {"name": "R13 TIMESTAMP = TIMESTAMPTZ through the session time zone: 02:30 and 03:30 on 2018-03-11 (New York) are one instant",
     "tables": {"t": {"columns": {"id": "INTEGER", "ts": "TIMESTAMP"}, "keys": [["id"]]},
                "u": {"columns": {"id": "INTEGER", "tz": "TIMESTAMP WITH TIME ZONE"}, "keys": [["id"]]}},
     "rows": {"t": [(1, "2018-03-11 02:30:00"), (2, "2018-03-11 03:30:00")], "u": [(1, "2018-03-11 07:30:00+00")]},
     "session": SESSION,
     "sql": "SELECT t.ts FROM t JOIN u ON t.ts = u.tz ORDER BY u.tz"},
    {"name": "R14 CHAR(3) = VARCHAR ignores trailing blanks (PostgreSQL): 'a' and 'a ' both match",
     "tables": {"t": {"columns": {"id": "INTEGER", "ch": "CHAR(3)"}, "keys": [["id"]]},
                "u": {"columns": {"id": "INTEGER", "vc": "VARCHAR"}, "keys": [["id"]]}},
     "pgtypes": {"u": {"vc": "varchar"}},  # PostgreSQL character varying (the other cases map VARCHAR to text)
     "rows": {"t": [(1, "a")], "u": [(1, "a"), (2, "a ")]},
     "sql": "SELECT u.vc FROM t JOIN u ON t.ch = u.vc ORDER BY t.ch"},
    {"name": "R6 (known defect 2) SELECT DISTINCT with a non-output ORDER BY key",
     "tables": {"r": {"columns": {"id": "INTEGER", "name": "VARCHAR"}, "keys": [["id"]]},
                "s": {"columns": {"id": "INTEGER", "r_id": "INTEGER", "rank": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"r": [(1, "a"), (2, "b")], "s": [(1, 1, 5), (2, 1, 3), (3, 2, 4)]},
     "sql": "SELECT DISTINCT r.name FROM r JOIN s ON s.r_id = r.id ORDER BY s.rank LIMIT 1"},
    {"name": "R3 header renamed by the regenerated rewrite (bag unchanged; not a G2 violation)",
     "tables": {"t": T_IDX}, "rows": {"t": [(1, None), (2, 5)]},
     "sql": "SELECT a.x IS NOT NULL, a.x FROM t a"},
    {"name": "R7a typed literal + cast (DATE 'x'::VARCHAR) re-parsed as DATE(x::VARCHAR): rewrite changes the result",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 1), (2, 1)]},
     "sql": "SELECT t.g, DATE '2026-01-10'::VARCHAR < '2026-1-5' AS c FROM t"},
    {"name": "R7b same parse: the rewrite no longer binds (LENGTH(DATE))",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 1), (2, 1)]},
     "sql": "SELECT t.g, LENGTH(DATE '2026-01-10'::VARCHAR) AS c FROM t"},
    {"name": "R7c same parse: TIMESTAMP 'x'::DATE becomes CAST(CAST(x AS DATE) AS TIMESTAMP) (rendering changes)",
     "tables": {"t": {"columns": {"id": "INTEGER", "g": "INTEGER"}, "keys": [["id"]]}},
     "rows": {"t": [(1, 1), (2, 1)]},
     "sql": "SELECT t.g, TIMESTAMP '2026-01-10 10:00:00'::DATE AS c FROM t"},
    {"name": "R4b certified execution fails where the raw query succeeds (LIMIT stops before the bad row)",
     "tables": {"t": {"columns": {"id": "INTEGER", "s": "VARCHAR"}, "keys": [["id"]]}},
     "rows": {"t": [(1, "7"), (2, "x")]},
     "sql": "SELECT CAST(t.s AS INTEGER) FROM t WHERE t.id = 1 OR t.s = 'x' LIMIT 1"},
]


def shuffled(rows, key):
    rows = list(rows)
    random.Random(key).shuffle(rows)
    return rows


def duck_runs(case, sql, n=24):
    res = []
    for p in range(n):
        con = duckdb.connect()
        con.execute(f"SET threads={1 if p % 2 == 0 else 4}")
        for stmt in case.get("session", []):
            con.execute(stmt)
        for t, spec in case["tables"].items():
            con.execute(f"CREATE TABLE {t} ({', '.join(f'{c} {ty}' for c, ty in spec['columns'].items())})")
            rows = shuffled(case["rows"][t], f"repro-{p}-{t}")
            if rows:
                con.executemany(f"INSERT INTO {t} VALUES ({', '.join('?' * len(spec['columns']))})", rows)
        res.append(observe_duck(con, sql))
        con.close()
    return res


def pg_load(loader, case):
    for h in range(3):
        loader.execute(f"DROP SCHEMA IF EXISTS h{h} CASCADE")
        loader.execute(f"CREATE SCHEMA h{h}")
        for t, spec in case["tables"].items():
            over = case.get("pgtypes", {}).get(t, {})
            defs = ", ".join(f"{c} {over.get(c, PGT[ty])}" for c, ty in spec["columns"].items())
            loader.execute(f"CREATE TABLE h{h}.{t} ({defs})")
            rows = shuffled(case["rows"][t], f"repro-h{h}-{t}")
            if rows:
                with loader.cursor() as cur:
                    cur.executemany(f"INSERT INTO h{h}.{t} VALUES ({', '.join(['%s'] * len(spec['columns']))})", rows)
            for j, k in enumerate(spec["keys"]):
                loader.execute(f"ALTER TABLE h{h}.{t} ADD {'PRIMARY KEY' if j == 0 else 'UNIQUE'} ({', '.join(k)})")
            loader.execute(f"ANALYZE h{h}.{t}")


def digest(obs):
    ok = [o for o in obs if o["ok"]]
    distinct = {}
    for o in ok:
        distinct.setdefault(o["dig"], {"n": o["n"], "head": o["head"], "top": o["top"][:6]})
    return {"executions": len(obs), "succeeded": len(ok),
            "errors": sorted({o["err"] + ": " + o["msg"].split("\n")[0][:110] for o in obs if not o["ok"]}),
            "distinct_observations": len(distinct), "observations": list(distinct.values())[:3]}


def main():
    global certify
    out, use_pg = sys.argv[1], "--pg" in sys.argv
    if "--certify" in sys.argv:
        exp_md5 = sys.argv[sys.argv.index("--certify-md5") + 1] if "--certify-md5" in sys.argv else None
        certify = use_certifier(sys.argv[sys.argv.index("--certify") + 1], exp_md5).certify
    print("[repro] certifier", certifier_id(), flush=True)
    engines = [("duckdb", lambda case, sql: duck_runs(case, sql))]
    stop = None
    if use_pg:
        import pg_setup
        import psycopg
        from pg_cost import to_pg
        pg_setup.start("proptest", "1GB")
        stop = lambda: pg_setup.stop("proptest")  # noqa: E731
        with psycopg.connect(pg_setup.conninfo("proptest"), autocommit=True) as adm:
            adm.execute("DROP DATABASE IF EXISTS repro")
            adm.execute("CREATE DATABASE repro TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'")
        ci = pg_setup.conninfo("proptest", "repro")
        loader = psycopg.connect(ci, autocommit=True)
        cons = []
        for h in range(3):
            for w in (0, 4):
                c = psycopg.connect(ci, autocommit=True, prepare_threshold=None)
                c.execute(f"SET search_path = h{h}")
                c.execute(f"SET max_parallel_workers_per_gather = {w}")
                for s in (PARALLEL if w else []) + SESSION:
                    c.execute(s)
                cons.append(c)
        engines.append(("postgres", lambda case, sql: [observe_pg(c, sql) for c in cons]))
    results = []
    try:
        for case in CASES:
            rec = {"name": case["name"], "schema": case["tables"],
                   "rows": {t: [[str(v) if isinstance(v, D) else v for v in r] for r in rows]
                            for t, rows in case["rows"].items()}}
            for eng, runs in engines:
                sql = case["sql"] if eng == "duckdb" else to_pg(case["sql"])
                if eng == "postgres":
                    pg_load(loader, case)
                c = certify(sql, case["tables"], eng)
                run = sql if c.verdict == "DET" else c.rewritten
                r = {"sql": sql, "verdict": c.verdict, "reason": c.reason, "tie_break": c.tie_break,
                     "order_cols": [list(x) for x in c.evidence.get("order_cols", [])], "certified_sql": run,
                     "raw": digest(runs(case, sql))}
                if run:
                    r["certified"] = digest(runs(case, run))
                if eng == "duckdb" and case.get("probe"):
                    r["probe"] = [case["probe"], runs(case, case["probe"])[0].get("top")]
                rec[eng] = r
            results.append(rec)
            print(json.dumps(rec)[:2500], flush=True)
    finally:
        if stop:
            stop()
    json.dump(results, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
