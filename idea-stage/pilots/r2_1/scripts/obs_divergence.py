# Steps 1 + 2 of pilot R2-1: replay the successful exploratory statements of the C3 K=8 trace under
# equivalent executions and compare what the agent would see.
#   d1      : DuckDB, original physical order, 1 thread (reference)
#   d8_run1 : DuckDB, original order, 8 threads
#   d8_run2 : same instance, executed again
#   p1 / p8 : DuckDB, physically permuted copy (seed 42), 1 / 8 threads
#   sqlite  : SQLite copy (C6's, read-only; statement transpiled duckdb -> sqlite with sqlglot)
# Observation modes: raw (first 20 rows as returned, rendered exactly like the C3 agent tool);
# OBSERVE-hash (tie-breakers / deterministic LIMIT subset in SQL, otherwise client-side canonical-hash order);
# OBSERVE-lex (engine-side total order: existing ORDER BY keys, then ORDER BY 1..m NULLS LAST).
# Per statement and configuration: rendered text hash, header-free canonical signature, result multiset hash,
# timings; plus an overhead pass (alternating raw / OBSERVE, DuckDB 8 threads, SF1 and SF10).
import argparse
import collections
import hashlib
import json
import os
import sqlite3
import sys
import time

import sqlglot

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import db_path, execute_with_timeout, bag_hash  # noqa: E402
import observe as ob  # noqa: E402

V = os.environ["PROJECT_ROOT"]
PERM = f"{V}/data/pilot_r2_1"
SQLITE = f"{V}/runs/pilot_c6/dbs"
SCALED = f"{V}/data/pilot_c3_scaled"


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()


def sqlite_exec(con, sql, timeout_s=20.0, row_cap=100000):
    out = {"success": False, "error": None, "rows": [], "columns": [], "n_rows": 0, "truncated": False,
           "timeout": False}
    deadline = time.perf_counter() + timeout_s
    con.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10000)
    t0 = time.perf_counter()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(row_cap + 1)
        truncated = len(rows) > row_cap
        rows = rows[:row_cap]
        out.update(success=True, rows=rows, columns=cols, n_rows=len(rows), truncated=truncated)
    except Exception as e:
        out["error"] = str(e)[:500]
        out["timeout"] = "interrupted" in str(e).lower()
    finally:
        out["runtime"] = time.perf_counter() - t0
        con.set_progress_handler(None, 0)
    return out


def n_out_of(info, probe, sql):
    if info["n_out_static"] is not None:
        return info["n_out_static"]
    return len(probe(f"SELECT * FROM ({sql.strip().rstrip(';')}) AS __obs LIMIT 0").description)


def observe(executor, probe, sql, info, ast, dialect, variant):
    """Returns (result, shown rows, text, meta) for OBSERVE-hash or OBSERVE-lex."""
    t0 = time.perf_counter()
    exec_sql, mode, rewritten, fallback = sql, "raw", False, False
    query_like = info["parse_ok"] and info["kind"] in ("select", "setop")
    if query_like:
        needs = info["has_order"] or info["has_limit"] or info["has_offset"]
        try:
            if variant == "lex":
                exec_sql = ob.observe_rewrite_lex(ast, n_out_of(info, probe, sql), dialect)
                rewritten, mode = True, "lex"
            elif needs:
                exec_sql, _ = ob.observe_rewrite(ast, n_out_of(info, probe, sql), dialect)
                rewritten, mode = True, "lex"
            else:
                mode = "hash"
        except Exception:
            fallback = True
            mode = "raw" if info["has_order"] else "hash"
    r = executor(exec_sql)
    if not r["success"] and rewritten:
        r = executor(sql)
        fallback = True
        mode = "raw" if info["has_order"] else "hash"
    t1 = time.perf_counter()
    rows = ob.shown_rows(r, mode)
    text = ob.render_rows(r, rows, ob.K)
    t2 = time.perf_counter()
    return r, rows, text, {"rewritten": rewritten, "fallback": fallback, "mode": mode, "engine_s": t1 - t0,
                           "client_s": t2 - t1, "exec_sql": exec_sql if rewritten else None}


def canon_rows_list(rows):
    return [tuple(ob.canon_value(v) for v in row) for row in rows]


