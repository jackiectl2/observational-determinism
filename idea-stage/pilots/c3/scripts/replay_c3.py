# Replay an agent SQL trace on an (optionally scaled) in-memory copy of each database and account
# engine cost under three policies, per task (reuse scope = the K parallel attempts of one question):
#   (a) no cache: every statement is executed (measured);
#   (b) exact / normalized result cache: a statement whose exact text or normalized form was issued
#       earlier in the task is served from the cache (cost 0); others are charged their (a) measurement;
#   (c) (b) + containment reuse from cached results + materialization of shared SPJ units (join core +
#       filters) and filtered scans on their second occurrence. Every reuse operation (compensation query,
#       materialization, rewritten query) is executed and measured; statements that still miss are charged
#       their (a) measurement (same statement, same engine state).
# Results served by reuse are validated against the (a) result of the same statement.
import argparse
import collections
import json
import os
import random
import re
import threading
import time
import warnings

import duckdb
import pyarrow as pa

from common import db_path, SCALED_DIR, SKIP_TABLES, canon_rows, bag_hash
import sqlreuse as sr
from sqlglot import exp

warnings.filterwarnings("ignore", category=DeprecationWarning)

CACHE_ROW_CAP = 1_000_000
# (c) policies: containment from cached results is always on; SPJ-unit / filtered-scan materialization on the
# second occurrence either always ("c"), never ("c_contain"), or only when an earlier occurrence of the same
# unit cost >= 20 ms of engine time ("c_cost"; threshold fixed before looking at SF100 results).
POLICIES = {"c": {"units": True, "scans": True, "min_prior_s": 0.0},
            "c_contain": {"units": False, "scans": False, "min_prior_s": 0.0},
            "c_cost": {"units": True, "scans": True, "min_prior_s": 0.02}}
VALIDATE_ROW_CAP = 50_000
FIXED_WIDTH = {"BOOLEAN": 1, "TINYINT": 1, "SMALLINT": 2, "INTEGER": 4, "BIGINT": 8, "HUGEINT": 16, "FLOAT": 4,
               "DOUBLE": 8, "DATE": 4, "TIME": 8, "TIMESTAMP": 8, "UUID": 16, "UBIGINT": 8, "UINTEGER": 4}


def load_db(db_id, scale, threads):
    src = db_path(db_id) if scale == 1 else f"{SCALED_DIR}/{db_id}_x{scale}.duckdb"
    con = duckdb.connect()
    con.execute("SET threads=8")  # load with 8 threads regardless of the replay setting
    con.execute("SET memory_limit='60GB'")
    con.execute(f"ATTACH '{src}' AS src (READ_ONLY)")
    con.execute("COPY FROM DATABASE src TO memory")
    con.execute("DETACH src")
    con.execute("USE memory")
    con.execute(f"SET threads={threads}")
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE database_name='memory' AND schema_name='main'").fetchall()
        if r[0] not in SKIP_TABLES]
    widths, schema_lc, nrows = {}, {}, {}
    for t in tables:
        cols = con.execute("SELECT column_name, data_type FROM duckdb_columns() WHERE database_name='memory' "
                           "AND schema_name='main' AND table_name=? ORDER BY column_index", [t]).fetchall()
        schema_lc[t.lower()] = {c.lower(): ty for c, ty in cols}
        nrows[t.lower()] = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
        w = {}
        for c, ty in cols:
            base = ty.split("(")[0].upper()
            if base in FIXED_WIDTH:
                w[c.lower()] = FIXED_WIDTH[base]
            elif base == "DECIMAL":
                w[c.lower()] = 8
            else:
                avg = con.execute(f'SELECT avg(strlen(CAST("{c}" AS VARCHAR))) FROM "{t}" USING SAMPLE 20000 ROWS').fetchone()[0]
                w[c.lower()] = 4 + (avg or 0)
        widths[t.lower()] = w
    con.execute("PRAGMA enable_profiling='no_output'")
    return con, widths, schema_lc, nrows


