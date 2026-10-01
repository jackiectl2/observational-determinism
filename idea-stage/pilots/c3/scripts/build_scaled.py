# Build a scaled copy of a BIRD DuckDB database as SF disjoint copies of the original ("key-offset
# replication"). Copy k (k = 0..SF-1) of every table is the original table with
#   * every integer key column (name 'id', or ending in 'Id' / 'ID' / '_id', not containing 'type')
#     shifted by k * OFF, where OFF is a power of ten larger than any key value in the database;
#   * every string key column listed in STR_KEYS suffixed with '~k' for k >= 1.
# Key-equality joins therefore stay within one copy (join fan-out is unchanged, work grows ~SF x), while
# non-key attributes (names, dates, scores, type codes) are duplicated, so a filter on a non-key value
# matches SF x more rows and a filter on a key literal still hits one entity (copy 0).
# Tables in NO_REPLICATE are copied once (their join key is not an id column).
import argparse
import os
import time

import duckdb

from common import db_path, quote_ident, SCALED_DIR, SKIP_TABLES

INT_TYPES = {"TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT"}
STR_KEYS = {
    "card_games": {"uuid", "setcode", "code", "parentcode"},
    "california_schools": {"cdscode", "cds"},
}
NO_REPLICATE = {"formula_1": {"seasons"}}


def is_int_key(col, ty):
    # 'Id', 'UserId', 'CustomerID', 'account_id' are keys; 'grid' (formula_1 results) is not.
    named_key = col.lower() == "id" or col.endswith("Id") or col.endswith("ID") or col.lower().endswith("_id")
    return ty.upper() in INT_TYPES and named_key and "type" not in col.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--sf", type=int, default=10)
    args = ap.parse_args()
    os.makedirs(SCALED_DIR, exist_ok=True)
    dst = f"{SCALED_DIR}/{args.db}_x{args.sf}.duckdb"
    tmp = dst + ".building"
    for p in (tmp, tmp + ".wal"):
        if os.path.exists(p):
            os.remove(p)
    t0 = time.time()
    con = duckdb.connect(tmp)
    con.execute("SET threads=8")
    con.execute(f"ATTACH '{db_path(args.db)}' AS src (READ_ONLY)")
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE database_name='src' AND schema_name='main' ORDER BY 1").fetchall()
        if r[0] not in SKIP_TABLES]
    cols = {t: con.execute("SELECT column_name, data_type FROM duckdb_columns() WHERE database_name='src' "
                           "AND schema_name='main' AND table_name=? ORDER BY column_index", [t]).fetchall()
            for t in tables}
    maxv = 1
    key_cols = []
    for t in tables:
        for c, ty in cols[t]:
            if is_int_key(c, ty):
                key_cols.append(f"{t}.{c}")
                lo, hi = con.execute(f"SELECT min({quote_ident(c)}), max({quote_ident(c)}) FROM src.{quote_ident(t)}").fetchone()
                for v in (lo, hi):
                    if v is not None:
                        maxv = max(maxv, abs(int(v)))
    off = 10 ** len(str(maxv))
    print(args.db, "sf", args.sf, "offset", off, "int key cols:", key_cols, flush=True)
    print("string key cols:", sorted(STR_KEYS.get(args.db, set())), "no-replicate:", sorted(NO_REPLICATE.get(args.db, set())))
    strk = STR_KEYS.get(args.db, set())
    for t in tables:
        qt = quote_ident(t)
        if t in NO_REPLICATE.get(args.db, set()):
            con.execute(f"CREATE TABLE {qt} AS SELECT * FROM src.{qt}")
        else:
            exprs = []
            for c, ty in cols[t]:
                qc = quote_ident(c)
                if is_int_key(c, ty):
                    exprs.append(f"CAST(s.{qc} AS BIGINT) + r.k * {off} AS {qc}")
                elif c.lower() in strk:
                    exprs.append(f"CASE WHEN r.k = 0 THEN s.{qc} ELSE s.{qc} || '~' || r.k END AS {qc}")
                else:
                    exprs.append(f"s.{qc}")
            con.execute(f"CREATE TABLE {qt} AS SELECT {', '.join(exprs)} FROM src.{qt} AS s "
                        f"CROSS JOIN range({args.sf}) AS r(k) ORDER BY r.k, s.rowid")
        n_src = con.execute(f"SELECT count(*) FROM src.{qt}").fetchone()[0]
        n_dst = con.execute(f"SELECT count(*) FROM {qt}").fetchone()[0]
        print(f"  {t}: {n_src} -> {n_dst}", flush=True)
    con.execute("DETACH src")
    con.execute("CHECKPOINT")
    con.close()
    os.replace(tmp, dst)
    print("built", dst, round(os.path.getsize(dst) / 1e9, 2), "GB in", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
