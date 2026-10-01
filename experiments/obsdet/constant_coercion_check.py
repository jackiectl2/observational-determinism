"""Does col = numeric literal pin col in DuckDB (proof blind review 2, BR-01)? The certifier treats an INT/DECIMAL column
compared with an INT/DECIMAL literal as a constant. If DuckDB compares in DOUBLE when the exact common decimal would
need more than 38 digits, two distinct stored values can both equal the literal. For each case: rows DuckDB returns,
the comparison it plans, and the verdicts of the given certifiers.
Usage: python constant_coercion_check.py <out.json> <certify.py> [<certify.py> ...]"""
import importlib.util
import json
import sys

import duckdb

CASES = [  # (column type, stored values, literal)
    ("DECIMAL(38,20)", ["1.00000000000000000000", "1.00000000000000000001"], "1.0000000000000000000000000000000000000"),
    ("DECIMAL(38,20)", ["1.00000000000000000000", "1.00000000000000000001"], "1.00000000000000000000"),
    ("DECIMAL(38,20)", ["10000000000.00000000000000000000", "10000000000.00000000000000000001"], "10000000000"),
    ("BIGINT", ["9007199254740992", "9007199254740993"], "9007199254740992.0000000000000000000000"),
    ("BIGINT", ["9007199254740992", "9007199254740993"], "9007199254740992.5"),
    ("BIGINT", ["9007199254740992", "9007199254740993"], "9007199254740992"),
    ("HUGEINT", ["9007199254740992", "9007199254740993"], "9007199254740992.0"),
    ("DECIMAL(18,3)", ["1.000", "1.001"], "1.0000000000000000000000000000000000000"),
    ("INTEGER", ["1", "2"], "1.00000000000000000000000000000000000"),
    # literals that the column's scale cannot represent: an exact comparison matches nothing, a DOUBLE one both rows
    ("DECIMAL(38,20)", ["1.00000000000000000000", "1.00000000000000000001"], "1.0000000000000000000000000000000000001"),
    ("DECIMAL(38,20)", ["1.00000000000000000000", "1.00000000000000000001"], "1.00000000000000000000000000000000000001"),
    ("BIGINT", ["9007199254740992", "9007199254740993"], "9007199254740993.0000000000000000000001"),
]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(out_path, *certifiers):
    mods = [load(p, f"c{i}") for i, p in enumerate(certifiers)]
    rows = []
    for ty, vals, lit in CASES:
        con = duckdb.connect()
        con.execute(f"CREATE TABLE t(x {ty})")
        con.execute("INSERT INTO t VALUES " + ", ".join(f"(CAST('{v}' AS {ty}))" for v in vals))
        q = f"SELECT x FROM t WHERE x = {lit}"
        got = [str(r[0]) for r in con.execute(q).fetchall()]
        plan = " ".join(r[1] for r in con.execute("EXPLAIN " + q).fetchall())
        filt = [ln.strip() for ln in plan.splitlines() if "=" in ln and "x" in ln][:2]
        catalog = {"t": {"columns": {"x": ty}, "keys": []}}
        verdicts = {p: [m.certify(q, catalog, "duckdb").verdict, m.certify(q, catalog, "duckdb").reason]
                    for p, m in zip(certifiers, mods)}
        pg = {p: m.certify(q, catalog, "postgres").verdict for p, m in zip(certifiers, mods)}
        row = {"type": ty, "values": vals, "literal": lit, "rows": got, "filter": filt, "duckdb_verdicts": verdicts,
               "postgres_verdicts": pg, "lossy": len(got) > 1}
        # a tie-break (NARROW/ALL) orders the qualifying rows; only DET claims that they need none
        row["unsound"] = {p: row["lossy"] and v[0] == "DET" for p, v in verdicts.items()}
        rows.append(row)
        print(json.dumps(row))
    json.dump(rows, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
