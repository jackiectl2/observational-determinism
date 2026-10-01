"""Facts for making the DuckDB tool read-only (proof blind review BR-01). The E4 tool instance is a writable in-memory
copy of the database (observe.open_instance), so an agent statement could change a table or a setting that later
certificates rely on. Reports (1) DuckDB's statement type for probe statements, (2) whether settings changed on one
cursor reach the next, and (3) the statement types of every statement the agents sent in the E4 traces.
Usage: python statement_types_check.py <db_file> <out.json> <trace dirs...>"""
import collections
import json
import os
import re
import sys

import duckdb

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_r2_1")
from observe import open_instance  # noqa: E402

PROBES = ["SELECT 1", "WITH x AS (SELECT 1) SELECT * FROM x", "FROM users LIMIT 1", "VALUES (1)", "TABLE users",
          "DESCRIBE users", "SHOW TABLES", "SHOW users", "SUMMARIZE users", "EXPLAIN SELECT 1",
          "PRAGMA table_info(users)", "PRAGMA show_tables", "PRAGMA enable_profiling",
          "PRAGMA default_null_order='nulls_first'", "SET default_null_order='nulls_first'",
          "SET default_collation='nocase'", "CALL pragma_table_info('users')", "CREATE TABLE t2 AS SELECT 1",
          "CREATE TEMP TABLE t3 AS SELECT 1", "CREATE SCHEMA s2", "INSERT INTO users SELECT * FROM users LIMIT 1",
          "ATTACH ':memory:' AS m", "USE memory", "-- just a comment", "FINAL ANSWER: 42", "SELECT 1; SELECT 2"]


def types(con, sql):
    try:
        return [s.type.name for s in con.extract_statements(sql)]
    except duckdb.Error as e:
        return [f"PARSE_ERROR: {str(e)[:80]}"]


def pragma_name(sql):
    m = re.match(r"\s*pragma\s+(\w+)", sql, re.I)
    return m.group(1).lower() if m else None


def main(db_file, out_path, *trace_dirs):
    con = open_instance(db_file, 1)
    out = {"probes": {p: types(con, p) for p in PROBES}, "leak": {}, "agents": {}}
    for s, check in (("SET default_null_order='nulls_first'", "default_null_order"),
                     ("SET default_collation='nocase'", "default_collation"),
                     ("PRAGMA default_null_order='nulls_first'", "default_null_order")):
        c1 = con.cursor()
        before = con.cursor().execute(f"SELECT current_setting('{check}')").fetchone()[0]
        try:
            c1.execute(s)
            err = None
        except duckdb.Error as e:
            err = str(e)[:120]
        c1.close()
        after = con.cursor().execute(f"SELECT current_setting('{check}')").fetchone()[0]
        out["leak"][s] = {"before": before, "after_on_new_cursor": after, "error": err}
        con.execute(f"RESET {check}")
    agg, pragmas, other = collections.Counter(), collections.Counter(), collections.Counter()
    for d in trace_dirs:
        for line in open(f"{d.rstrip('/')}/trace.jsonl"):
            r = json.loads(line)
            if not r.get("sql"):
                continue
            ts = types(con, r["sql"])
            for t in ts:
                agg[t.split(":")[0]] += 1
            if "PRAGMA" in ts:
                pragmas[pragma_name(r["sql"])] += 1
            if any(t not in ("SELECT", "PRAGMA") and not t.startswith("PARSE_ERROR") for t in ts) or not ts:
                other[(tuple(ts), r["sql"][:80], bool(r.get("success")))] += 1
    out["agents"] = {"types": dict(agg), "pragma_names": dict(pragmas),
                     "other": [{"types": list(k[0]), "sql": k[1], "success": k[2], "n": n} for k, n in other.items()]}
    json.dump(out, open(out_path, "w"), indent=1)
    print(json.dumps(out, indent=1)[:6000])


if __name__ == "__main__":
    main(*sys.argv[1:])
