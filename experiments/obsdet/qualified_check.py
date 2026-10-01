"""Schema-qualified table names: does a certifier apply the catalog's keys to a table in another schema?

The catalog describes one schema by bare table names. A statement that names `evil.t` reads a different table than
the catalog's `t`, so the catalog's key on `t` says nothing about it; a certifier must not return DET or a tie-break
based on that key. Runs each statement in both dialects on the old and the new certifier and checks the new one.
Usage: python qualified_check.py <old_certify.py> <new_certify.py> <out.json>"""
import importlib.util
import json
import sys

CATALOG = {"t": {"columns": {"id": "INTEGER", "x": "INTEGER"}, "keys": [["id"]]}}
DOTTED = {"s.t": {"columns": {"id": "INTEGER", "x": "INTEGER"}, "keys": [["id"]]}}  # a table named "s.t"
# (sql, dialects, expected verdict of the new certifier)
CASES = [
    ("SELECT x FROM t ORDER BY id LIMIT 1", ("duckdb", "postgres"), "DET"),
    ("SELECT x FROM evil.t ORDER BY id LIMIT 1", ("duckdb", "postgres"), "UNSUPPORTED"),
    ("SELECT x FROM main.t ORDER BY id LIMIT 1", ("duckdb",), "UNSUPPORTED"),
    ("SELECT x FROM public.t ORDER BY id LIMIT 1", ("postgres",), "UNSUPPORTED"),
    ("SELECT x FROM other.evil.t ORDER BY id LIMIT 1", ("duckdb",), "UNSUPPORTED"),
    ("SELECT a.x FROM evil.t AS a JOIN t AS b ON a.id = b.id ORDER BY a.id LIMIT 1", ("duckdb", "postgres"), "UNSUPPORTED"),
    ("SELECT x FROM t WHERE id IN (SELECT id FROM evil.t) ORDER BY id LIMIT 1", ("duckdb", "postgres"), "UNSUPPORTED"),
]
# a catalog table literally named "s.t" must not match the qualified reference s.t (table t in schema s)
DOTTED_CASES = [("SELECT x FROM s.t ORDER BY id LIMIT 1", ("duckdb", "postgres"), "UNSUPPORTED")]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(old_path, new_path, out_path):
    old, new = load("c_old", old_path), load("c_new", new_path)
    rows, failures = [], 0
    for sql, dialects, expected, cat in [c + (CATALOG,) for c in CASES] + [c + (DOTTED,) for c in DOTTED_CASES]:
        for dialect in dialects:
            a, b = old.certify(sql, cat, dialect), new.certify(sql, cat, dialect)
            ok = b.verdict == expected
            failures += not ok
            rows.append({"sql": sql, "dialect": dialect, "old": [a.verdict, a.reason, a.tie_break],
                         "new": [b.verdict, b.reason, b.tie_break], "expected_new": expected, "ok": ok})
            print(f"{'OK ' if ok else 'BAD'} {dialect:8s} old={a.verdict}/{a.reason} new={b.verdict}/{b.reason} | {sql}")
    json.dump({"cases": rows, "failures": failures}, open(out_path, "w"), indent=1)
    print("failures", failures)


if __name__ == "__main__":
    main(*sys.argv[1:])
