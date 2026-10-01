"""Online cost of certification: static analysis time per statement, and the one-time key validation per database.

Per development probe, the median of `reps` timings of
  - certify() in the DuckDB dialect (the statement as issued),
  - certify() in the PostgreSQL dialect (the transpiled statement recorded by replay_pg.py),
  - smartlex(), the baseline's rewrite,
all of which read only the catalog. Key validation runs catalog.py's check (row count, distinct keys, null keys) for
every declared key on the SF1 DuckDB files, once per database.

Usage: python time_certify.py <catalog.json> <cert_probes.jsonl> <sound_pg.jsonl> <duckdb_dir> <out.json> [reps]
"""
import hashlib
import json
import os
import statistics
import sys
import time

import duckdb

from certify import certify, smartlex


def qi(name):
    return '"' + name.replace('"', '""') + '"'


def med_ms(fn, reps):
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return 1000 * statistics.median(ts)


def summary(xs):
    xs = sorted(xs)
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]  # noqa: E731
    return {"n": len(xs), "median_ms": round(statistics.median(xs), 3), "p90_ms": round(q(0.90), 3),
            "p99_ms": round(q(0.99), 3), "max_ms": round(xs[-1], 3), "mean_ms": round(statistics.mean(xs), 3)}


def main(cat_path, cert_path, pg_path, duck_dir, out_path, reps=5):
    reps = int(reps)
    cat = json.load(open(cat_path))
    catl = {d: {t.lower(): {"columns": {c.lower(): ty for c, ty in v["columns"].items()},
                            "keys": [[c.lower() for c in k] for k in v["keys"]]} for t, v in tabs.items()}
            for d, tabs in cat.items()}
    probes = [json.loads(line) for line in open(cert_path)]
    pg = {(r["db_id"], r["sql"]): r.get("pg_sql") for r in map(json.loads, open(pg_path))}
    rows = []
    for p in probes:
        db, sql = p["db_id"], p["sql"]
        r = {"db_id": db, "sql": sql, "verdict": p["verdict"]}
        r["duckdb_ms"] = med_ms(lambda: certify(sql, cat[db], "duckdb"), reps)
        if p.get("n_out"):
            r["smartlex_ms"] = med_ms(lambda: smartlex(sql, p["n_out"]), reps)
        pg_sql = pg.get((db, sql))
        if pg_sql:
            r["postgres_ms"] = med_ms(lambda: certify(pg_sql, catl[db], "postgres"), reps)
        rows.append(r)
    out = {"certify_md5": hashlib.md5(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "certify.py"),
                                           "rb").read()).hexdigest(),
           "reps": reps, "n_probes": len(rows)}
    for k in ("duckdb_ms", "postgres_ms", "smartlex_ms"):
        out[k] = summary([r[k] for r in rows if k in r])
    out["duckdb_ms_by_verdict"] = {v: summary([r["duckdb_ms"] for r in rows if r["verdict"] == v])
                                   for v in sorted({r["verdict"] for r in rows})}
    # one-time key validation per database (SF1), as in catalog.py
    kv = {}
    for db, tabs in sorted(cat.items()):
        path = os.path.join(duck_dir, f"{db}.duckdb")
        if not os.path.exists(path):
            continue
        con = duckdb.connect(path, read_only=True)
        t0 = time.perf_counter()
        nkeys = 0
        for t, v in tabs.items():
            for key in v["keys"]:
                ksql = ", ".join(qi(c) for c in key)
                nn = " or ".join(f"{qi(c)} is null" for c in key)
                con.execute(f"select count(*), (select count(*) from (select distinct {ksql} from {qi(t)})), "
                            f"count(*) filter (where {nn}) from {qi(t)}").fetchone()
                nkeys += 1
        kv[db] = {"keys": nkeys, "seconds": round(time.perf_counter() - t0, 4)}
        con.close()
    out["key_validation_sf1"] = kv
    out["key_validation_sf1_total_seconds"] = round(sum(v["seconds"] for v in kv.values()), 3)
    json.dump({"summary": out, "per_probe": rows}, open(out_path, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
