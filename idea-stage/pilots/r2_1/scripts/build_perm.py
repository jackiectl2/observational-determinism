# Physically permuted copy of a BIRD DuckDB database: same rows, same schema, rows of every table stored
# in a fixed pseudo-random order (ORDER BY hash(rowid, seed)); DuckDB preserves insertion order on scans.
import argparse
import os
import sys

import duckdb

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import db_path, quote_ident, SKIP_TABLES  # noqa: E402

OUT = os.environ["PROJECT_ROOT"] + "/data/pilot_r2_1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    dst = f"{OUT}/{args.db}_perm{args.seed}.duckdb"
    if os.path.exists(dst):
        os.remove(dst)
    con = duckdb.connect(dst)
    con.execute("SET threads=8")
    con.execute(f"ATTACH '{db_path(args.db)}' AS src (READ_ONLY)")
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE database_name='src' AND schema_name='main' ORDER BY 1").fetchall()]
    for t in tables:
        qt = quote_ident(t)
        con.execute(f"CREATE TABLE {qt} AS SELECT * FROM src.{qt} ORDER BY hash(rowid, {args.seed})")
        same = con.execute(f"SELECT count(*) FROM (SELECT rowid AS r, * FROM {qt}) a").fetchone()[0]
        print(f"  {t}: {same} rows", flush=True)
    con.execute("DETACH src")
    con.execute("CHECKPOINT")
    con.close()
    print("built", dst)


if __name__ == "__main__":
    main()
