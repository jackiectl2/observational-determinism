"""Key catalog for the BIRD dev databases.

Declared primary keys come from BIRD's dev_tables.json (column indices into column_names_original);
each declared key is validated on the data (unique and non-null) and dropped if it does not hold.
Column types come from the DuckDB copies (which carry no constraints of their own).

Usage: python catalog.py <dev_tables.json> <duckdb_dir> <out.json>
"""
import json
import os
import sys

import duckdb


def qi(name):
    return '"' + name.replace('"', '""') + '"'


def build(tables_json, duckdb_dir):
    out = {}
    for db in json.load(open(tables_json)):
        path = os.path.join(duckdb_dir, f"{db['db_id']}.duckdb")
        if not os.path.exists(path):
            continue
        con = duckdb.connect(path, read_only=True)
        present = {r[0].lower(): r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()}
        tables = {}
        for tname, cname, ctype in con.execute(
                "select table_name, column_name, data_type from information_schema.columns order by table_name, ordinal_position").fetchall():
            tables.setdefault(tname, {"columns": {}, "keys": [], "declared_keys": [], "invalid_keys": []})
            tables[tname]["columns"][cname] = ctype
        cols = db["column_names_original"]  # [[table_idx, col_name], ...]; index 0 is [-1, "*"]
        tnames = db["table_names_original"]
        for pk in db["primary_keys"]:
            idx = pk if isinstance(pk, list) else [pk]
            t = tnames[cols[idx[0]][0]]
            key = [cols[i][1] for i in idx]
            t_actual = present.get(t.lower())
            if t_actual is None or any(c not in tables[t_actual]["columns"] for c in key):
                continue
            tables[t_actual]["declared_keys"].append(key)
            ksql = ", ".join(qi(c) for c in key)
            nn = " or ".join(f"{qi(c)} is null" for c in key)
            n, nd, nnull = con.execute(
                f"select count(*), (select count(*) from (select distinct {ksql} from {qi(t_actual)})), "
                f"count(*) filter (where {nn}) from {qi(t_actual)}").fetchone()
            (tables[t_actual]["keys"] if (n == nd and nnull == 0) else tables[t_actual]["invalid_keys"]).append(key)
        out[db["db_id"]] = tables
        con.close()
    return out


if __name__ == "__main__":
    cat = build(sys.argv[1], sys.argv[2])
    json.dump(cat, open(sys.argv[3], "w"), indent=1)
    for db, ts in cat.items():
        nk = sum(len(t["keys"]) for t in ts.values())
        nbad = sum(len(t["invalid_keys"]) for t in ts.values())
        nokey = [t for t, v in ts.items() if not v["keys"]]
        print(f"{db}: {len(ts)} tables, {nk} valid keys, {nbad} invalid declared keys, tables without key: {nokey}")
