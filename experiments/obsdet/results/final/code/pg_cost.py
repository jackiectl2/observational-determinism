"""E3 cost on PostgreSQL, same protocol as cost_duck.py: tool latency = execute + fetch capped at CAP rows (rows
streamed in chunks of 20, so t20 = time until the first 20 rows are in hand; a capped stream is cancelled),
REPS repetitions with seeded shuffled policy order, TIMEOUT via statement_timeout, a policy that times out or
errors is not repeated. --model pc: preview + count model of cost_duck.py (queries built on the DuckDB SQL, then
transpiled); EXPLAIN is then run on the preview queries. Each policy's DuckDB SQL is transpiled with sqlglot: parse (duckdb) ->
normalize_identifiers (duckdb: every identifier lowercased, matching the lowercased PG schema) -> postgres.
--explain-scales adds one EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) per policy at those scales.

python pg_cost.py natural <server> <db> --scales sf1,x10 --out f.jsonl [--explain-scales x10]
python pg_cost.py controlled <server> <db> --scales sf1,x10 --out f.jsonl [--explain-scales sf1,x10]
Natural probes whose three variants do not all succeed at the first scale are not replayed at later scales.
"""
import argparse
import json
import os
import random
import sys
import time

import sqlglot
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cost_duck import POLICIES, SCALE_ID, V, controlled_probes, pc_queries, probe_class, variants  # noqa: E402
from pg_setup import CATALOG, conninfo  # noqa: E402  (also appends the psycopg path)

import psycopg  # noqa: E402


def pg_catalog():
    """The catalog with every table and column name lowercased (as loaded into PostgreSQL; as in replay_pg.py)."""
    return {d: {t.lower(): {"columns": {c.lower(): ty for c, ty in v["columns"].items()},
                            "keys": [[c.lower() for c in k] for k in v["keys"]]} for t, v in tabs.items()}
            for d, tabs in json.load(open(CATALOG)).items()}


def pg_policies(raw_duck, n_out, catdb):
    """PostgreSQL-dialect certificate and policies, constructed as in replay_pg.py."""
    from certify import certify, smartlex
    raw = to_pg(raw_duck)
    cert = certify(raw, catdb, "postgres")
    slx = smartlex(raw, n_out, "postgres") or raw
    pol = {"raw": raw, "smartlex": slx,
           "certified": (cert.rewritten or raw) if cert.verdict != "UNSUPPORTED" else slx}
    return pol, cert


def to_pg(sql):
    return normalize_identifiers(sqlglot.parse_one(sql, read="duckdb"), dialect="duckdb").sql(dialect="postgres")


def run(con, sql, cap):
    status, n, t20 = "ok", 0, None
    t0 = time.perf_counter()
    try:
        gen = con.cursor().stream(sql, size=20)
        for _ in gen:
            n += 1
            if n == 20:
                t20 = time.perf_counter() - t0
            if n >= cap:
                break
        gen.close()
    except psycopg.errors.QueryCanceled:
        status = "timeout"
    except Exception as ex:  # noqa: BLE001
        status = "error: " + str(ex)[:160]
    t = time.perf_counter() - t0
    return status, t, (t20 if t20 is not None else t), n


def run_txn(con, preview, count):
    """One observation: BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; preview; count; COMMIT.
    Returns (status, t_preview, t_count, t_txn, rows); status ok / timeout_preview / timeout_count / error."""
    tp = tc = None
    status, n, stage = "ok", None, "begin"
    t0 = time.perf_counter()
    try:
        con.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        stage = "preview"
        t1 = time.perf_counter()
        n = len(con.execute(preview).fetchall())
        tp = time.perf_counter() - t1
        stage = "count"
        t2 = time.perf_counter()
        con.execute(count).fetchone()
        tc = time.perf_counter() - t2
        con.execute("COMMIT")
    except psycopg.errors.QueryCanceled:
        status = "timeout_" + stage
    except Exception as ex:  # noqa: BLE001
        status = "error: " + str(ex)[:160]
    if status != "ok":
        con.execute("ROLLBACK")
    return status, tp, tc, time.perf_counter() - t0, n


