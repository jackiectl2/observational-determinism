# Shared helpers for pilot C3: paths, DuckDB execution with timeout, schema text, result hashing.
import hashlib
import json
import math
import os
import threading
import time

import duckdb

VLDB27 = os.environ["PROJECT_ROOT"]
DATA = f"{VLDB27}/data"
DEV_JSON = f"{DATA}/bird_dev/data/dev_20251106-00000-of-00001.json"
DB_DIR = f"{DATA}/bird_duckdb/validation"
SCALED_DIR = f"{DATA}/pilot_c3_scaled"
RUNS = f"{VLDB27}/runs/pilot_c3"

SKIP_TABLES = {"sqlite_sequence"}


def db_path(db_id):
    return f"{DB_DIR}/{db_id}.duckdb"


def open_db(path, threads=4, memory_limit="8GB"):
    con = duckdb.connect(path, read_only=True)
    con.execute(f"SET threads={threads}")
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute("SET enable_external_access=false")
    return con


def quote_ident(name):
    if name.replace("_", "a").isalnum() and not name[0].isdigit():
        return name
    return '"' + name.replace('"', '""') + '"'


def list_tables(con):
    rows = con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE schema_name='main' ORDER BY table_name").fetchall()
    return [r[0] for r in rows if r[0] not in SKIP_TABLES]


def table_columns(con, table):
    rows = con.execute(
        "SELECT column_name, data_type FROM duckdb_columns() WHERE schema_name='main' AND table_name=? "
        "ORDER BY column_index", [table]).fetchall()
    return [(r[0], r[1]) for r in rows]


def schema_dict(con):
    """{table: {column: type}} for sqlglot qualification."""
    return {t: {c: ty for c, ty in table_columns(con, t)} for t in list_tables(con)}


def schema_text(con):
    lines = []
    for t in list_tables(con):
        cols = ", ".join(f"{quote_ident(c)} {ty}" for c, ty in table_columns(con, t))
        lines.append(f"CREATE TABLE {quote_ident(t)} ({cols});")
    return "\n".join(lines)


def _canon_cell(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    try:
        import decimal
        if isinstance(v, decimal.Decimal):
            v = float(v)
    except Exception:
        pass
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        v = round(v, 4)
        return int(v) if v.is_integer() else v  # 3.0 and 3 (e.g. SUM vs COUNT) canonicalize equally
    return str(v)


def canon_rows(rows):
    """Canonical row tuples (floats rounded) for set/bag comparison."""
    return [tuple(_canon_cell(v) for v in r) for r in rows]


def bag_hash(rows):
    """Order-insensitive multiset hash of canonical rows."""
    items = sorted(json.dumps(r, default=str) for r in canon_rows(rows))
    return hashlib.sha1("\n".join(items).encode()).hexdigest()


def set_of(rows):
    return set(canon_rows(rows))


def execute_with_timeout(con, sql, timeout_s=20.0, row_cap=100000):
    """Run sql on a fresh cursor of con. Returns dict with success, error, rows (<= row_cap), columns, n_rows, truncated, runtime."""
    cur = con.cursor()
    timer = threading.Timer(timeout_s, cur.interrupt)
    t0 = time.perf_counter()
    timer.start()
    out = {"success": False, "error": None, "rows": [], "columns": [], "n_rows": 0, "truncated": False,
           "timeout": False}
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(row_cap + 1)
        truncated = len(rows) > row_cap
        rows = rows[:row_cap]
        out.update(success=True, rows=rows, columns=cols, n_rows=len(rows), truncated=truncated)
    except Exception as e:  # DuckDB raises many exception types; record message
        msg = str(e)
        out["error"] = msg[:500]
        out["timeout"] = "INTERRUPT" in msg.upper()
    finally:
        timer.cancel()
        out["runtime"] = time.perf_counter() - t0
        try:
            cur.close()
        except Exception:
            pass
    return out
