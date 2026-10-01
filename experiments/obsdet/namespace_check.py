"""Namespace facts behind the proof blind review's BR-01: can an unqualified catalog table name resolve to a relation
the catalog does not describe in our DuckDB deployment?
(1) Does a read-only DuckDB connection, opened as the agent tool opens it, accept DDL (temporary tables and views)?
(2) For every evaluated database: which relations named like each catalog table exist, in which catalog and schema?
(3) Which statements other than SELECT/WITH did agents send in the E4 traces, and did any of them succeed?
(4) Which statements of the certified statement sets the certifier rejected as not-select.
Usage: python namespace_check.py <catalog.json> <duck_dir> <out.json> <cert_*.jsonl files and trace dirs...>"""
import collections
import json
import re
import sys

import duckdb

PROBES = ("CREATE TEMP TABLE ns_probe AS SELECT 1 AS a", "CREATE TEMP VIEW ns_probe_v AS SELECT 1 AS a",
          "CREATE TABLE ns_probe2 AS SELECT 1 AS a", "CREATE SCHEMA ns_probe_s")


def first_word(sql):
    s = re.sub(r"(--[^\n]*\n)|(/\*.*?\*/)", " ", sql or "", flags=re.S).lstrip(" \t\n(")
    return (s.split(None, 1)[0] if s else "").upper()


def main(cat_path, duck_dir, out_path, *sources):
    cat = json.load(open(cat_path))
    out = {"ddl_on_read_only": {}, "search_path": None, "relations": {}, "agent_non_select": {}, "not_select": {}}
    con = duckdb.connect(f"{duck_dir}/{sorted(cat)[0]}.duckdb", read_only=True)
    out["search_path"] = con.execute("SELECT current_setting('search_path'), current_schemas(true)").fetchone()
    for stmt in PROBES:
        try:
            con.execute(stmt)
            out["ddl_on_read_only"][stmt] = "ACCEPTED"
        except Exception as e:  # noqa: BLE001
            out["ddl_on_read_only"][stmt] = f"rejected: {type(e).__name__}: {str(e)[:200]}"
    con.close()
    for db, tables in sorted(cat.items()):
        con = duckdb.connect(f"{duck_dir}/{db}.duckdb", read_only=True)
        rels = con.execute("SELECT database_name, schema_name, table_name, 'table' FROM duckdb_tables() UNION ALL "
                           "SELECT database_name, schema_name, view_name, 'view' FROM duckdb_views()").fetchall()
        con.close()
        byname = collections.defaultdict(list)
        for d, s, n, k in rels:
            byname[n.lower()].append(f"{d}.{s}.{n} ({k})")
        out["relations"][db] = {t: byname.get(t.lower(), []) for t in tables}
    for src in sources:
        path = src if src.endswith(".jsonl") else f"{src.rstrip('/')}/trace.jsonl"
        rows = [json.loads(line) for line in open(path)]
        name = src.rstrip("/").split("/")[-1]
        if src.endswith(".jsonl"):  # certificate file: statements the certifier rejected as not-select
            out["not_select"][name] = collections.Counter(
                first_word(r.get("sql")) for r in rows if str(r.get("reason", "")).startswith("not-select"))
            continue
        agg = collections.Counter()
        succeeded = []
        for r in rows:
            w = first_word(r.get("sql"))
            if r.get("sql") and w not in ("SELECT", "WITH"):
                agg[(w, bool(r.get("success")))] += 1
                if r.get("success"):
                    succeeded.append(r["sql"][:160])
        out["agent_non_select"][name] = {"counts": {f"{w}|{'ok' if ok else 'failed'}": n for (w, ok), n in agg.items()},
                                         "succeeded_examples": succeeded[:20]}
    json.dump(out, open(out_path, "w"), indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("ddl_on_read_only", "search_path")}, indent=1, default=str))
    dup = {db: {t: v for t, v in m.items() if len(v) != 1} for db, m in out["relations"].items()}
    print("catalog names not resolving to exactly one relation:", {db: v for db, v in dup.items() if v} or "none")
    print("agent non-SELECT statements:", json.dumps(out["agent_non_select"], indent=1)[:3000])
    print("not-select statements by first word:", json.dumps(out["not_select"], default=dict))


if __name__ == "__main__":
    main(*sys.argv[1:])
