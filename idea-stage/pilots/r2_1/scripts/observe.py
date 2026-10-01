# Observation operators for SQL tools used by data agents.
#   raw      : first k rows in whatever order the engine returns (the C3 agent harness rendering);
#   OBSERVE k: deterministic bounded observation -
#              (1) a top-level ORDER BY gets all output columns appended as positional tie-breakers
#                  (NULLS LAST), so ORDER BY ... LIMIT picks a deterministic prefix;
#              (2) a top-level LIMIT/OFFSET without ORDER BY gets ORDER BY 1..m (NULLS LAST), i.e. a
#                  deterministic subset;
#              (3) no top-level ORDER BY / LIMIT: the full result is ordered client-side by a stable hash of
#                  the canonical row (a deterministic pseudo-random sample for the first k rows);
#              floats are rendered with 10 significant digits in every case.
import os
import sys
import time
import zlib

import sqlglot
from sqlglot import exp

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from agent_c3 import observation as render_raw  # noqa: E402  (exact rendering the C3 agent saw)

DIALECT = "duckdb"
K = 20


def _flatten_top(ast):
    """Return the top-level query node that carries ORDER BY / LIMIT (Select or set operation)."""
    return ast


def top_info(sql):
    """Parse the statement and describe its top level."""
    info = {"parse_ok": False, "kind": "other", "has_order": False, "has_limit": False, "has_offset": False,
            "has_distinct": False, "has_group": False, "has_agg": False, "has_window": False,
            "limit_in_subquery": False, "n_out_static": None, "order_keys": [], "select_names": [],
            "select_sqls": []}
    try:
        asts = sqlglot.parse(sql, read=DIALECT)
    except Exception:
        return info, None
    asts = [a for a in asts if a is not None]
    if len(asts) != 1:
        return info, None
    ast = asts[0]
    info["parse_ok"] = True
    if isinstance(ast, exp.Select):
        info["kind"] = "select"
    elif isinstance(ast, (exp.Union, exp.Intersect, exp.Except)):
        info["kind"] = "setop"
    else:
        return info, ast
    info["has_order"] = ast.args.get("order") is not None
    info["has_limit"] = ast.args.get("limit") is not None
    info["has_offset"] = ast.args.get("offset") is not None
    if isinstance(ast, exp.Select):
        info["has_distinct"] = ast.args.get("distinct") is not None
        info["has_group"] = ast.args.get("group") is not None
        info["has_agg"] = any(isinstance(e.unalias() if isinstance(e, exp.Alias) else e, exp.AggFunc)
                              or any(isinstance(n, exp.AggFunc) for n in e.walk()) for e in ast.expressions)
        info["has_window"] = any(isinstance(n, exp.Window) for e in ast.expressions for n in e.walk())
        if not any(isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
                   for e in ast.expressions):
            info["n_out_static"] = len(ast.expressions)
        info["select_names"] = [e.alias_or_name for e in ast.expressions]
        info["select_sqls"] = [(e.this if isinstance(e, exp.Alias) else e).sql(dialect=DIALECT) for e in ast.expressions]
    for sub in ast.find_all(exp.Select):
        if sub is not ast and sub.args.get("limit") is not None:
            info["limit_in_subquery"] = True
    if info["has_order"]:
        info["order_keys"] = [o.this.sql(dialect=DIALECT) for o in ast.args["order"].expressions]
    return info, ast


def order_key_positions(info, ast):
    """Map top-level ORDER BY keys to output positions (0-based); None if any key is not an output column."""
    if not info["has_order"] or info["kind"] != "select":
        return None
    pos = []
    for o in ast.args["order"].expressions:
        t = o.this
        if isinstance(t, exp.Literal) and not t.is_string:
            pos.append(int(t.this) - 1)
            continue
        s = t.sql(dialect=DIALECT)
        if isinstance(t, exp.Column) and not t.table and t.name in info["select_names"]:
            pos.append(info["select_names"].index(t.name))
        elif s in info["select_sqls"]:
            pos.append(info["select_sqls"].index(s))
        elif isinstance(t, exp.Column) and t.name in info["select_names"]:
            pos.append(info["select_names"].index(t.name))
        else:
            return None
    return pos


