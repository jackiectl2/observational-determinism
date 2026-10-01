"""Can an agent statement change what a later certificate relies on in the E4 tool instance (observe.open_instance: a
writable in-memory copy, on which SET reaches every later cursor)? Each scenario runs, in its own process, the
harness's run_statement: the scenario's statements under the raw policy, then a query under certified and strict.
A certificate is unsound if the certified query returns rows other than on an untouched instance.
Usage: python readonly_tool_check.py <code dir: tool.py, certify.py, agent_det3.py> <db_file> <out.json>"""
import json
import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_r2_1")
from observe import open_instance  # noqa: E402

Q = "SELECT Id, DisplayName FROM users ORDER BY Id LIMIT 3"
SCENARIOS = {  # name: (statements, query)
    "replace-table": (["CREATE OR REPLACE TABLE users AS SELECT * FROM users UNION ALL SELECT * FROM users"], Q),
    "insert-duplicate": (["INSERT INTO users SELECT * FROM users WHERE Id = -1"], Q),
    "set-collation": (["SET default_collation='nocase'"], "SELECT DisplayName FROM users ORDER BY DisplayName LIMIT 5"),
    "set-null-order": (["SET default_null_order='nulls_first'"], "SELECT Id, Location FROM users ORDER BY Location, Id LIMIT 3"),
    "attach+qualified": (["ATTACH ':memory:' AS m", "CREATE TABLE m.users AS SELECT * FROM users UNION ALL SELECT * FROM users"],
                         "SELECT Id, DisplayName FROM m.users ORDER BY Id LIMIT 3"),
    "metadata": (["PRAGMA table_info(users)", "DESCRIBE users", "SHOW TABLES"], Q),
}


def scenario(code_dir, db_file, stmts, query, out):
    sys.path.insert(0, code_dir)
    import certify  # noqa: E402,F401  (the versions in code_dir, cached before agent_det3 extends sys.path)
    import tool  # noqa: E402
    import agent_det3 as h  # noqa: E402
    assert h.tool is tool
    con = open_instance(db_file, 1)
    res = {"steps": []}
    for s in stmts:
        r = h.run_statement(con, s, "raw", 20.0, "codebase_community")[0]
        res["steps"].append({"sql": s, "success": r["success"], "error": (r.get("error") or "")[:120]})
    for mode in ("certified", "strict"):
        r, _, _, meta = h.run_statement(con, query, mode, 20.0, "codebase_community")
        res[mode] = {"verdict": meta.get("verdict"), "reason": meta.get("reason"), "refused": meta.get("refused", False),
                     "rows": [list(x) for x in r["rows"]]}
    out.put(res)


def main(code_dir, db_file, out_path):
    fresh = open_instance(db_file, 1)
    # the catalog's table is what a certificate is about, also for the attached copy named explicitly
    truth = {q: [list(x) for x in fresh.execute(q.replace("FROM m.users", "FROM users")).fetchall()]
             for _, q in SCENARIOS.values()}
    ctx = mp.get_context("spawn")
    report, unsound = {}, 0
    for name, (stmts, query) in SCENARIOS.items():
        q = ctx.Queue()
        p = ctx.Process(target=scenario, args=(code_dir, db_file, stmts, query, q))
        p.start()
        res = q.get(timeout=300)
        p.join()
        for mode in ("certified", "strict"):
            m = res[mode]
            m["certified"] = m["verdict"] in ("DET", "NARROW", "ALL")
            m["unsound"] = m["certified"] and not m["refused"] and m["rows"] != truth[query]
            unsound += m["unsound"]
        report[name] = res
        print(name, json.dumps({"steps": [(s["success"], s["error"][:60]) for s in res["steps"]],
                                **{k: {kk: res[k][kk] for kk in ("verdict", "reason", "refused", "unsound")}
                                   for k in ("certified", "strict")}}))
    report["unsound_certificates"] = unsound
    json.dump(report, open(out_path, "w"), indent=1)
    print("unsound_certificates", unsound)


if __name__ == "__main__":
    main(*sys.argv[1:])
