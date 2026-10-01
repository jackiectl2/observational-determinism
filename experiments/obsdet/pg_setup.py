"""E3/PostgreSQL: a private PostgreSQL 16 server (binaries bundled with the pgserver wheel) whose data directory
lives under runs/obsdet/pg/<name>/, loaded from the DuckDB copies of the BIRD databases.

Every table and column identifier is lowercased; the catalog keys are declared (first key PRIMARY KEY, further
keys UNIQUE), which creates their btree indexes; then VACUUM (FREEZE, ANALYZE). No other index is created.
Databases use UTF8 with the C (binary) collation, matching DuckDB's binary string order.
The server is tuned only for bulk loading of a disposable copy (fsync off, minimal WAL); query settings are
PostgreSQL defaults except shared_buffers, work_mem=64MB, effective_cache_size, jit=off, autovacuum=off.

python pg_setup.py start <name> <shared_buffers>
python pg_setup.py load <name> <db> <scale> [<db> <scale> ...]      creates database <db>_<scale>
python pg_setup.py stop <name>
"""
import json
import os
import shutil
import subprocess
import sys
import time

V = os.environ["PROJECT_ROOT"]
BIN = f"{V}/code/pilot_c6/pylib/pgserver/pginstall/bin"
PGROOT = f"{V}/runs/obsdet/pg"
CATALOG = f"{V}/runs/obsdet/catalog.json"
sys.path.append(f"{V}/code/pilot_c6/pylib")  # psycopg (appended: the venv's packages take precedence)
PGT = {"VARCHAR": "text", "BIGINT": "bigint", "INTEGER": "integer", "SMALLINT": "smallint", "DOUBLE": "double precision",
       "FLOAT": "real", "DATE": "date", "TIMESTAMP": "timestamp", "BOOLEAN": "boolean", "BLOB": "bytea"}


def sock(name):
    return f"/tmp/obsdet_e3pg_{name}"


def conninfo(name, db="postgres"):
    return f"host={sock(name)} dbname={db} user=postgres"


def qi(s):
    return '"' + s.replace('"', '""') + '"'


def duck_path(db, scale):
    if scale == "sf1":
        return f"{V}/data/bird_duckdb/validation/{db}.duckdb"
    return f"{V}/data/pilot_c3_scaled/{db}_{scale}.duckdb"


def start(name, shared_buffers):
    d = f"{PGROOT}/{name}"
    os.makedirs(sock(name), exist_ok=True)
    if not os.path.exists(f"{d}/PG_VERSION"):
        os.makedirs(PGROOT, exist_ok=True)
        subprocess.run([f"{BIN}/initdb", "-D", d, "-U", "postgres", "-A", "trust", "--locale=C", "--encoding=UTF8"],
                       check=True, stdout=subprocess.DEVNULL)
    if os.path.exists(f"{d}/postmaster.pid"):  # left by a job that ended without a clean stop (one job per data dir)
        print("[pg_setup] removing stale postmaster.pid", flush=True)
        os.remove(f"{d}/postmaster.pid")
    opts = (f"-k {sock(name)} -c listen_addresses='' -c shared_buffers={shared_buffers} -c work_mem=64MB "
            f"-c maintenance_work_mem=2GB -c effective_cache_size=40GB -c jit=off -c autovacuum=off "
            f"-c fsync=off -c synchronous_commit=off -c full_page_writes=off -c wal_level=minimal "
            f"-c max_wal_senders=0 -c max_wal_size=32GB -c max_connections=20")
    subprocess.run([f"{BIN}/pg_ctl", "-D", d, "-o", opts, "-l", f"{d}/server.log", "-w", "-t", "600", "start"],
                   check=True, stdout=subprocess.DEVNULL)
    import psycopg
    with psycopg.connect(conninfo(name), autocommit=True) as c:
        print("[pg_setup]", c.execute("select version()").fetchone()[0][:40], "shared_buffers",
              c.execute("show shared_buffers").fetchone()[0], flush=True)


def stop(name):
    subprocess.run([f"{BIN}/pg_ctl", "-D", f"{PGROOT}/{name}", "-m", "fast", "-w", "stop"], check=False)


def load(name, db, scale):
    import duckdb
    import psycopg
    t0 = time.time()
    keys = {t: v.get("keys", []) for t, v in json.load(open(CATALOG))[db].items()}
    target = f"{db}_{scale}".lower()
    with psycopg.connect(conninfo(name), autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {qi(target)}")
        admin.execute(f"CREATE DATABASE {qi(target)} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'")
    tmp = f"/tmp/obsdet_e3pg_load_{os.getpid()}"
    os.makedirs(tmp, exist_ok=True)
    dcon = duckdb.connect(duck_path(db, scale), read_only=True)
    dcon.execute("SET threads=8")
    con = psycopg.connect(conninfo(name, target), autocommit=True)
    tables = [r[0] for r in dcon.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' "
                                         "AND table_type='BASE TABLE' ORDER BY 1").fetchall()]
    nrows = {}
    for t in tables:
        sel, defs = [], []
        for c, ty, *_ in dcon.execute(f"DESCRIBE {qi(t)}").fetchall():
            base = ty.split("(")[0]
            pgt = ("numeric" + ty[len("DECIMAL"):]) if base == "DECIMAL" else PGT.get(base, "text")
            e = f"replace({qi(c)}, chr(0), '')" if base == "VARCHAR" else (f"'\\x' || hex({qi(c)})" if base == "BLOB" else qi(c))
            sel.append(e)
            defs.append(f"{qi(c.lower())} {pgt}")
        f = f"{tmp}/{t}.csv"
        dcon.execute(f"COPY (SELECT {', '.join(sel)} FROM {qi(t)}) TO '{f}' (FORMAT csv, HEADER false, NULL '\\N')")
        with con.transaction():
            con.execute(f"CREATE TABLE {qi(t.lower())} ({', '.join(defs)})")
            con.execute(f"COPY {qi(t.lower())} FROM '{f}' (FORMAT csv, NULL '\\N', FREEZE)")
        os.remove(f)
        for j, k in enumerate(keys.get(t, [])):
            kind = "PRIMARY KEY" if j == 0 else "UNIQUE"
            con.execute(f"ALTER TABLE {qi(t.lower())} ADD {kind} ({', '.join(qi(c.lower()) for c in k)})")
        con.execute(f"VACUUM (FREEZE, ANALYZE) {qi(t.lower())}")
        nrows[t.lower()] = con.execute(f"SELECT count(*) FROM {qi(t.lower())}").fetchone()[0]
        n_duck = dcon.execute(f"SELECT count(*) FROM {qi(t)}").fetchone()[0]
        assert nrows[t.lower()] == n_duck, (t, nrows[t.lower()], n_duck)
    size = con.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    con.close()
    dcon.close()
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"[pg_setup] loaded {target}: {len(tables)} tables, {sum(nrows.values())} rows, {size}, "
          f"{time.time() - t0:.0f}s", flush=True)


def main():
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "start":
        start(name, sys.argv[3])
    elif cmd == "stop":
        stop(name)
    elif cmd == "load":
        rest = sys.argv[3:]
        for db, scale in zip(rest[::2], rest[1::2]):
            load(name, db, scale)


if __name__ == "__main__":
    main()