def statement_type(info, ast, rows):
    """Mutually exclusive statement type used for the divergence split."""
    if not info["parse_ok"] or info["kind"] == "other":
        return "other"
    if info["has_order"]:
        pos = order_key_positions(info, ast)
        if pos is None or rows is None:
            return "order_by_unknown_ties"
        keys = [tuple(r[p] for p in pos) for r in rows]
        return "order_by_ties" if len(set(keys)) < len(keys) else "order_by_no_ties"
    if info["has_limit"] or info["has_offset"]:
        return "limit_no_order"
    if info["has_group"]:
        return "group_by"
    if info["has_distinct"]:
        return "distinct"
    if info["has_agg"]:
        return "aggregate_no_group"
    return "no_order_by"


def observe_rewrite(ast, n_out, write_dialect=DIALECT):
    """SQL rewrite part of OBSERVE. Returns (sql, needs_client_order)."""
    if ast is None:
        return None, True
    order = ast.args.get("order")
    has_lim = ast.args.get("limit") is not None or ast.args.get("offset") is not None
    if order is None and not has_lim:
        return ast.sql(dialect=write_dialect), True
    a2 = ast.copy()
    keys = [o.copy() for o in (order.expressions if order is not None else [])]
    tie = [exp.Ordered(this=exp.Literal.number(i), desc=False, nulls_first=False) for i in range(1, n_out + 1)]
    a2.set("order", exp.Order(expressions=keys + tie))
    return a2.sql(dialect=write_dialect), False


def fmt_float(v):
    return format(v, ".10g")


def canon_display(v):
    if isinstance(v, float):
        return fmt_float(v)
    return v


def stable_row_key(row):
    s = repr(tuple(fmt_float(v) if isinstance(v, float) else v for v in row))
    return (zlib.crc32(s.encode()), s)


def render_observe(res, k=K, client_order=True):
    """OBSERVE rendering: same text layout as the raw tool, canonical floats, deterministic row order."""
    if not res["success"]:
        return f"Error: {res['error'][:400]}"
    rows = res["rows"]
    if client_order:
        rows = sorted(rows, key=stable_row_key)
    rows = [tuple(canon_display(v) for v in r) for r in rows]
    shown = dict(res)
    shown["rows"] = rows
    return render_raw(shown, k)


def open_instance(path, threads, memory_limit="8GB"):
    """A private in-memory DuckDB instance holding a copy of the database file (insertion order preserved).
    duckdb.connect(path) would share one instance (and one global `threads` setting) per file per process."""
    import duckdb
    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"ATTACH '{path}' AS src (READ_ONLY)")
    con.execute("COPY FROM DATABASE src TO memory")
    con.execute("DETACH src")
    con.execute("USE memory")
    con.execute(f"SET threads={threads}")
    con.execute("SET enable_external_access=false")
    return con


def n_out_probe(con_execute, sql):
    """Number of output columns via a LIMIT 0 wrapper (DuckDB / SQLite)."""
    q = sql.strip().rstrip(";")
    cur = con_execute(f"SELECT * FROM ({q}) AS __obs LIMIT 0")
    return len(cur.description)


# ---------------------------------------------------------------------------------------------------------
# Engine-neutral variants used for the step-1 measurements (the greedy agent run imported the functions
# above; within DuckDB both key functions order identically because value types are identical).
# ---------------------------------------------------------------------------------------------------------

