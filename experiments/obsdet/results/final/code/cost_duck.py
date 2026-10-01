"""E3 cost: tool latency of agent probes on DuckDB under three observation policies.

  raw        the probe as issued;
  smartlex   existing ORDER BY keys, then every output column by position (NULLS LAST);
  certified  DET -> unchanged; NARROW/ALL -> certified rewrite; UNSUPPORTED -> smartlex fallback.

Tool latency t = execute + fetch of the result, capped at CAP rows (the same cap for every policy, so every
policy fetches the same number of rows); t20 = time until the first 20 rows (the preview) are in hand.
Per probe: REPS repetitions, policy order shuffled per repetition (seeded); TIMEOUT per execution via
interrupt; a policy that times out or errors is not repeated (reported as censored / failed).
--profile adds one EXPLAIN (ANALYZE, FORMAT JSON) per policy for plan attribution (not timed).

Cost models (--model):
  fetch  "tool as implemented in the pilot": each policy's SQL as is, fetched up to CAP rows (above);
  pc     the observation of FINAL_PROPOSAL.md: preview = the policy's SQL with its top-level LIMIT replaced by
         min(L, 20) (OFFSET kept; LIMIT 20 added if absent), plus count = SELECT count(*) over the original SQL
         with its top-level ORDER BY removed (LIMIT/OFFSET kept); the count query is the same for every policy,
         measured as a fourth query in the shuffled order and charged to every policy.

Modes:
  natural     python cost_duck.py natural --scale {sf1,x10,xmax} --dbs a,b --out f.jsonl [--probes p.jsonl] [--profile]
  controlled  python cost_duck.py controlled --scale {sf1,x10,xmax} --out f.jsonl [--profile]
"""
import argparse
import json
import os
import random
import sys
import threading
import time

import duckdb
import sqlglot
from sqlglot import exp

V = os.environ["PROJECT_ROOT"]
CATALOG = f"{V}/runs/obsdet/catalog.json"
POLICIES = ("raw", "smartlex", "certified")
SCALE_ID = {"sf1": 1, "x10": 2, "xmax": 3}

# Controlled LIMIT study: (db, table, three non-key columns, selective predicate).
CONTROLLED = [
    ("codebase_community", "posts", ["Title", "Score", "ViewCount"], "Score >= 40"),
    ("codebase_community", "comments", ["PostId", "Score", "UserId"], "Score >= 15"),
    ("codebase_community", "votes", ["PostId", "VoteTypeId", "UserId"], "VoteTypeId = 8"),
    ("codebase_community", "users", ["DisplayName", "Reputation", "Views"], "Reputation >= 5000"),
    ("card_games", "cards", ["name", "rarity", "artist"], '"convertedManaCost" >= 9'),
]


def db_path(db, scale):
    if scale == "sf1":
        return f"{V}/data/bird_duckdb/validation/{db}.duckdb"
    if scale == "x10":
        return f"{V}/data/pilot_c3_scaled/{db}_x10.duckdb"
    return f"{V}/data/pilot_c3_scaled/{db}_{'x30' if db == 'codebase_community' else 'x100'}.duckdb"


def probe_class(info):
    o, lim = info.get("has_order"), info.get("has_limit") or info.get("has_offset")
    if o and lim:
        return "order_limit"
    if o:
        return "order_only"
    if lim:
        return "limit_no_order"
    if info.get("has_distinct"):
        return "distinct"
    if info.get("has_group"):
        return "group_by"
    return "other"


def variants(r):
    sl = r.get("smartlex")
    if not sl:
        return None
    v = r["verdict"]
    cert = r["sql"] if v == "DET" else r["rewritten"] if v in ("NARROW", "ALL") else sl
    return {"raw": r["sql"], "smartlex": sl, "certified": cert}


def run(con, sql, cap, timeout):
    """Execute and fetch up to cap rows; returns (status, t, t20, rows)."""
    cur = con.cursor()
    timer = threading.Timer(timeout, cur.interrupt)
    status, n, t20 = "ok", 0, None
    t0 = time.perf_counter()
    timer.start()
    try:
        cur.execute(sql)
        while n < cap:
            b = cur.fetchmany(20 if n == 0 else min(10000, cap - n))
            if t20 is None:
                t20 = time.perf_counter() - t0
            if not b:
                break
            n += len(b)
        cur.close()
    except duckdb.InterruptException:
        status = "timeout"
    except Exception as ex:  # noqa: BLE001
        status = "error: " + str(ex)[:160]
    finally:
        timer.cancel()
    t = time.perf_counter() - t0
    try:
        cur.close()
    except Exception:  # noqa: BLE001
        pass
    return status, t, (t20 if t20 is not None else t), n


