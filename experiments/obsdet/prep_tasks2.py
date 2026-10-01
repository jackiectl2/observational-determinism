"""E4 task list: the 66 pilot tasks plus new BIRD dev tasks (fixed before any agent run).

Selection rule (unchanged from the pilot): gold SQL (SQLite dialect) transpiled with sqlglot to DuckDB runs
on the DuckDB conversion and returns 1..200 rows. New tasks are drawn with a seed from databases not used
in the pilot plus extra tasks from the pilot databases, excluding the pilot tasks.

Usage: python prep_tasks2.py <pilot_tasks.json> <out.json>
"""
import collections
import json
import os
import random
import sys

import sqlglot

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import DEV_JSON, db_path, open_db, execute_with_timeout, canon_rows  # noqa: E402

PLAN = {"student_club": 16, "superhero": 16, "toxicology": 16, "european_football_2": 10, "financial": 10,
        "codebase_community": 4, "card_games": 4, "formula_1": 4, "california_schools": 2,
        "debit_card_specializing": 1, "thrombosis_prediction": 1}


def main(pilot_path, out_path, seed=1):
    pilot = json.load(open(pilot_path))
    used = {t["task_id"] for t in pilot}
    dev = json.load(open(DEV_JSON))
    rng = random.Random(seed)
    chosen, stats = list(pilot), collections.Counter()
    for db_id, n_want in PLAN.items():
        con = open_db(db_path(db_id))
        cands = [x for x in dev if x["db_id"] == db_id and f"{db_id}:{x['question_id']}" not in used]
        rng.shuffle(cands)
        picked = 0
        for x in cands:
            if picked >= n_want:
                break
            try:
                gold = sqlglot.transpile(x["SQL"], read="sqlite", write="duckdb")[0]
            except Exception:  # noqa: BLE001
                stats[(db_id, "transpile_fail")] += 1
                continue
            r = execute_with_timeout(con, gold, timeout_s=30, row_cap=1000)
            if not r["success"] or r["n_rows"] == 0 or r["n_rows"] > 200:
                stats[(db_id, "not_eligible")] += 1
                continue
            picked += 1
            chosen.append({"task_id": f"{db_id}:{x['question_id']}", "question_id": x["question_id"], "db_id": db_id,
                           "difficulty": x.get("difficulty"), "question": x["question"], "evidence": x.get("evidence", ""),
                           "gold_sql_sqlite": x["SQL"], "gold_sql_duckdb": gold,
                           "gold_rows": [list(t) for t in canon_rows(r["rows"])], "gold_runtime": r["runtime"],
                           "split": "new"})
        con.close()
        print(db_id, "picked", picked, "of", n_want, flush=True)
    json.dump(chosen, open(out_path, "w"), indent=1, default=str)
    print("total tasks", len(chosen), collections.Counter(t["db_id"] for t in chosen))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
