"""The exact-count path of the tool (proof blind review 2, BR-02). A result longer than the fetch cap is counted with
SELECT count(*) FROM (sql); a trailing line comment in sql used to swallow the closing parenthesis, and a failed count
left the call successful without the exact count. Runs each tool on the E4 instance of codebase_community (comments
has more than 100,000 rows), once as is and once with every count query failing.
Usage: python count_path_check.py <old tool.py> <new tool.py> <db_file> <out.json>"""
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_r2_1")
from observe import open_instance  # noqa: E402

CASES = ["SELECT Id FROM comments ORDER BY Id -- trailing comment", "SELECT Id FROM comments ORDER BY Id"]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(old_path, new_path, db_file, out_path):
    con = open_instance(db_file, 1)
    exact = con.execute("SELECT count(*) FROM comments").fetchone()[0]
    report = {"exact_count": exact, "runs": []}
    for label, path in (("old", old_path), ("new", new_path)):
        tool = load(path, f"tool_{label}")
        real = tool.execute_with_timeout
        for failing in (False, True):
            def fake(c, sql, timeout, _real=real):
                if sql.lstrip().upper().startswith("SELECT COUNT(*)"):
                    return {"success": False, "error": "simulated count failure", "rows": [], "columns": [],
                            "n_rows": 0, "truncated": False, "timeout": False, "runtime": 0.0}
                return _real(c, sql, timeout)
            tool.execute_with_timeout = fake if failing else real
            for sql in CASES:
                r = tool.run(con, sql, 60.0)
                row = {"tool": label, "count_fails": failing, "sql": sql, "success": r["success"],
                       "truncated": r["truncated"], "n_rows": r["n_rows"], "exact_count": r.get("exact_count"),
                       "error": (r.get("error") or "")[:100]}
                # the contract's observation: either the call fails, or it reports the exact count
                row["ok"] = (not r["success"]) or (r["n_rows"] == exact and not r["truncated"])
                report["runs"].append(row)
                print(json.dumps(row))
            tool.execute_with_timeout = real
    report["violations"] = {lab: sum(not x["ok"] for x in report["runs"] if x["tool"] == lab) for lab in ("old", "new")}
    json.dump(report, open(out_path, "w"), indent=1)
    print("violations", report["violations"])


if __name__ == "__main__":
    main(*sys.argv[1:])