def contract_check(con, sql, info, ast, r, ro, meta):
    """Semantic contract of canonical OBSERVE v2 against the raw execution r of the same statement on the
    same configuration. Returns dict of violations (True = violated) or None if not checkable."""
    if not r["success"] or r["truncated"] or not ro["success"]:
        return None
    v = {}
    k = ob.K
    obs_rows = canon_rows_list(ro["rows"][:k])
    raw_rows = canon_rows_list(r["rows"])
    v["row_count"] = ro["n_rows"] != r["n_rows"]
    v["columns"] = list(ro["columns"]) != list(r["columns"])
    full = raw_rows
    if meta.get("path") == "total_order" and (info["has_limit"] or info["has_offset"]):
        a2 = ast.copy()
        a2.set("limit", None)
        a2.set("offset", None)
        rf = execute_with_timeout(con, a2.sql(dialect="duckdb"), 20.0)
        full = canon_rows_list(rf["rows"]) if (rf["success"] and not rf["truncated"]) else None
    if full is not None:
        need, have = collections.Counter(obs_rows), collections.Counter(full)
        v["rows_not_in_result"] = any(have[x] < c for x, c in need.items())
    if info["has_order"]:
        pos = ob.order_key_positions(info, ast)
        if pos is not None:
            ka = [tuple(row[p] for p in pos) for row in obs_rows]
            kb = [tuple(row[p] for p in pos) for row in raw_rows[:len(obs_rows)]]
            v["order_keys"] = ka != kb
    return v


