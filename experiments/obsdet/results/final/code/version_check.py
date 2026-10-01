"""Recertify the development probes with the current certify.py and compare with stored certificates: the DuckDB
certificates of cert_probes_v6.jsonl and the PostgreSQL-dialect certificates recorded by replay_pg.py.

Usage: python version_check.py <catalog.json> <cert_probes.jsonl> <sound_pg.jsonl>
"""
import json
import sys
from collections import Counter

from certify import certify
from pg_cost import to_pg


def main(cat_path, cert_path, pg_path):
    cat = json.load(open(cat_path))
    catl = {d: {t.lower(): {"columns": {c.lower(): ty for c, ty in v["columns"].items()},
                            "keys": [[c.lower() for c in k] for k in v["keys"]]} for t, v in tabs.items()}
            for d, tabs in cat.items()}
    diff = Counter()
    for line in open(cert_path):
        p = json.loads(line)
        c = certify(p["sql"], cat[p["db_id"]], "duckdb")
        diff["duckdb_same" if (c.verdict, c.rewritten) == (p["verdict"], p["rewritten"]) else "duckdb_changed"] += 1
    for line in open(pg_path):
        r = json.loads(line)
        if "pg_sql" not in r:
            continue
        c = certify(r["pg_sql"], catl[r["db_id"]], "postgres")
        same = c.verdict == r["verdict"] and (c.rewritten or r["pg_sql"]) == r["policies"]["certified"]["sql"] \
            if c.verdict != "UNSUPPORTED" else c.verdict == r["verdict"]
        diff["postgres_same" if same else "postgres_changed"] += 1
    print(dict(diff))


if __name__ == "__main__":
    main(*sys.argv[1:4])
