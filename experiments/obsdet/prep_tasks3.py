"""Task-disjoint E4 replication: 150 new BIRD dev tasks, disjoint from tasks_v2 (fixed before any agent run).

Selection rule (unchanged from prep_tasks.py / prep_tasks2.py): gold SQL (SQLite dialect) transpiled with sqlglot
to DuckDB runs on the DuckDB conversion (30 s timeout, row cap 1,000) and returns 1..200 rows.
Stratification: the per-database counts of tasks_v2. Candidates of a database exclude every tasks_v2 question_id
and every question whose question text or gold SQL (lower-cased, whitespace-collapsed) equals that of a tasks_v2
task of the same database. Databases are processed in sorted order with one random.Random(SEED); each database's
candidates are sorted by question_id, shuffled, and the first eligible ones are taken. A database with too few
eligible candidates keeps all of them; the shortfall is filled one task per database, continuing each database's
shuffled order, from the databases with the largest tasks_v2 counts first (largest remainder of the tasks_v2
shares; ties by name), so that the list has as many tasks as tasks_v2.

Also verifies the seed-42 / seed-7 physical-order copies that agent_det3.py opens: same tables, same row counts,
same multiset of rows (EXCEPT ALL), and whether the first 20 rows in physical (rowid) order differ.

Usage: python prep_tasks3.py <tasks_v2.json> <out_tasks.json> <out_note.json>
"""
import collections
import hashlib
import json
import os
import random
import sys

import duckdb
import sqlglot

sys.path.insert(0, os.environ["PROJECT_ROOT"] + "/code/pilot_c3")
from common import DEV_JSON, db_path, open_db, execute_with_timeout, canon_rows  # noqa: E402

SEED = 2
PERM_DIR = os.environ["PROJECT_ROOT"] + "/data/pilot_r2_1"


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def norm(s):
    return " ".join((s or "").lower().split()).rstrip(";").strip()


def qi(s):
    return '"' + s.replace('"', '""') + '"'


def select(v2, dev):
    plan = collections.Counter(t["db_id"] for t in v2)
    used_q = {t["question_id"] for t in v2}
    used_text = {(t["db_id"], norm(t["question"])) for t in v2}
    used_sql = {(t["db_id"], norm(t["gold_sql_sqlite"])) for t in v2}
    rng = random.Random(SEED)
    chosen, stats, pools, pos, cons, topup = [], collections.defaultdict(collections.Counter), {}, {}, {}, []

    def take(db_id, n):
        """Continue db_id's shuffled candidate order until n more eligible tasks are picked or it runs out."""
        picked = 0
        while picked < n and pos[db_id] < len(pools[db_id]):
            x = pools[db_id][pos[db_id]]
            pos[db_id] += 1
            stats[db_id]["examined"] += 1
            try:
                gold = sqlglot.transpile(x["SQL"], read="sqlite", write="duckdb")[0]
            except Exception:  # noqa: BLE001
                stats[db_id]["transpile_fail"] += 1
                continue
            r = execute_with_timeout(cons[db_id], gold, timeout_s=30, row_cap=1000)
            if not r["success"]:
                stats[db_id]["gold_error"] += 1
                continue
            if r["n_rows"] == 0 or r["n_rows"] > 200:
                stats[db_id]["gold_rows_out_of_range"] += 1
                continue
            picked += 1
            chosen.append({"task_id": f"{db_id}:{x['question_id']}", "question_id": x["question_id"], "db_id": db_id,
                           "difficulty": x.get("difficulty"), "question": x["question"], "evidence": x.get("evidence", ""),
                           "gold_sql_sqlite": x["SQL"], "gold_sql_duckdb": gold,
                           "gold_rows": [list(t) for t in canon_rows(r["rows"])], "gold_runtime": r["runtime"],
                           "split": "td"})
        stats[db_id]["picked"] += picked
        return picked

    for db_id in sorted(plan):
        cands = []
        for x in sorted((x for x in dev if x["db_id"] == db_id), key=lambda x: x["question_id"]):
            if x["question_id"] in used_q:
                stats[db_id]["in_tasks_v2"] += 1
            elif (db_id, norm(x["question"])) in used_text or (db_id, norm(x["SQL"])) in used_sql:
                stats[db_id]["same_text_or_gold_as_tasks_v2"] += 1
            else:
                cands.append(x)
        stats[db_id]["candidates"] = len(cands)
        rng.shuffle(cands)
        pools[db_id], pos[db_id], cons[db_id] = cands, 0, open_db(db_path(db_id))
        stats[db_id]["wanted"] = plan[db_id]
        take(db_id, plan[db_id])
        print(db_id, "picked", stats[db_id]["picked"], "of", plan[db_id], dict(stats[db_id]), flush=True)
    deficit = sum(plan.values()) - len(chosen)
    for db_id in sorted(plan, key=lambda d: (-plan[d], d)):
        if deficit == 0:
            break
        if take(db_id, 1):
            deficit -= 1
            topup.append(chosen[-1]["task_id"])
            print("top-up", chosen[-1]["task_id"], flush=True)
    assert deficit == 0, deficit
    for con in cons.values():
        con.close()
    return chosen, plan, stats, topup


