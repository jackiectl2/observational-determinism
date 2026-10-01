"""Can an agent statement make a later certified preview read a relation other than the catalog's (proof blind review
BR-01)? Each scenario runs, in its own process, the harness's run_statement on a read-only BIRD database: a certified
query, then the scenario's raw statements, then a query under certified and strict. A certificate is unsound if the
certified query returns rows other than the catalog table's. The shadowing table has duplicate keys. The last
scenario names the attached table explicitly (other.users), which the final certifier rejects as unknown-table.
Usage: python namespace_guard_check.py <code dir: tool.py, certify.py, agent_det3.py> <duck_dir> <out.json>"""
import json
import multiprocessing as mp
import os
import sys

import duckdb

Q = "SELECT Id, DisplayName FROM users ORDER BY Id LIMIT 3"
SHADOW = "SELECT 1 AS Id, 'a' AS DisplayName UNION ALL SELECT 1, 'b' UNION ALL SELECT 0, 'c'"


def scenario(code_dir, db, other, stmts, query, out):
    sys.path.insert(0, code_dir)
    import certify  # noqa: E402,F401  (the versions in code_dir, cached before agent_det3 extends sys.path)
    import tool  # noqa: E402
    import agent_det3 as h  # noqa: E402
    assert h.tool is tool
    con = duckdb.connect(db, read_only=True)
    res = {"fresh": h.run_statement(con, Q, "certified", 20.0, "codebase_community")[3].get("verdict"), "steps": []}
    for s in stmts:
        r = h.run_statement(con, s.format(other=other), "raw", 20.0, "codebase_community")[0]
        res["steps"].append({"sql": s, "success": r["success"], "error": (r.get("error") or "")[:120]})
    for mode in ("certified", "strict"):
        r, _, _, meta = h.run_statement(con, query, mode, 20.0, "codebase_community")
        res[mode] = {"verdict": meta.get("verdict"), "reason": meta.get("reason"), "refused": meta.get("refused", False),
                     "rows": [list(x) for x in r["rows"]]}
    out.put(res)


def main(code_dir, duck_dir, out_path):
    db = f"{duck_dir}/codebase_community.duckdb"
    truth = [list(x) for x in duckdb.connect(db, read_only=True).execute(Q).fetchall()]
    other = f"/tmp/{os.environ.get('USER', 'u')}-nsguard-{os.getpid()}.duckdb"
    w = duckdb.connect(other)
    w.execute(f"CREATE TABLE users AS {SHADOW}")
    w.close()
    scenarios = {
        "temp-table": [f"CREATE TEMP TABLE users AS {SHADOW}"],
        "attach": ["ATTACH '{other}' AS other (READ_ONLY)"],
        "attach+use": ["ATTACH '{other}' AS other (READ_ONLY)", "USE other"],
        "attach+global-search-path": ["ATTACH '{other}' AS other (READ_ONLY)", "SET GLOBAL search_path = 'other.main'"],
        "attach+global-schema": ["ATTACH '{other}' AS other (READ_ONLY)", "SET GLOBAL schema = 'other.main'"],
        "metadata": ["PRAGMA table_info(users)"],
        "attach+qualified-query": ["ATTACH '{other}' AS other (READ_ONLY)"],
    }
    queries = {"attach+qualified-query": Q.replace("FROM users", "FROM other.users")}
    ctx = mp.get_context("spawn")
    report, unsound = {"truth": truth}, 0
    for name, stmts in scenarios.items():
        q = ctx.Queue()
        p = ctx.Process(target=scenario, args=(code_dir, db, other, stmts, queries.get(name, Q), q))
        p.start()
        res = q.get(timeout=300)
        p.join()
        for mode in ("certified", "strict"):
            m = res[mode]
            m["certified"] = m["verdict"] in ("DET", "NARROW", "ALL")
            m["unsound"] = m["certified"] and not m["refused"] and m["rows"] != truth
            unsound += m["unsound"]
        report[name] = res
        print(name, json.dumps(res))
    report["unsound_certificates"] = unsound
    json.dump(report, open(out_path, "w"), indent=1)
    os.remove(other)
    print("unsound_certificates", unsound)


if __name__ == "__main__":
    main(*sys.argv[1:])
