"""E1 on PostgreSQL: does each observation policy give the same preview across equivalent PostgreSQL executions?

Configurations (5): heap order of the original copy vs the seed-42 permuted copy (loaded in their physical order)
x a serial and a parallel-enabled setting (max_parallel_workers_per_gather 4, parallel costs zeroed), plus a
repeated parallel-enabled run on the original; whether PostgreSQL planned workers is recorded per query (EXPLAIN).
Each probe is transpiled to PostgreSQL (pg_cost.to_pg) and certified in the PostgreSQL dialect; policies: raw,
smart-lex, certified (DET unchanged, NARROW/ALL rewritten, UNSUPPORTED -> smart-lex). Observation: the C3
rendering (header, first 20 canonical rows, exact count), taken inside one REPEATABLE READ READ ONLY transaction.
A probe/policy is censored unless all 5 runs produce an observation.

Usage: python replay_pg.py <cert_probes.jsonl> <server> <out.jsonl>
"""
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

V = os.environ["PROJECT_ROOT"]
sys.path.insert(0, f"{V}/code/pilot_c3")
from agent_c3 import observation  # noqa: E402
from certify import certify, smartlex  # noqa: E402
from pg_cost import to_pg  # noqa: E402
from pg_setup import conninfo  # noqa: E402
from tool import canon  # noqa: E402
import psycopg  # noqa: E402

CAP = 100000
CONFIGS = [("orig_w0", "sf1", 0), ("orig_w4a", "sf1", 4), ("orig_w4b", "sf1", 4), ("p42_w0", "perm42", 0),
           ("p42_w4", "perm42", 4)]
PARALLEL = ("SET parallel_setup_cost = 0; SET parallel_tuple_cost = 0; SET min_parallel_table_scan_size = 0; "
            "SET min_parallel_index_scan_size = 0")


def connect(server, db, variant, workers):
    con = psycopg.connect(conninfo(server, f"{db}_{variant}"), autocommit=True)
    con.execute("SET statement_timeout = '20s'")
    con.execute(f"SET max_parallel_workers_per_gather = {workers}")
    if workers:
        for s in PARALLEL.split("; "):
            con.execute(s)
    return con


def observe(con, sql):
    r = {"success": False, "error": None, "rows": [], "columns": [], "n_rows": 0, "truncated": False}
    try:
        con.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur = con.execute(sql)
        rows = cur.fetchmany(CAP + 1)
        cols = [d.name for d in cur.description]
        n = len(rows)
        if n > CAP:
            n = con.execute(f"SELECT count(*) FROM ({sql.strip().rstrip(';')}) AS obs_count").fetchone()[0]
        con.execute("COMMIT")
        r.update(success=True, columns=cols, rows=[tuple(canon(v) for v in x) for x in rows[:20]], n_rows=n)
    except Exception as ex:  # noqa: BLE001
        con.execute("ROLLBACK")
        r["error"] = str(ex)[:300]
    return r


def parallel_planned(con, sql):
    try:
        plan = json.dumps(con.execute(f"EXPLAIN (FORMAT JSON) {sql}").fetchone()[0])
    except Exception:  # noqa: BLE001
        return None
    return '"Workers Planned": 0' not in plan and '"Workers Planned"' in plan


def main(cert_path, server, out_path):
    cat = {d: {t.lower(): {"columns": {c.lower(): ty for c, ty in v["columns"].items()},
                           "keys": [[c.lower() for c in k] for k in v["keys"]]} for t, v in tabs.items()}
           for d, tabs in json.load(open(f"{V}/runs/obsdet/catalog.json")).items()}
    probes = [json.loads(l) for l in open(cert_path)]
    probes = [p for p in probes if "exec_error" not in p]
    by_db = defaultdict(list)
    for p in probes:
        by_db[p["db_id"]].append(p)
    out = open(out_path, "w")
    summ = Counter()
    for db, ps in sorted(by_db.items()):
        cons = {name: connect(server, db, variant, w) for name, variant, w in CONFIGS}
        for p in ps:
            try:
                raw = to_pg(p["sql"])
            except Exception as ex:  # noqa: BLE001
                rec = {"db_id": db, "sql": p["sql"], "verdict": "UNSUPPORTED", "transpile_error": str(ex)[:120]}
                for pol in ("raw", "smartlex", "certified"):
                    summ[(pol, "UNSUPPORTED", None)] += 1
                out.write(json.dumps(rec) + "\n")
                continue
            cert = certify(raw, cat[db], "postgres")
            slx = smartlex(raw, p["n_out"], "postgres") or raw
            pgq = {"raw": raw, "smartlex": slx,
                   "certified": (cert.rewritten or raw) if cert.verdict != "UNSUPPORTED" else slx}
            rec = {"db_id": db, "sql": p["sql"], "pg_sql": raw, "verdict": cert.verdict, "reason": cert.reason,
                   "duckdb_verdict": p["verdict"], "policies": {}}
            for pol, pq in pgq.items():
                hashes, errs = [], []
                for name, _, _ in CONFIGS:
                    r = observe(cons[name], pq)
                    if r["success"]:
                        hashes.append(hashlib.sha1(observation(r, 20).encode()).hexdigest())
                    else:
                        errs.append(r["error"][:120])
                complete = len(hashes) == len(CONFIGS)
                rec["policies"][pol] = {"diverged": (len(set(hashes)) > 1) if complete else None,
                                        "n_ok": len(hashes), "errors": errs[:2], "sql": pq,
                                        "parallel_planned": parallel_planned(cons["orig_w4a"], pq)}
                summ[(pol, cert.verdict, rec["policies"][pol]["diverged"])] += 1
                summ[("parallel", pol, rec["policies"][pol]["parallel_planned"])] += 1
            out.write(json.dumps(rec) + "\n")
        for c in cons.values():
            c.close()
        print(db, "done", flush=True)
    out.close()
    print("\nPostgreSQL certificates and policies; parallel plans chosen in the parallel-enabled setting:")
    for pol in ("raw", "smartlex", "certified"):
        print(f"  {pol:9s} parallel planned {summ[('parallel', pol, True)]}, serial {summ[('parallel', pol, False)]}")
    print("\npolicy x verdict: diverged / complete (censored: transpile error or not observed in every configuration)")
    for pol in ("raw", "smartlex", "certified"):
        for v in ("DET", "NARROW", "ALL", "UNSUPPORTED"):
            d, n = summ[(pol, v, True)], summ[(pol, v, True)] + summ[(pol, v, False)]
            print(f"  {pol:9s} {v:11s} {d}/{n}  censored {summ[(pol, v, None)]}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