def check_perm(dbs):
    out = {}
    for db in dbs:
        for seed in (42, 7):
            p = f"{PERM_DIR}/{db}_perm{seed}.duckdb"
            rec = {"path": p, "exists": os.path.exists(p)}
            out[f"{db}_perm{seed}"] = rec
            if not rec["exists"]:
                continue
            con = duckdb.connect()
            con.execute("SET threads=8")
            con.execute(f"ATTACH '{db_path(db)}' AS o (READ_ONLY)")
            con.execute(f"ATTACH '{p}' AS p (READ_ONLY)")
            tabs = {d: sorted(r[0] for r in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE database_name = ? AND schema_name = 'main'", [d]).fetchall())
                for d in ("o", "p")}
            rec["same_tables"] = tabs["o"] == tabs["p"]
            rec["n_tables"] = len(tabs["o"])
            rec["count_mismatch"], rec["multiset_mismatch"], rec["order_differs"], rec["tables_ge2_rows"] = [], [], 0, 0
            for t in tabs["o"]:
                n_o = con.execute(f"SELECT count(*) FROM o.{qi(t)}").fetchone()[0]
                n_p = con.execute(f"SELECT count(*) FROM p.{qi(t)}").fetchone()[0]
                if n_o != n_p:
                    rec["count_mismatch"].append(t)
                    continue
                extra = con.execute(f"SELECT count(*) FROM (SELECT * FROM o.{qi(t)} EXCEPT ALL SELECT * FROM p.{qi(t)})").fetchone()[0]
                if extra:
                    rec["multiset_mismatch"].append(t)
                if n_o >= 2:
                    rec["tables_ge2_rows"] += 1
                    first = [con.execute(f"SELECT * FROM {d}.{qi(t)} ORDER BY rowid LIMIT 20").fetchall() for d in ("o", "p")]
                    rec["order_differs"] += first[0] != first[1]
            con.close()
            rec["ok"] = rec["same_tables"] and not rec["count_mismatch"] and not rec["multiset_mismatch"]
            print(f"{db}_perm{seed}: {rec}", flush=True)
    return out


def main(v2_path, out_path, note_path):
    v2 = json.load(open(v2_path))
    dev = json.load(open(DEV_JSON))
    chosen, plan, stats, topup = select(v2, dev)
    assert not {t["question_id"] for t in chosen} & {t["question_id"] for t in v2}
    json.dump(chosen, open(out_path, "w"), indent=1, default=str)
    perm = check_perm(sorted(plan))
    note = {"seed": SEED, "script": os.path.abspath(__file__), "script_md5": md5(__file__),
            "dev_json": DEV_JSON, "dev_json_md5": md5(DEV_JSON), "tasks_v2": os.path.abspath(v2_path),
            "tasks_v2_md5": md5(v2_path), "procedure": __doc__.strip(),
            "per_db_target": dict(sorted(plan.items())),
            "per_db_picked": dict(sorted(collections.Counter(t["db_id"] for t in chosen).items())),
            "per_db_stats": {d: dict(s) for d, s in sorted(stats.items())}, "topup": topup,
            "difficulty_v3": dict(collections.Counter(t["difficulty"] for t in chosen)),
            "difficulty_v2": dict(collections.Counter(t["difficulty"] for t in v2)),
            "n_tasks": len(chosen), "shared_question_ids_with_v2": 0,
            "tasks_v3": os.path.abspath(out_path), "tasks_v3_md5": md5(out_path),
            "task_ids": [t["task_id"] for t in chosen], "perm_copies": perm,
            "perm_all_ok": all(r.get("ok") for r in perm.values())}
    json.dump(note, open(note_path, "w"), indent=1)
    print("total tasks", len(chosen), note["per_db_picked"])
    print("difficulty v3", note["difficulty_v3"], "| v2", note["difficulty_v2"])
    print("tasks_v3 md5", note["tasks_v3_md5"], "| perm copies all ok:", note["perm_all_ok"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