def canon_value(v):
    """Type-insensitive canonical text of a value (so DuckDB and SQLite values compare equal)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    try:
        import decimal
        if isinstance(v, decimal.Decimal):
            v = float(v)
    except Exception:
        pass
    if isinstance(v, float):
        if v != v:
            return "nan"
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return format(v, ".10g")
    return str(v)


def canon_key(row):
    s = repr(tuple(canon_value(v) for v in row))
    return (zlib.crc32(s.encode()), s)


def canon_sig(rows, n_rows, truncated, k=K):
    """Header-free, type-insensitive signature of what the agent sees: first k rows (in the order shown) + count."""
    import hashlib
    body = repr((n_rows, bool(truncated), [tuple(canon_value(v) for v in r) for r in rows[:k]]))
    return hashlib.sha1(body.encode()).hexdigest()


def observe_rewrite_lex(ast, n_out, write_dialect=DIALECT):
    """OBSERVE-lex: engine-side total order for every SELECT/set operation: existing keys + ORDER BY 1..m."""
    if ast is None:
        return None
    a2 = ast.copy()
    order = a2.args.get("order")
    keys = [o.copy() for o in (order.expressions if order is not None else [])]
    tie = [exp.Ordered(this=exp.Literal.number(i), desc=False, nulls_first=False) for i in range(1, n_out + 1)]
    a2.set("order", exp.Order(expressions=keys + tie))
    return a2.sql(dialect=write_dialect)


def shown_rows(res, mode):
    """Rows in the order the tool shows them. mode: raw | hash (client-side canonical hash) | lex (engine order)."""
    if not res["success"]:
        return []
    if mode == "hash":
        return sorted(res["rows"], key=canon_key)
    return list(res["rows"])


def render_rows(res, rows, k=K):
    if not res["success"]:
        return f"Error: {res['error'][:400]}"
    shown = dict(res)
    shown["rows"] = [tuple("NULL" if v is None else canon_value(v) for v in r) for r in rows]
    return render_raw(shown, k)


# ---------------------------------------------------------------------------------------------------------
# OBSERVE v2 ("canonical OBSERVE", DuckDB): deterministic over the COMPLETE logical result.
#   * top-level ORDER BY and/or LIMIT/OFFSET: the statement gets a total order (its keys, then every output
#     column, NULLS LAST) and is executed as is; its first k rows are then a function of the logical result.
#   * otherwise: the statement is wrapped and DuckDB returns the k rows with the smallest canonical-row hash
#     plus the exact row count, computed over the full result (no client-side fetch cap involved):
#       SELECT c0..cm-1, count(*) OVER () FROM (<q>) AS __obs(c0..cm-1)
#       ORDER BY hash(canon(c0), ..., canon(cm-1)), c0, ..., cm-1 LIMIT k
#     canonical encoding: DOUBLE/FLOAT/REAL values -> format('{:.10g}', v) (10 significant digits, removes
#     summation-order noise); every other type hashed by value (DuckDB hash is value-based and seed-free);
#     NULL hashes to a fixed value and sorts last; exact duplicate rows are indistinguishable when displayed.
#   * statements that sqlglot cannot parse, or non-query commands, are executed unchanged.
# Display: header = the statement's own column names; values rendered with canon_value (floats 10 significant
# digits, integral floats as integers, NULL as "NULL").
# ---------------------------------------------------------------------------------------------------------
FLOAT_TYPES = {"DOUBLE", "FLOAT", "REAL", "FLOAT8", "FLOAT4"}


def describe(con, sql):
    """Output columns and types, bound but not executed. Uses its own cursor: a DuckDB connection object is not
    safe to share between threads (a shared con.execute returned another statement's DESCRIBE in testing)."""
    q = sql.strip().rstrip(";")
    cur = con.cursor()
    try:
        return [(r[0], str(r[1])) for r in cur.execute(f"DESCRIBE {q}").fetchall()]
    finally:
        cur.close()


def canon_hash_sql(sql, cols, k=K):
    q = sql.strip().rstrip(";")
    names = [f"c{i}" for i in range(len(cols))]
    canon = [f"format('{{:.10g}}', {n})" if t.upper() in FLOAT_TYPES else n for n, (_, t) in zip(names, cols)]
    return (f"SELECT {', '.join(names)}, count(*) OVER () AS __obs_n FROM ({q}) AS __obs({', '.join(names)}) "
            f"ORDER BY hash({', '.join(canon)}), {', '.join(names)} LIMIT {k}")


def observe_v2(con, sql, execute, k=K):
    """execute(con, sql) -> result dict (common.execute_with_timeout signature).
    Returns (result, shown_rows, text, meta); result['n_rows'] is the exact row count on the hash path."""
    import time as _t
    t0 = _t.perf_counter()
    info, ast = top_info(sql)
    meta = {"path": "unchanged", "fallback": False, "exec_sql": None}
    res = None
    if info["parse_ok"] and info["kind"] in ("select", "setop"):
        try:
            if info["has_order"] or info["has_limit"] or info["has_offset"]:
                n_out = info["n_out_static"] if info["n_out_static"] is not None else len(describe(con, sql))
                exec_sql, _ = observe_rewrite(ast, n_out)
                r = execute(con, exec_sql)
                if not r["success"]:
                    meta["error"] = (r["error"] or "")[:200]
                if r["success"]:
                    res, meta["path"], meta["exec_sql"] = r, "total_order", exec_sql
            else:
                cols = describe(con, sql)
                exec_sql = canon_hash_sql(sql, cols, k)
                r = execute(con, exec_sql)
                if not r["success"]:
                    meta["error"] = (r["error"] or "")[:200]
                if r["success"]:
                    n_total = r["rows"][0][-1] if r["rows"] else 0
                    res = dict(r)
                    res["rows"] = [tuple(row[:-1]) for row in r["rows"]]
                    res["columns"] = [c for c, _ in cols]
                    res["n_rows"] = n_total
                    res["truncated"] = False
                    meta["path"], meta["exec_sql"] = "canonical_hash", exec_sql
        except Exception as e:  # rewrite could not be built (e.g. DESCRIBE failed): run unchanged
            meta["error"] = str(e)[:200]
        if res is None:
            meta["fallback"] = True
    if res is None:
        res = execute(con, sql)
    t1 = _t.perf_counter()
    shown = list(res["rows"]) if res["success"] else []
    text = render_rows(res, shown, k)
    meta["engine_s"] = t1 - t0
    meta["client_s"] = _t.perf_counter() - t1
    return res, shown, text, meta


# ---------------------------------------------------------------------------------------------------------
# OBSERVE v3 (same observation semantics as v2 on complete results, cheaper): no extra database round trip
# on the common path.
#   * top-level ORDER BY / LIMIT / OFFSET: total-order rewrite; the column count comes from sqlglot (star
#     expanded with the schema) instead of a DESCRIBE probe;
#   * otherwise: the statement runs unchanged (exactly the raw tool's execution and fetch), and the k rows with
#     the smallest canonical-row hash are selected client-side. Canonical row: floats rounded to 10 significant
#     digits, integral floats -> int, NULL -> None, other values as returned; key = Python tuple hash, made
#     process-independent by PYTHONHASHSEED=0 (checked below);
#   * if the fetched result is truncated (more than the tool's 100,000-row cap), the selection falls back to
#     v2 (engine-side, over the complete result), so the prefix never depends on physical order.
# ---------------------------------------------------------------------------------------------------------
import math as _math
import os as _os


def _canon_fast(v):
    if isinstance(v, list):
        return tuple(_canon_fast(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((str(a), _canon_fast(b)) for a, b in v.items()))
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")) or v == 0.0:
            return v
        r = round(v, 9 - int(_math.floor(_math.log10(abs(v)))))
        return int(r) if r.is_integer() and abs(r) < 1e15 else r
    return v


def fast_key(row):
    return hash(tuple(_canon_fast(v) for v in row))


def n_out_static_schema(ast, schema_lc):
    """Output column count with SELECT * expanded via sqlglot qualification (None if not derivable)."""
    try:
        from sqlglot.optimizer.qualify import qualify
        q = qualify(ast.copy(), dialect=DIALECT, schema=schema_lc, validate_qualify_columns=False,
                    quote_identifiers=False, identify=False)
        sel = q if isinstance(q, exp.Select) else q.find(exp.Select)
        if sel is None or any(isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
                              for e in sel.expressions):
            return None
        return len(sel.expressions)
    except Exception:
        return None


def observe_v3(con, sql, execute, schema_lc, k=K):
    import heapq
    import time as _t
    assert _os.environ.get("PYTHONHASHSEED") == "0", "OBSERVE v3 needs PYTHONHASHSEED=0 for a stable key"
    t0 = _t.perf_counter()
    info, ast = top_info(sql)
    meta = {"path": "unchanged", "fallback": False, "exec_sql": None}
    res = None
    shown = None
    if info["parse_ok"] and info["kind"] in ("select", "setop"):
        if info["has_order"] or info["has_limit"] or info["has_offset"]:
            try:
                n_out = info["n_out_static"]
                if n_out is None:
                    n_out = n_out_static_schema(ast, schema_lc)
                    meta["probe"] = n_out is None
                if n_out is None:
                    n_out = len(describe(con, sql))
                exec_sql, _ = observe_rewrite(ast, n_out)
                r = execute(con, exec_sql)
                if r["success"]:
                    res, shown, meta["path"], meta["exec_sql"] = r, list(r["rows"]), "total_order", exec_sql
                else:
                    meta["error"] = (r["error"] or "")[:200]
            except Exception as e:
                meta["error"] = str(e)[:200]
            if res is None:
                meta["fallback"] = True
        else:
            r = execute(con, sql)
            if r["success"] and r["truncated"]:
                res, shown, text, m2 = observe_v2(con, sql, execute, k)
                meta.update(path="v2_complete_result", exec_sql=m2.get("exec_sql"))
            elif r["success"]:
                res = r
                rows = r["rows"]
                if len(rows) > 1:
                    # 64-bit keys: distinct rows with equal keys (a collision) are the only case where input order
                    # could matter; the selected rows are re-sorted with repr as a tie-breaker.
                    shown = heapq.nsmallest(k, rows, key=fast_key)
                    shown.sort(key=lambda row: (fast_key(row), repr(row)))
                else:
                    shown = list(rows)
                meta["path"] = "client_hash"
            else:
                res = r
    if res is None:
        res = execute(con, sql)
        shown = list(res["rows"]) if res["success"] else []
    t1 = _t.perf_counter()
    text = render_rows(res, shown, k)
    meta["engine_s"] = t1 - t0
    meta["client_s"] = _t.perf_counter() - t1
    return res, shown, text, meta


# ---------------------------------------------------------------------------------------------------------
# OBSERVE v4 (lowest-overhead emulation): no SQL parser on the common path.
#   * a character scanner removes comments, quoted text and parenthesised groups; if the remaining top level
#     has no ORDER BY / LIMIT / OFFSET, the statement is executed once as
#         SELECT *, hash(__q) AS __obs_h FROM (\n<q>\n) AS __q
#     (DuckDB computes a value-based hash of the whole output row), all rows are fetched exactly as the raw
#     tool does, and the k rows with the smallest hash are shown (ties: repr of the row);
#   * results above the fetch cap fall back to v2 (engine-side selection over the complete result);
#   * top-level ORDER BY / LIMIT / OFFSET: v3 path (sqlglot + total-order rewrite);
#   * canonical encoding: the row hash is DuckDB's hash of the row struct (types as produced; floats NOT
#     rounded before hashing - summation-order noise in a float column can still change the selection);
#     display as in render_rows (floats 10 significant digits).
# ---------------------------------------------------------------------------------------------------------
import re as _re

_TOP_KW = _re.compile(r"\b(order\s+by|limit|offset)\b", _re.I)
_QUERY_START = _re.compile(r"^\s*(select|with|from|values|\()", _re.I)


def top_level_text(sql):
    out, depth, i, n = [], 0, 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    break
                j += 1
            i = j + 1
            out.append(" ")
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            continue
        if sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
        i += 1
    return "".join(out)


def _strip_leading_comments(sql):
    s = sql.lstrip()
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            j = s.find("\n")
            s = "" if j < 0 else s[j + 1:].lstrip()
        else:
            j = s.find("*/")
            s = "" if j < 0 else s[j + 2:].lstrip()
    return s


def observe_v4(con, sql, execute, schema_lc, k=K):
    import heapq
    import time as _t
    t0 = _t.perf_counter()
    meta = {"path": "unchanged", "fallback": False}
    top = top_level_text(sql)
    if not _QUERY_START.match(_strip_leading_comments(sql)) or ";" in top.strip().rstrip(";"):
        res = execute(con, sql)  # commands / multi-statement text: unchanged
        shown = list(res["rows"]) if res["success"] else []
    elif _TOP_KW.search(top):
        res, shown, _, m3 = observe_v3(con, sql, execute, schema_lc, k)
        meta.update(path="v3_" + m3["path"], fallback=m3["fallback"])
    else:
        q = sql.strip().rstrip(";")
        r = execute(con, f"SELECT *, hash(__q) AS __obs_h FROM (\n{q}\n) AS __q")
        if r["success"] and r["truncated"]:
            res, shown, _, _ = observe_v2(con, sql, execute, k)
            meta["path"] = "v2_complete_result"
        elif r["success"]:
            rows = r["rows"]
            sel = heapq.nsmallest(k, rows, key=lambda row: row[-1]) if len(rows) > k else list(rows)
            sel.sort(key=lambda row: (row[-1], repr(row)))
            res = dict(r)
            res["columns"] = r["columns"][:-1]
            res["rows"] = [tuple(row[:-1]) for row in rows]  # full result (for checks); display uses `shown`
            shown = [tuple(row[:-1]) for row in sel]
            meta["path"] = "engine_hash"
        else:
            res = execute(con, sql)
            shown = list(res["rows"]) if res["success"] else []
            meta["fallback"] = res["success"]
    t1 = _t.perf_counter()
    text = render_rows(res, shown, k)
    meta["engine_s"] = t1 - t0
    meta["client_s"] = _t.perf_counter() - t1
    return res, shown, text, meta
