"""The agent-facing SQL tool of the study: execute, report the exact row count, render values canonically.

Observation = header + first K rendered rows + exact row count (refine-logs/FINAL_PROPOSAL.md). The pilot helper
fetches at most 100,000 rows; when it truncates, the exact count is taken with a COUNT(*) over the same statement
on the same read-only instance. Floating-point signed zero is rendered as 0.0, so that SQL-equal values render
identically (-0.0 = 0.0 in SQL but str() distinguishes them).
"""
import os
import sys

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


def run(con, sql, timeout):
    """Execute on a private read-only instance (preview and count see the same data). A result that stays
    truncated (`exact_count` False) means the count query failed: an operational failure, reported separately."""
    r = execute_with_timeout(con, sql, timeout)
    r["exact_count"] = r["success"]
    if r["success"]:
        r["rows"] = [tuple(canon(v) for v in row) for row in r["rows"]]
        if r["truncated"]:
            c = execute_with_timeout(con, f"SELECT count(*) FROM ({sql.strip().rstrip(';')}) AS obs_count", timeout)
            if c["success"]:
                r["n_rows"], r["truncated"] = c["rows"][0][0], False
            else:
                r["exact_count"] = False
            r["runtime"] += c["runtime"]
    return r