def profile(con, sql, timeout):
    """One EXPLAIN (ANALYZE, FORMAT JSON): sort operator, sort keys, operator timings, rows scanned, memory."""
    cur = con.cursor()
    timer = threading.Timer(timeout, cur.interrupt)
    timer.start()
    try:
        j = json.loads(cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql).fetchall()[0][1])
    except Exception as ex:  # noqa: BLE001
        return {"status": str(ex)[:120]}
    finally:
        timer.cancel()
        cur.close()
    j = j[0] if isinstance(j, list) else j
    timing, sorts, late = {}, [], False

    def walk(nd):
        nonlocal late
        t = nd.get("operator_type")
        timing[t] = timing.get(t, 0.0) + (nd.get("operator_timing") or 0.0)
        ei = nd.get("extra_info") or {}
        if t in ("TOP_N", "ORDER_BY"):
            ob = ei.get("Order By", "")
            ob = ob if isinstance(ob, str) else "\n".join(map(str, ob))
            sorts.append({"op": t, "keys": ob.count(" ASC") + ob.count(" DESC"), "time": nd.get("operator_timing"),
                          "rows_in": sum(c.get("operator_cardinality") or 0 for c in nd.get("children", [])),
                          "top": ei.get("Top")})
        if t == "HASH_JOIN" and ei.get("Join Type") == "SEMI" and "rowid" in str(ei.get("Conditions", "")):
            late = True
        for c in nd.get("children", []):
            walk(c)
    walk(j)
    return {"status": "ok", "latency": j.get("latency"), "cpu": j.get("cpu_time"),
            "rows_scanned": j.get("cumulative_rows_scanned"), "peak_mem": j.get("system_peak_buffer_memory"),
            "temp": j.get("system_peak_temp_dir_size"), "bytes_read": j.get("total_bytes_read"),
            "timing": {k: round(v, 6) for k, v in timing.items()}, "sorts": sorts, "late_mat": late}


def preview_sql(sql, k=20, dialect="duckdb"):
    """The policy's SQL with its top-level LIMIT replaced by min(L, k); OFFSET kept; LIMIT k added if absent."""
    ast = sqlglot.parse_one(sql, read=dialect)
    lim = ast.args.get("limit")
    if lim is None:
        ast.set("limit", exp.Limit(expression=exp.Literal.number(k)))
    elif isinstance(lim, exp.Limit) and isinstance(lim.expression, exp.Literal) and lim.expression.is_int:
        lim.set("expression", exp.Literal.number(min(int(lim.expression.name), k)))
    else:
        raise ValueError("top-level limit is not an integer literal: " + lim.sql(dialect=dialect))
    return ast.sql(dialect=dialect)


def count_sql(sql, dialect="duckdb"):
    """SELECT count(*) over the original SQL with its top-level ORDER BY removed (LIMIT/OFFSET kept)."""
    ast = sqlglot.parse_one(sql, read=dialect)
    ast.set("order", None)
    return exp.select("count(*)").from_(ast.subquery("_q")).sql(dialect=dialect)


def pc_queries(var, dialect="duckdb"):
    q = {p: preview_sql(var[p], dialect=dialect) for p in POLICIES}
    q["count"] = count_sql(var["raw"], dialect=dialect)
    return q


def measure(con, var, seed, a):
    rng = random.Random(seed)
    res = {p: {"t": [], "t20": [], "rows": [], "status": "ok"} for p in var}
    for _ in range(a.reps):
        order = list(var)
        rng.shuffle(order)
        for p in order:
            if res[p]["status"] != "ok":
                continue
            st, t, t20, n = run(con, var[p], a.cap, a.timeout)
            res[p]["status"] = st
            if st == "ok":
                res[p]["t"].append(round(t, 6))
                res[p]["t20"].append(round(t20, 6))
                res[p]["rows"].append(n)
    return res


def connect(path, a):
    con = duckdb.connect(path, read_only=True)
    con.execute(f"SET threads={a.threads}")
    con.execute(f"SET memory_limit='{a.mem}'")
    con.execute(f"SET temp_directory='{a.tmp}'")
    return con