def measure_txn(con, pv, seed, a):
    """pctxn model: per repetition, the three policies in shuffled order, each as one read-only transaction."""
    rng = random.Random(seed)
    res = {p: {"t": [], "count_t": [], "txn_t": [], "rows": [], "status": "ok"} for p in POLICIES}
    for _ in range(a.reps):
        order = list(POLICIES)
        rng.shuffle(order)
        for p in order:
            if res[p]["status"] != "ok":
                continue
            st, tp, tc, tt, n = run_txn(con, pv[p], pv["count"])
            res[p]["status"] = st
            if tp is not None:
                res[p]["t"].append(round(tp, 6))
            if st == "ok":
                res[p]["count_t"].append(round(tc, 6))
                res[p]["txn_t"].append(round(tt, 6))
                res[p]["rows"].append(n)
    return res


def measure(con, var, seed, a):
    rng = random.Random(seed)
    res = {p: {"t": [], "t20": [], "rows": [], "status": "ok"} for p in var}
    for _ in range(a.reps):
        order = list(var)
        rng.shuffle(order)
        for p in order:
            if res[p]["status"] != "ok":
                continue
            st, t, t20, n = run(con, var[p], a.cap)
            res[p]["status"] = st
            if st == "ok":
                res[p]["t"].append(round(t, 6))
                res[p]["t20"].append(round(t20, 6))
                res[p]["rows"].append(n)
    return res


