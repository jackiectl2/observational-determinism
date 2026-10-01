# Select BIRD dev (2025-11-06 release) tasks whose gold SQL runs on the DuckDB conversion.
# Gold SQL is SQLite dialect; it is transpiled with sqlglot (sqlite -> duckdb) and executed on the
# unscaled DuckDB file. Tasks whose gold fails, times out, or returns 0 / >200 rows are not eligible.
import argparse
import collections
import json
import random

import sqlglot

from common import DEV_JSON, db_path, open_db, execute_with_timeout, canon_rows

PLAN = {
    "codebase_community": 16,
    "card_games": 14,
    "formula_1": 14,
    "california_schools": 8,
    "debit_card_specializing": 8,
    "thrombosis_prediction": 6,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    dev = json.load(open(DEV_JSON))
    rng = random.Random(args.seed)
    chosen, stats = [], collections.Counter()
    for db_id, n_want in PLAN.items():
        con = open_db(db_path(db_id))
        cands = [x for x in dev if x["db_id"] == db_id]
        rng.shuffle(cands)
        picked = 0
        for x in cands:
            if picked >= n_want:
                break
            try:
                gold_duck = sqlglot.transpile(x["SQL"], read="sqlite", write="duckdb")[0]
            except Exception:
                stats[(db_id, "transpile_fail")] += 1
                continue
            r = execute_with_timeout(con, gold_duck, timeout_s=30, row_cap=1000)
            if not r["success"]:
                stats[(db_id, "gold_error")] += 1
                continue
            if r["n_rows"] == 0 or r["n_rows"] > 200:
                stats[(db_id, "gold_rows_out_of_range")] += 1
                continue
            stats[(db_id, "ok")] += 1
            picked += 1
            chosen.append({
                "task_id": f"{db_id}:{x['question_id']}",
                "question_id": x["question_id"],
                "db_id": db_id,
                "difficulty": x.get("difficulty"),
                "question": x["question"],
                "evidence": x.get("evidence", ""),
                "gold_sql_sqlite": x["SQL"],
                "gold_sql_duckdb": gold_duck,
                "gold_rows": [list(t) for t in canon_rows(r["rows"])],
                "gold_runtime": r["runtime"],
            })
        con.close()
        print(db_id, "picked", picked, "of", n_want, flush=True)
    with open(args.out, "w") as f:
        json.dump(chosen, f, indent=1, default=str)
    print("total tasks", len(chosen))
    print("difficulty", collections.Counter(t["difficulty"] for t in chosen))
    for k, v in sorted(stats.items()):
        print(k, v)


if __name__ == "__main__":
    main()