def scan_bytes(profile, widths):
    """Estimated bytes read by base-table scans: rows scanned x widths of projected + filter columns."""
    total = 0.0
    stack = [profile]
    while stack:
        n = stack.pop()
        stack.extend(n.get("children", []))
        if n.get("operator_type") != "TABLE_SCAN":
            continue
        info = n.get("extra_info") or {}
        table = info.get("Table")
        if not table:
            continue
        t = table.split(".")[-1].lower()
        w = widths.get(t)
        if w is None:
            continue
        proj = info.get("Projections") or []
        if isinstance(proj, str):
            proj = [p.strip() for p in proj.split("\n") if p.strip()]
        cols = {p.lower() for p in proj if p.lower() in w}
        filt = info.get("Filters") or ""
        if isinstance(filt, list):
            filt = " ".join(filt)
        for c in w:
            if c not in cols and re.search(r"(?<![A-Za-z0-9_])" + re.escape(c) + r"(?![A-Za-z0-9_])", filt, re.I):
                cols.add(c)
        total += n.get("operator_rows_scanned", 0) * sum(w[c] for c in cols)
    return total


def run(con, sql, timeout, widths, keep=True):
    timer = threading.Timer(timeout, con.interrupt)
    out = {"ok": False, "timeout": False, "error": None, "exec_s": 0.0, "fetch_s": 0.0, "rows_scanned": 0,
           "bytes": 0.0, "cpu_s": 0.0, "n_rows": 0, "tbl": None}
    timer.start()
    t0 = time.perf_counter()
    try:
        res = con.execute(sql)
        t1 = time.perf_counter()
        tbl = res.fetch_arrow_table()
        t2 = time.perf_counter()
        out.update(ok=True, exec_s=t1 - t0, fetch_s=t2 - t1, n_rows=tbl.num_rows, tbl=tbl if keep else None)
        prof = json.loads(con.get_profiling_information(format="json"))
        out["rows_scanned"] = prof.get("cumulative_rows_scanned", 0)
        out["cpu_s"] = prof.get("cpu_time", 0.0) or 0.0
        out["bytes"] = scan_bytes(prof, widths)
    except Exception as e:
        out["exec_s"] = time.perf_counter() - t0
        out["cpu_s"] = out["exec_s"]  # failed / interrupted: charge wall time
        out["error"] = str(e)[:300]
        out["timeout"] = "INTERRUPT" in str(e).upper()
    finally:
        timer.cancel()
    return out


def signature(tbl):
    if tbl is None:
        return None
    if tbl.num_rows > VALIDATE_ROW_CAP:
        return ("n", tbl.num_rows)
    rows = list(zip(*[c.to_pylist() for c in tbl.columns])) if tbl.num_columns else []
    return ("h", bag_hash(rows))


def as_relation(tbl):
    t = tbl.rename_columns([f"c{i}" for i in range(tbl.num_columns)])
    return t.append_column("__rn", pa.array(range(t.num_rows), type=pa.int64()))


class Q:
    """One trace statement with its parsed forms."""

    def __init__(self, ev, schema_lc):
        self.ev = ev
        self.seq = ev["seq"]
        self.attempt = ev["attempt"]
        self.sql = ev["sql"]
        self.exact = sr.exact_key(self.sql)
        self.ast, self.qual_ok, self.alias_ok = sr.normalize_ast(self.sql, schema_lc)
        self.norm = sr.normalized_key(self.ast) if self.ast is not None else None
        self.block = None
        self.scan_units = []
        self.alias_table = {}
        if self.ast is not None and self.qual_ok and self.alias_ok:
            try:
                self.block = sr.extract_block(self.ast)
            except Exception:
                self.block = None
            try:
                self.scan_units = sr.scan_units(self.ast)
            except Exception:
                self.scan_units = []
            for t in self.ast.find_all(exp.Table):
                self.alias_table[t.alias_or_name] = t.name


def unit_block(core_block, filt_items, cols):
    b = sr.Block()
    b.tables, b.left, b.join_preds = core_block.tables, (), core_block.join_preds
    b.filters = dict(filt_items)
    b.select = [(c, sr.sqlglot.parse_one(c, read=sr.DIALECT)) for c in cols]
    return b


