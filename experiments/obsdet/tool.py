"""The agent-facing SQL tool of the study: execute, report the exact row count, render values canonically.

Observation = header + first K rendered rows + exact row count (refine-logs/FINAL_PROPOSAL.md). The pilot helper
fetches at most 100,000 rows; when it truncates, the exact count is taken with a COUNT(*) over the same statement
on the same read-only instance. Floating-point signed zero is rendered as 0.0, so that SQL-equal values render
identically (-0.0 = 0.0 in SQL but str() distinguishes them).
"""
import os
import sys

import duckdb

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import execute_with_timeout  # noqa: E402


def canon(v):
    """Canonical value for rendering: signed zero -> 0.0, recursively inside lists, tuples and structs."""
    if isinstance(v, float):
        return 0.0 if v == 0.0 else v
    if isinstance(v, (list, tuple)):
        return type(v)(canon(x) for x in v)
    if isinstance(v, dict):
        return {k: canon(x) for k, x in v.items()}
    return v


def is_query(con, sql):
    """True unless DuckDB parses sql into a statement other than a query (its SELECT type also covers DESCRIBE, SHOW and
    PRAGMA table_info). The instance is a writable in-memory copy and SET reaches every later cursor, so a CREATE,
    INSERT or SET could change the tables, keys or settings that later certificates rely on."""
    try:
        return all(s.type == duckdb.StatementType.SELECT for s in con.extract_statements(sql))
    except duckdb.Error:  # the engine rejects the statement with its own error
        return True


def run(con, sql, timeout):
    """Execute on a private instance (preview and count see the same data); statements other than queries are refused,
    so no call changes the database or the session. If the exact count of a long result fails, the call fails."""
    if not is_query(con, sql):
        return {"success": False, "rows": [], "columns": [], "n_rows": 0, "truncated": False, "timeout": False,
                "runtime": 0.0, "exact_count": False,
                "error": "Not executed: this tool runs only queries (SELECT, DESCRIBE, SHOW); it does not change the "
                         "database or the session."}
    r = execute_with_timeout(con, sql, timeout)
    r["exact_count"] = r["success"]
    if r["success"]:
        r["rows"] = [tuple(canon(v) for v in row) for row in r["rows"]]
        if r["truncated"]:
            # newlines: a trailing line comment in sql must not swallow the closing parenthesis
            c = execute_with_timeout(con, f"SELECT count(*) FROM (\n{sql.strip().rstrip(';')}\n) AS obs_count", timeout)
            if c["success"]:
                r["n_rows"], r["truncated"] = c["rows"][0][0], False
            else:  # without the exact count the observation is not the contract's, so the call fails
                r.update(success=False, rows=[], columns=[], n_rows=0, exact_count=False,
                         error=f"Could not count the rows of the result: {c['error']}")
            r["runtime"] += c["runtime"]
    return r