def controlled_probes():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hashlib
    from certify import certify, smartlex
    md5 = hashlib.md5(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "certify.py"), "rb").read()).hexdigest()
    cat = json.load(open(CATALOG))
    out = []
    for db, t, cols, pred in CONTROLLED:
        ncol = len(cat[db][t]["columns"])
        c3 = ", ".join(f'"{c}"' for c in cols)
        for form, sql, nout in (("star", f'SELECT * FROM "{t}" LIMIT 20', ncol),
                                ("cols3", f'SELECT {c3} FROM "{t}" LIMIT 20', 3),
                                ("cols3_where", f'SELECT {c3} FROM "{t}" WHERE {pred} LIMIT 20', 3)):
            c = certify(sql, cat[db], "duckdb")
            sl = smartlex(sql, nout, "duckdb")
            cert = sql if c.verdict == "DET" else c.rewritten if c.verdict in ("NARROW", "ALL") else sl
            out.append({"db_id": db, "table": t, "form": form, "verdict": c.verdict, "tie_break": c.tie_break,
                        "var": {"raw": sql, "smartlex": sl, "certified": cert}, "certify_md5": md5, "n_out": nout})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["natural", "controlled"])
    ap.add_argument("--scale", required=True, choices=list(SCALE_ID))
    ap.add_argument("--dbs", default="")
    ap.add_argument("--probes", default=f"{V}/runs/obsdet/cert_probes_v3.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--cap", type=int, default=100000)
    ap.add_argument("--mem", default="24GB")
    ap.add_argument("--tmp", default="/tmp/obsdet_e3")
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--model", choices=["fetch", "pc"], default="fetch")
    ap.add_argument("--limit", type=int, default=0, help="debug: at most this many probes per db")
    ap.add_argument("--skip-timeouts-from", default="", help="jsonl(s) of a smaller scale, comma-separated: probes "
                    "whose three policies all timed out there are recorded as skipped (the interrupt is not always "
                    "honoured inside a long nested-loop join, see JOBS_E3.md)")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(line)["key"] for line in open(a.out)}
    skip = set()
    for f in filter(None, a.skip_timeouts_from.split(",")):
        for line in open(f):
            r = json.loads(line)
            if r.get("res") and all(r["res"][p]["status"] == "timeout" for p in POLICIES):
                skip.add(r["i"])
    out = open(a.out, "a")
    if a.mode == "natural":
        rows = [json.loads(line) for line in open(a.probes)]
        items = [(f"{a.scale}:{i}", i, r) for i, r in enumerate(rows)]
    else:
        items = [(f"{a.scale}:{p['db_id']}.{p['table']}.{p['form']}", i, p) for i, p in enumerate(controlled_probes())]
    dbs = a.dbs.split(",") if a.dbs else sorted({r["db_id"] for _, _, r in items})
    for db in dbs:
        con = connect(db_path(db, a.scale), a)
        t_db, k = time.time(), 0
        for key, i, r in items:
            if r["db_id"] != db or key in done or (a.limit and k >= a.limit):
                continue
            var = variants(r) if a.mode == "natural" else r["var"]
            if var is None:
                continue
            k += 1
            if i in skip:
                out.write(json.dumps({"key": key, "i": i, "db": db, "scale": a.scale, "verdict": r["verdict"],
                                      "cls": probe_class(r["info"]), "probes": os.path.basename(a.probes),
                                      "skipped": "all three policies timed out at a smaller scale"}) + "\n")
                continue
            base = {"key": key, "i": i, "db": db, "scale": a.scale, "verdict": r["verdict"], "model": a.model,
                    "probes": os.path.basename(a.probes) if a.mode == "natural" else "controlled"}
            if a.model == "pc":
                try:
                    var = pc_queries(var)
                except Exception as ex:  # noqa: BLE001
                    out.write(json.dumps({**base, "pc_error": str(ex)[:160]}) + "\n")
                    continue
            res = measure(con, var, 1000 * i + SCALE_ID[a.scale], a)
            rec = {**base, "res": res}
            if a.model == "pc":
                rec["sql"] = var
            if a.mode == "natural":
                rec["cls"] = probe_class(r["info"])
                rec["has_agg"] = bool(r["info"].get("has_agg"))
            else:
                rec.update(table=r["table"], form=r["form"], tie_break=r["tie_break"], var=var,
                           certify_md5=r.get("certify_md5"))
            if a.profile:
                rec["prof"] = {p: profile(con, var[p], a.timeout) for p in POLICIES}
            out.write(json.dumps(rec) + "\n")
            out.flush()
        con.close()
        print(f"[cost_duck] {a.mode} {a.scale} {db}: {k} probes in {time.time() - t_db:.1f}s", flush=True)


if __name__ == "__main__":
    main()