def explain(con, sql):
    try:
        j = con.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql).fetchone()[0]
    except Exception as ex:  # noqa: BLE001
        return {"status": str(ex)[:120]}
    j = j[0] if isinstance(j, list) else j
    root, nodes = j["Plan"], []

    def walk(nd):
        nodes.append(nd)
        for c in nd.get("Plans", []):
            walk(c)
    walk(root)
    chain, nd = [], root
    while nd is not None and len(chain) < 6:
        chain.append(nd["Node Type"])
        nd = (nd.get("Plans") or [None])[0]
    loops = lambda n: n.get("Actual Loops", 1) or 1  # noqa: E731
    sorts = [{"type": n["Node Type"], "method": n.get("Sort Method"), "keys": len(n.get("Sort Key", [])),
              "presorted": len(n.get("Presorted Key", [])), "space_kb": n.get("Sort Space Used"),
              "space_type": n.get("Sort Space Type"), "time": n.get("Actual Total Time")}
             for n in nodes if n["Node Type"] in ("Sort", "Incremental Sort")]
    scans = [{"type": n["Node Type"], "rel": n.get("Relation Name"), "index": n.get("Index Name"),
              "dir": n.get("Scan Direction"), "rows": n.get("Actual Rows", 0) * loops(n),
              "removed": (n.get("Rows Removed by Filter", 0) or 0) * loops(n)}
             for n in nodes if n["Node Type"].endswith("Scan")]
    return {"status": "ok", "exec_ms": j.get("Execution Time"), "plan_ms": j.get("Planning Time"), "chain": chain,
            "sorts": sorts, "scans": scans, "rows_scanned": sum(s["rows"] + s["removed"] for s in scans),
            "hit": root.get("Shared Hit Blocks"), "read": root.get("Shared Read Blocks"),
            "temp_written": root.get("Temp Written Blocks")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["natural", "controlled"])
    ap.add_argument("server")
    ap.add_argument("db")
    ap.add_argument("--scales", default="sf1,x10")
    ap.add_argument("--explain-scales", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--probes", default=f"{V}/runs/obsdet/cert_probes_v3.jsonl")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--cap", type=int, default=100000)
    ap.add_argument("--limit", type=int, default=0, help="debug: at most this many probes per scale")
    ap.add_argument("--pgcert", action="store_true", help="certify the transpiled SQL in the postgres dialect (as "
                    "replay_pg.py) instead of transpiling the DuckDB-dialect rewrites")
    ap.add_argument("--model", choices=["fetch", "pc", "pctxn"], default="fetch",
                    help="see cost_duck.py; pctxn = pc with each policy's preview and count in one REPEATABLE READ "
                         "READ ONLY transaction (the count is timed inside every policy's transaction)")
    a = ap.parse_args()
    scales = a.scales.split(",")
    prev = [json.loads(line) for line in open(a.out)] if os.path.exists(a.out) else []
    done = {r["key"] for r in prev}
    ok_first = {r["i"] for r in prev if r["scale"] == scales[0] and r.get("res")
                and all(x["status"] == "ok" for x in r["res"].values())}
    if a.mode == "natural":
        items = [(i, r, variants(r)) for i, r in enumerate(json.loads(line) for line in open(a.probes))]
    else:
        items = [(i, p, p["var"]) for i, p in enumerate(controlled_probes())]
    items = [(i, r, var) for i, r, var in items if r["db_id"] == a.db and var is not None]
    out = open(a.out, "a")
    catpg = pg_catalog()[a.db] if a.pgcert else None
    md5 = __import__("hashlib").md5(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "certify.py"),
                                         "rb").read()).hexdigest()
    for scale in scales:
        con = psycopg.connect(conninfo(a.server, f"{a.db}_{scale}"), autocommit=True)
        con.execute(f"SET statement_timeout = {int(a.timeout * 1000)}")
        t_s, k = time.time(), 0
        for i, r, var in items:
            key = f"pg:{scale}:{i}" if a.mode == "natural" else f"pg:{scale}:{r['db_id']}.{r['table']}.{r['form']}"
            if key in done or (a.mode == "natural" and scale != scales[0] and i not in ok_first) or (a.limit and k >= a.limit):
                continue
            rec = {"key": key, "i": i, "db": a.db, "scale": scale, "engine": "postgres", "verdict": r["verdict"],
                   "model": a.model, "probes": os.path.basename(a.probes) if a.mode == "natural" else "controlled"}
            if a.mode == "natural":
                rec.update(cls=probe_class(r["info"]), has_agg=bool(r["info"].get("has_agg")))
            else:
                rec.update(table=r["table"], form=r["form"])
            try:
                if a.pgcert:
                    pol, cert = pg_policies(var["raw"], r["n_out"], catpg)
                    rec.update(duckdb_verdict=r["verdict"], verdict=cert.verdict, reason=cert.reason,
                               tie_break=cert.tie_break, certify_md5=md5, cert_dialect="postgres")
                    pv = pc_queries(pol, dialect="postgres") if a.model in ("pc", "pctxn") else pol
                else:
                    q = pc_queries(var) if a.model in ("pc", "pctxn") else {p: var[p] for p in POLICIES}
                    pv = {p: to_pg(x) for p, x in q.items()}
            except Exception as ex:  # noqa: BLE001
                rec["translate_error"] = str(ex)[:160]
                out.write(json.dumps(rec) + "\n")
                continue
            rec["res"] = (measure_txn if a.model == "pctxn" else measure)(con, pv, 1000 * i + SCALE_ID[scale], a)
            if scale == scales[0] and all(x["status"] == "ok" for x in rec["res"].values()):
                ok_first.add(i)
            if scale in a.explain_scales.split(","):
                rec["explain"] = {p: explain(con, pv[p]) for p in POLICIES}
            if a.mode == "controlled" or a.model != "fetch":
                rec["pg_sql"] = pv
            out.write(json.dumps(rec) + "\n")
            out.flush()
            k += 1
        con.close()
        print(f"[pg_cost] {a.mode} {a.db} {scale}: {k} probes in {time.time() - t_s:.1f}s", flush=True)


if __name__ == "__main__":
    main()
