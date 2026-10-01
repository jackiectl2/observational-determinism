"""Check that a private PostgreSQL server (pg_setup.py) still holds the databases that run_e1pg*.sbatch loaded:
for every <db>_sf1 and <db>_perm42, the database exists, its tables are the DuckDB source's tables (lower-cased) with
equal row counts, and the number of primary-key/unique constraints equals the number of declared catalog keys.
Exits non-zero on any mismatch. The server must be running.

Usage: python pg_check.py <server> <db> [<db> ...]
"""
import json
import sys

import duckdb

from pg_setup import CATALOG, V, conninfo, duck_path  # also puts psycopg (pilot_c6/pylib) on sys.path
import psycopg  # noqa: E402


def main(server, *dbs):
    cat = json.load(open(CATALOG))
    bad = []
    for db in dbs:
        for sc in ("sf1", "perm42"):
            src = f"{V}/data/pilot_r2_1/{db}_perm42.duckdb" if sc == "perm42" else duck_path(db, "sf1")
            d = duckdb.connect(src, read_only=True)
            want = {t.lower(): d.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in d.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' "
                "AND table_type = 'BASE TABLE'").fetchall()}
            d.close()
            with psycopg.connect(conninfo(server, f"{db}_{sc}".lower()), autocommit=True) as con:
                got = {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in con.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()}
                n_keys = con.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                                     "WHERE n.nspname = 'public' AND c.contype IN ('p', 'u')").fetchone()[0]
            n_want = sum(len(v.get("keys", [])) for v in cat[db].values())
            ok = got == want and n_keys == n_want
            print(f"{db}_{sc}: {len(got)} tables, {sum(got.values())} rows, keys {n_keys}/{n_want}:",
                  "ok" if ok else f"MISMATCH {sorted(set(got.items()) ^ set(want.items()))[:6]}", flush=True)
            if not ok:
                bad.append(f"{db}_{sc}")
    print("pg_check:", "all ok" if not bad else f"FAILED {bad}", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(*sys.argv[1:])
