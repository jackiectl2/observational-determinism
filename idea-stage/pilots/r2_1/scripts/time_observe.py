# Step 2 (overhead) and a determinism check for OBSERVE v3: alternating raw / v2 / v3 executions of every
# distinct successful exploratory statement, DuckDB 8 threads, SF1 and SF10; plus v3 observations under the
# five DuckDB equivalent executions (d1, d8 x2, p1, p8) at SF1.
import argparse
import collections
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import db_path, execute_with_timeout  # noqa: E402
import observe as ob  # noqa: E402

V = os.environ["PROJECT_ROOT"]


def schema_lc(con):
    out = {}
    for t, c, ty in con.execute("SELECT table_name, column_name, data_type FROM duckdb_columns() WHERE schema_name='main'").fetchall():
        out.setdefault(t.lower(), {})[c.lower()] = ty
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default=f"{V}/runs/pilot_c3/agent_qwen3_8b/trace.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--dbs", default="")
    args = ap.parse_args()
    evs = [json.loads(l) for l in open(args.trace)]
    distinct = collections.OrderedDict()
    for e in evs:
        if not e["is_final"] and e["success"]:
            d = distinct.setdefault((e["db_id"], e["sql"]), {"db_id": e["db_id"], "sql": e["sql"], "occurrences": 0})
            d["occurrences"] += 1
    by_db = collections.defaultdict(list)
    for d in distinct.values():
        by_db[d["db_id"]].append(d)
    f = open(args.out, "w")
    for db in sorted(by_db):
        if args.dbs and db not in args.dbs.split(","):
            continue
        t0 = time.time()
        inst = {"d1": ob.open_instance(db_path(db), 1), "d8": ob.open_instance(db_path(db), 8),
                "p1": ob.open_instance(f"{V}/data/pilot_r2_1/{db}_perm42.duckdb", 1),
                "p8": ob.open_instance(f"{V}/data/pilot_r2_1/{db}_perm42.duckdb", 8),
                "sf10": ob.open_instance(f"{V}/data/pilot_c3_scaled/{db}_x10.duckdb", 8, memory_limit="40GB")}
        sch = schema_lc(inst["d1"])
        print(db, "ready", round(time.time() - t0, 1), "s", len(by_db[db]), "statements", flush=True)
        for d in by_db[db]:
            sql = d["sql"]
            rec = {"db_id": db, "sql": sql, "occurrences": d["occurrences"], "v3": {}, "timing": {}}
            ex20 = lambda c, q: execute_with_timeout(c, q, 20.0)
            rec["v4"] = {}
            for name, key in (("d1", "d1"), ("d8_run1", "d8"), ("d8_run2", "d8"), ("p1", "p1"), ("p8", "p8")):
                r, shown, text, meta = ob.observe_v3(inst[key], sql, ex20, sch)
                rec["v3"][name] = {"sha": hashlib.sha1(text.encode()).hexdigest(), "path": meta["path"],
                                   "fallback": meta["fallback"], "probe": meta.get("probe", False),
                                   "n_rows": r["n_rows"], "truncated": r["truncated"], "success": r["success"]}
                r, shown, text, meta = ob.observe_v4(inst[key], sql, ex20, sch)
                rec["v4"][name] = {"sha": hashlib.sha1(text.encode()).hexdigest(), "path": meta["path"],
                                   "fallback": meta["fallback"], "n_rows": r["n_rows"], "truncated": r["truncated"],
                                   "success": r["success"]}
            for scale, key in (("1", "d8"), ("10", "sf10")):
                con = inst[key]
                ex = lambda c, q: execute_with_timeout(c, q, 30.0)
                tr, t2, t3, t4, ok = [], [], [], [], True
                for rep in range(args.reps):
                    if rep > 0 and tr[0] > 2.0:
                        break
                    a = time.perf_counter()
                    r = ex(con, sql)
                    ob.render_raw(r, ob.K)
                    tr.append(time.perf_counter() - a)
                    ok = ok and r["success"] and not r["truncated"]
                    a = time.perf_counter()
                    ob.observe_v2(con, sql, ex)
                    t2.append(time.perf_counter() - a)
                    a = time.perf_counter()
                    ob.observe_v3(con, sql, ex, sch)
                    t3.append(time.perf_counter() - a)
                    a = time.perf_counter()
                    ob.observe_v4(con, sql, ex, sch)
                    t4.append(time.perf_counter() - a)
                med = lambda xs: sorted(xs)[len(xs) // 2]
                rec["timing"][scale] = {"raw_s": med(tr), "v2_s": med(t2), "v3_s": med(t3), "v4_s": med(t4),
                                        "eligible": ok, "reps": len(tr)}
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
        for c in inst.values():
            c.close()
        print(db, "done", round(time.time() - t0, 1), "s", flush=True)
    f.close()


if __name__ == "__main__":
    main()