def unit_sql(q, filt_items, cols):
    frm = ", ".join(f'"{q.alias_table[a]}" AS "{a}"' if q.alias_table[a] != a else f'"{a}"' for a in q.block.tables)
    conds = sorted(q.block.join_preds) + [s for s, _ in filt_items]
    where = (" WHERE " + " AND ".join(f"({c})" for c in conds)) if conds else ""
    sel = ", ".join(f"{c} AS c{i}" for i, c in enumerate(cols))
    return f"SELECT {sel} FROM {frm}{where}"


def implied_all(q_filters, cand_items):
    qp = [sr.Pred(n) for n in q_filters.values()]
    for s, node in cand_items:
        if s in q_filters:
            continue
        c = sr.Pred(node)
        if not any(sr.implies(n, c) for n in qp):
            return False
    return True


def replay_task(con, qs, widths, nrows, timeout, rng):
    recs = {q.seq: {"seq": q.seq, "task_id": q.ev["task_id"], "db_id": q.ev["db_id"], "attempt": q.attempt,
                    "turn": q.ev["turn"], "is_final": q.ev["is_final"], "trace_success": q.ev["success"],
                    "parse_ok": q.ast is not None, "block": q.block is not None} for q in qs}
    # ---------------- (a) execute everything
    a_res = {}
    for q in qs:
        r = run(con, q.sql, timeout, widths)
        a_res[q.seq] = r
        rec = recs[q.seq]
        rec["a"] = {k: r[k] for k in ("ok", "timeout", "exec_s", "fetch_s", "rows_scanned", "bytes", "cpu_s", "n_rows")}
        rec["a_sig"] = signature(r["tbl"]) if r["ok"] else None
    # ---------------- (b) exact / normalized cache ledger
    seen_exact, seen_norm = {}, {}
    for q in qs:
        rec = recs[q.seq]
        if q.exact in seen_exact:
            rec["b"] = {"hit": "exact", "src": seen_exact[q.exact]}
        elif q.norm is not None and q.norm in seen_norm:
            rec["b"] = {"hit": "normalized", "src": seen_norm[q.norm]}
        else:
            rec["b"] = {"hit": None}
        seen_exact.setdefault(q.exact, q.seq)
        if q.norm is not None:
            seen_norm.setdefault(q.norm, q.seq)
    # ---------------- (c) containment + shared sub-expression materialization, one run per policy
    def simulate(pname, pol):
        ZERO = {"exec_s": 0.0, "fetch_s": 0.0, "rows_scanned": 0, "bytes": 0.0, "cpu_s": 0.0}
        rels = collections.defaultdict(list)  # core -> [dict(block, name, n, nbytes, seq, attempt)] cached results (arrow)
        seen_blocks = collections.defaultdict(list)  # core -> [(filters dict, base_cols set, attempt, a_exec_s)]
        units = []  # [dict(core, filters, cols, name, n, block, attempts)] materialized SPJ units (temp tables)
        seen_scans = collections.defaultdict(list)  # table -> [(conj tuple, cols set, attempt, a_exec_s)]
        scans = {}  # (table, conj tuple) -> dict(useful, cols, name, n, attempts) materialized filtered scans
        registered, temps = [], []
        uid = [0]
        parsed = {}

        def P(s):
            if s not in parsed:
                parsed[s] = sr.sqlglot.parse_one(s, read=sr.DIALECT)
            return parsed[s]

        def add(cost, r):
            return {k: cost[k] + r[k] for k in ZERO}

        def register(tbl):
            uid[0] += 1
            name = f"rel_{uid[0]}"
            con.register(name, tbl)
            registered.append(name)
            return name

        def materialize(select_sql):
            """CREATE TEMP TABLE AS select (measured). Returns (name, n_rows, cost) or (None, 0, cost)."""
            uid[0] += 1
            name = f"tmp_{uid[0]}"
            r = run(con, f"CREATE TEMP TABLE {name} AS {select_sql}", timeout, widths, keep=False)
            cost = {k: r[k] for k in ZERO}
            if not r["ok"]:
                return None, 0, cost
            temps.append(name)
            # instrumentation (not charged): row count and column widths of the temp table
            n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            w = {}
            for cname, ty in con.execute("SELECT column_name, data_type FROM duckdb_columns() WHERE table_name=?", [name]).fetchall():
                base = ty.split("(")[0].upper()
                if base in FIXED_WIDTH:
                    w[cname.lower()] = FIXED_WIDTH[base]
                elif base == "DECIMAL":
                    w[cname.lower()] = 8
                else:
                    avg = con.execute(f'SELECT avg(strlen(CAST("{cname}" AS VARCHAR))) FROM {name}').fetchone()[0]
                    w[cname.lower()] = 4 + (avg or 0)
            widths[name] = w
            return name, n, cost

        for q in qs:
            rec = recs[q.seq]
            a = a_res[q.seq]
            c = {"mech": "miss", "exec_s": a["exec_s"], "fetch_s": a["fetch_s"], "rows_scanned": a["rows_scanned"],
                 "bytes": a["bytes"], "cpu_s": a["cpu_s"], "src": None, "cross_attempt": None, "valid": None}
            served = None
            wasted = dict(ZERO)
            eligible = rec["b"]["hit"] is None and q.ev["success"] and a["ok"]
            if rec["b"]["hit"] is not None:
                c.update(mech=rec["b"]["hit"], exec_s=0.0, fetch_s=0.0, rows_scanned=0, bytes=0.0, cpu_s=0.0,
                         src=rec["b"]["src"])
                c["cross_attempt"] = recs[rec["b"]["src"]]["attempt"] != q.attempt
            # 1) containment from cached results of earlier statements (smallest relation first)
            if eligible and q.block is not None:
                for v in sorted(rels.get(q.block.core, []), key=lambda x: x["n"]):
                    got = sr.containment_sql(q.block, v["block"], v["name"], v["n"])
                    if got is None:
                        continue
                    r = run(con, got[1], timeout, widths)
                    if r["ok"]:
                        c.update(mech="containment:" + got[0], exec_s=r["exec_s"], fetch_s=r["fetch_s"], cpu_s=r["cpu_s"],
                                 rows_scanned=v["n"] + r["rows_scanned"], bytes=v["nbytes"] + r["bytes"], src=v["seq"],
                                 cross_attempt=v["attempt"] != q.attempt, comp_sql=got[1])
                        served = r["tbl"]
                    else:
                        c["comp_error"] = r["error"]
                    break
            # 2) shared SPJ unit (inner join core + implied filter subset), materialized on second occurrence
            if eligible and served is None and pol["units"] and q.block is not None and not q.block.left and (
                    len(q.block.tables) >= 2 or q.block.filters):
                need = set(q.block.base_cols)
                u = None
                for x in units:
                    if (x["core"] == q.block.core and need <= x["cols"]
                            and implied_all(q.block.filters, list(x["filters"].items()))):
                        if u is None or x["n"] < u["n"]:
                            u = x
                mech, cost = "unit_reuse", dict(ZERO)
                if u is None:
                    cands = [(fd, bc, att) for (fd, bc, att, ca) in seen_blocks.get(q.block.core, [])
                             if implied_all(q.block.filters, list(fd.items())) and ca >= pol["min_prior_s"]]
                    if cands:
                        fbest = max(cands, key=lambda x: len(x[0]))[0]
                        if len(q.block.tables) >= 2 or fbest:
                            cols = set(need)
                            for (fd, bc, att, _) in seen_blocks.get(q.block.core, []):
                                if set(fd) >= set(fbest):
                                    cols |= bc
                            cols = sorted(cols)
                            items = sorted(fbest.items())
                            name, n, cost = materialize(unit_sql(q, items, cols))
                            mech = "unit_materialize"
                            if name is not None:
                                u = {"core": q.block.core, "filters": dict(items), "cols": set(cols), "name": name, "n": n,
                                     "block": unit_block(q.block, items, cols), "attempts": {att for (_, _, att) in cands}}
                                units.append(u)
                if u is not None:
                    got = sr.containment_sql(q.block, u["block"], u["name"], u["n"])
                    r = run(con, got[1], timeout, widths) if got is not None else None
                    if r is not None and r["ok"]:
                        tot = add(cost, r)
                        c.update(mech=mech, comp_sql=got[1], unit_rows=u["n"], mat_exec_s=cost["exec_s"],
                                 cross_attempt=bool(u["attempts"] - {q.attempt}), **tot)
                        served = r["tbl"]
                        u["attempts"].add(q.attempt)
                    else:
                        wasted = add(wasted, cost)
                else:
                    wasted = add(wasted, cost)
            # 3) filtered-scan substitution (any statement shape), materialized on second occurrence
            if eligible and served is None and pol["scans"] and q.scan_units:
                subst, cost, cross = {}, dict(ZERO), False
                for alias, table, conj in q.scan_units:
                    if alias in subst:
                        continue
                    need = {col.name for col in q.ast.find_all(exp.Column) if col.table == alias}
                    qconj = {s: P(s) for s in conj}
                    best = None
                    for (tb, cj), s in scans.items():
                        if (tb == table and s["useful"] and need <= s["cols"]
                                and implied_all(qconj, [(x, P(x)) for x in cj])):
                            if best is None or s["n"] < best["n"]:
                                best = s
                    if best is None:
                        cands = [(cj, cc, att) for (cj, cc, att, ca) in seen_scans.get(table, [])
                                 if implied_all(qconj, [(x, P(x)) for x in cj]) and ca >= pol["min_prior_s"]]
                        if not cands:
                            continue
                        cbest = max(cands, key=lambda x: len(x[0]))[0]
                        prev = scans.get((table, cbest))
                        if prev is not None and not prev["useful"]:
                            continue
                        cols = set(need)
                        for (cj, cc, att, _) in seen_scans.get(table, []):
                            if set(cj) >= set(cbest):
                                cols |= cc
                        cols = sorted(cols)
                        ssql = (f'SELECT {", ".join(chr(34) + x + chr(34) for x in cols)} FROM "{table}" WHERE '
                                + " AND ".join(f"({x})" for x in cbest))
                        name, n, mc = materialize(ssql)
                        cost = add(cost, mc)
                        if name is None:
                            scans[(table, cbest)] = {"useful": False, "cols": set(cols), "name": None, "n": 0, "attempts": set()}
                            continue
                        s = {"useful": n <= 0.5 * nrows.get(table, 0), "cols": set(cols), "name": name, "n": n,
                             "attempts": {att for (_, _, att) in cands}}
                        scans[(table, cbest)] = s
                        if not s["useful"]:
                            continue
                        best = s
                    subst[alias] = best
                    cross = cross or bool(best["attempts"] - {q.attempt})
                if subst:
                    ast2 = q.ast.copy()
                    for t in list(ast2.find_all(exp.Table)):
                        if t.alias_or_name in subst:
                            t.replace(exp.Table(this=exp.to_identifier(subst[t.alias_or_name]["name"]),
                                                alias=exp.TableAlias(this=exp.to_identifier(t.alias_or_name))))
                    ssql = sr.sql_of(ast2)
                    r = run(con, ssql, timeout, widths)
                    if r["ok"]:
                        tot = add(cost, r)
                        c.update(mech="scan_subst", comp_sql=ssql, cross_attempt=cross, mat_exec_s=cost["exec_s"], **tot)
                        served = r["tbl"]
                        for s in subst.values():
                            s["attempts"].add(q.attempt)
                    else:
                        c["comp_error"] = r["error"]
                        wasted = add(wasted, cost)
                else:
                    wasted = add(wasted, cost)
            if served is None and wasted["exec_s"] > 0:
                c["wasted_materialization"] = wasted
                for k in ZERO:
                    c[k] += wasted[k]
            if served is not None:
                sig = signature(served)
                c["valid"] = (sig == rec["a_sig"]) if rec["a_sig"] is not None else None
            rec[pname] = c
            # bookkeeping for later statements (the statement's own result is cached; it was computed anyway)
            if a["ok"] and q.ev["success"] and q.block is not None:
                seen_blocks[q.block.core].append((q.block.filters, set(q.block.base_cols), q.attempt, a["exec_s"]))
                if a["tbl"] is not None and a["n_rows"] <= CACHE_ROW_CAP:
                    rt = as_relation(a["tbl"])
                    rels[q.block.core].append({"block": q.block, "name": register(rt), "n": rt.num_rows,
                                               "nbytes": rt.nbytes, "seq": q.seq, "attempt": q.attempt})
            if a["ok"] and q.ev["success"]:
                for alias, table, conj in q.scan_units:
                    need = {col.name for col in q.ast.find_all(exp.Column) if col.table == alias}
                    seen_scans[table].append((conj, need, q.attempt, a["exec_s"]))
        for name in registered:
            try:
                con.unregister(name)
            except Exception:
                pass
        for name in temps:
            con.execute(f"DROP TABLE IF EXISTS {name}")
            widths.pop(name, None)

    for pname, pol in POLICIES.items():
        simulate(pname, pol)
    for q in qs:
        a_res[q.seq]["tbl"] = None
    return [recs[q.seq] for q in qs]