def one_config(executor, probe, sql, info, ast, dialect, keep_text, con=None):
    r = executor(sql)
    raw_text = ob.render_raw(r, ob.K)
    out = {"success": r["success"], "error": r["error"], "n_rows": r["n_rows"], "truncated": r["truncated"],
           "raw_sha": sha(raw_text), "raw_sig": ob.canon_sig(r["rows"], r["n_rows"], r["truncated"]) if r["success"] else None,
           "bag": bag_hash(r["rows"]) if r["success"] else None, "raw_s": r["runtime"],
           "raw_text": raw_text if keep_text else None, "columns": r["columns"]}
    for variant in ("hash", "lex"):
        ro, rows, text, meta = observe(executor, probe, sql, info, ast, dialect, variant)
        out[f"{variant}_sha"] = sha(text)
        out[f"{variant}_sig"] = ob.canon_sig(rows, ro["n_rows"], ro["truncated"]) if ro["success"] else None
        out[f"{variant}_bag"] = bag_hash(ro["rows"]) if ro["success"] else None
        out[f"{variant}_meta"] = meta
        out[f"{variant}_text"] = text if keep_text else None
    if con is not None:  # canonical OBSERVE v2 (DuckDB only)
        ro, rows, text, meta = ob.observe_v2(con, sql, lambda c, q: execute_with_timeout(c, q, 20.0))
        out["canon_sha"] = sha(text)
        out["canon_sig"] = ob.canon_sig(rows, ro["n_rows"], ro["truncated"]) if ro["success"] else None
        out["canon_meta"] = {kk: vv for kk, vv in meta.items() if kk != "exec_sql"}
        out["canon_text"] = text if keep_text else None
        out["contract"] = contract_check(con, sql, info, ast, r, ro, meta)
    return out, (r["rows"] if r["success"] else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default=f"{V}/runs/pilot_c3/agent_qwen3_8b/trace.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dbs", default="")
    ap.add_argument("--timing-reps", type=int, default=3)
    ap.add_argument("--timing-scales", default="1,10")
    args = ap.parse_args()
    evs = [json.loads(l) for l in open(args.trace)]
    probes = [e for e in evs if not e["is_final"] and e["success"]]
    distinct = collections.OrderedDict()
    for e in probes:
        d = distinct.setdefault((e["db_id"], e["sql"]), {"db_id": e["db_id"], "sql": e["sql"], "occurrences": 0,
                                                         "tasks": set()})
        d["occurrences"] += 1
        d["tasks"].add(e["task_id"])
    print("successful exploratory statements", len(probes), "distinct", len(distinct), flush=True)
    by_db = collections.defaultdict(list)
    for d in distinct.values():
        by_db[d["db_id"]].append(d)
    dbs = [d for d in sorted(by_db) if not args.dbs or d in args.dbs.split(",")]
    f = open(args.out, "w")
    for db in dbs:
        t0 = time.time()
        inst = {"orig1": ob.open_instance(db_path(db), 1), "orig8": ob.open_instance(db_path(db), 8),
                "perm1": ob.open_instance(f"{PERM}/{db}_perm42.duckdb", 1),
                "perm8": ob.open_instance(f"{PERM}/{db}_perm42.duckdb", 8)}
        sq = sqlite3.connect(f"file:{SQLITE}/{db}.sqlite?mode=ro", uri=True, check_same_thread=False)
        scaled = {int(s): ob.open_instance(f"{SCALED}/{db}_x{s}.duckdb", 8, memory_limit="40GB")
                  for s in args.timing_scales.split(",") if s and int(s) != 1}
        print(db, "instances ready in", round(time.time() - t0, 1), "s;", len(by_db[db]), "statements", flush=True)
        for d in by_db[db]:
            sql = d["sql"]
            info, ast = ob.top_info(sql)
            rec = {"db_id": db, "sql": sql, "occurrences": d["occurrences"], "tasks": sorted(d["tasks"]),
                   "info": {k: v for k, v in info.items() if k != "select_sqls"}, "cfg": {}}
            d1_rows = None
            for name, key in [("d1", "orig1"), ("d8_run1", "orig8"), ("d8_run2", "orig8"), ("p1", "perm1"), ("p8", "perm8")]:
                con = inst[key]
                res, rows = one_config(lambda q, c=con: execute_with_timeout(c, q, 20.0),
                                       lambda q, c=con: c.cursor().execute(q), sql, info, ast, "duckdb",
                                       keep_text=name in ("d1", "p1", "d8_run1"), con=con)
                rec["cfg"][name] = res
                if name == "d1":
                    d1_rows = rows
            try:
                sq_sql = sqlglot.transpile(sql, read="duckdb", write="sqlite")[0]
            except Exception:
                sq_sql = None
            if sq_sql is not None:
                res, _ = one_config(lambda q: sqlite_exec(sq, q), lambda q: sq.execute(q), sq_sql, info, ast, "sqlite",
                                    keep_text=True)
                res["sql"] = sq_sql
                rec["cfg"]["sqlite"] = res
            else:
                rec["cfg"]["sqlite"] = {"sql": None, "success": False, "error": "transpile failed"}
            rec["type"] = ob.statement_type(info, ast, d1_rows)
            rec["timing"] = {}
            for scale, con in [(1, inst["orig8"])] + sorted(scaled.items()):
                tr, th, thc, tl, tlc, tcn, tcnc = [], [], [], [], [], [], []
                ok = True
                for rep in range(args.timing_reps):
                    if rep > 0 and tr[0] > 2.0:
                        break  # heavy statement: one repetition (bounded by the timeout)
                    ex = lambda q, c=con: execute_with_timeout(c, q, 30.0)
                    pr = lambda q, c=con: c.cursor().execute(q)
                    r = ex(sql)
                    ok = ok and r["success"]
                    tr.append(r["runtime"])
                    _, _, _, mh = observe(ex, pr, sql, info, ast, "duckdb", "hash")
                    _, _, _, ml = observe(ex, pr, sql, info, ast, "duckdb", "lex")
                    _, _, _, mc = ob.observe_v2(con, sql, lambda c, q: execute_with_timeout(c, q, 30.0))
                    th.append(mh["engine_s"]); thc.append(mh["client_s"])
                    tl.append(ml["engine_s"]); tlc.append(ml["client_s"])
                    tcn.append(mc["engine_s"]); tcnc.append(mc["client_s"])
                med = lambda xs: sorted(xs)[len(xs) // 2]
                rec["timing"][str(scale)] = {"raw_s": med(tr), "hash_engine_s": med(th), "hash_client_s": med(thc),
                                             "lex_engine_s": med(tl), "lex_client_s": med(tlc),
                                             "canon_engine_s": med(tcn), "canon_client_s": med(tcnc), "raw_ok": ok,
                                             "reps": len(tr)}
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
        for c in list(inst.values()) + list(scaled.values()):
            c.close()
        sq.close()
        print(db, "done in", round(time.time() - t0, 1), "s", flush=True)
    f.close()


if __name__ == "__main__":
    main()