def shared_subexpr_analysis(qs):
    """Analysis-only: does a statement share a join sub-tree (>=2 tables) or a filtered scan with an
    earlier statement of the same task (any attempt / another attempt)?"""
    out = {}
    seen_bare, seen_filt, seen_scan = {}, {}, {}
    for q in qs:
        bare, filt = sr.join_subtrees(q.block) if q.block is not None else (set(), set())
        scans = {(t, cj) for (_, t, cj) in q.scan_units} if (q.qual_ok and q.alias_ok) else set()
        res = {"join_bare": False, "join_bare_x": False, "join_filt": False, "join_filt_x": False,
               "scan": False, "scan_x": False}
        for key, seen, f, fx in ((bare, seen_bare, "join_bare", "join_bare_x"), (filt, seen_filt, "join_filt", "join_filt_x"),
                                 (scans, seen_scan, "scan", "scan_x")):
            for k in key:
                if k in seen:
                    res[f] = True
                    if seen[k] - {q.attempt}:
                        res[fx] = True
        out[q.seq] = res
        if q.ev["success"]:
            for key, seen in ((bare, seen_bare), (filt, seen_filt), (scans, seen_scan)):
                for k in key:
                    seen.setdefault(k, set()).add(q.attempt)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--max-attempts", type=int, default=0)
    ap.add_argument("--dbs", default="")
    ap.add_argument("--limit-tasks", type=int, default=0)
    args = ap.parse_args()
    evs = [json.loads(l) for l in open(args.trace)]
    if args.max_attempts:
        evs = [e for e in evs if e["attempt"] < args.max_attempts]
    by_db = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in evs:
        by_db[e["db_id"]][e["task_id"]].append(e)
    dbs = [d for d in sorted(by_db) if not args.dbs or d in args.dbs.split(",")]
    rng = random.Random(0)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        for db in dbs:
            t0 = time.time()
            con, widths, schema_lc, nrows = load_db(db, args.scale, args.threads)
            print(db, "loaded in", round(time.time() - t0, 1), "s", flush=True)
            tasks = sorted(by_db[db])
            if args.limit_tasks:
                tasks = tasks[: args.limit_tasks]
            for tid in tasks:
                ts = sorted(by_db[db][tid], key=lambda e: (e["turn"], e["attempt"], e["seq"]))
                qs = [Q(e, schema_lc) for e in ts]
                recs = replay_task(con, qs, widths, nrows, args.timeout, rng)
                sse = shared_subexpr_analysis(qs)
                for r in recs:
                    r["sse"] = sse[r["seq"]]
                    r["scale"] = args.scale
                    f.write(json.dumps(r, default=str) + "\n")
                f.flush()
                ta = sum(r["a"]["exec_s"] for r in recs)
                tc = sum(r["c"]["exec_s"] for r in recs)
                print(f"  {tid}: n={len(recs)} a={ta:.3f}s c={tc:.3f}s mechs={collections.Counter(r['c']['mech'] for r in recs)}", flush=True)
            con.close()
            print(db, "done in", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
