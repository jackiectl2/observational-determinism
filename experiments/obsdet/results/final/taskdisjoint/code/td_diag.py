"""Diagnosis of certified statements whose tool observation changed across equivalent executions in the
task-disjoint E4 runs (found by the analyze3 attribution). For each statement: the frozen certificate, DuckDB's
result type of the relevant expression or its plan, and the observation under the 7 replay_sound.py configurations.

Usage: python td_diag.py <statements.json>   (a list of {"db_id", "sql"})
"""
import json
import os
import sys

import duckdb

from certify import certify
from replay_sound import CONFIGS, path_of
import observe as ob
import tool
from agent_c3 import observation

CAT = json.load(open(os.environ["PROJECT_ROOT"] + "/runs/obsdet/catalog.json"))
PROBES = ["SELECT typeof(CAST(1 AS DECIMAL(18, 6)) / 365.25)",
          "SELECT typeof(CAST(1 AS DECIMAL(18, 6)) / CAST(3 AS DECIMAL(18, 6)))",
          "SELECT typeof(AVG(CAST(1 AS DECIMAL(18, 6)) / 365.25))",
          "SELECT typeof(AVG(CAST(1 AS DECIMAL(18, 6))))"]


def main(path):
    print("duckdb", duckdb.__version__)
    con = duckdb.connect()
    for q in PROBES:
        print(q, "->", con.execute(q).fetchone()[0])
    for s in json.load(open(path)):
        cert = certify(s["sql"], CAT[s["db_id"]], "duckdb")
        q = cert.rewritten or s["sql"]
        print("\n==", s["db_id"], "|", s["sql"])
        print("certificate:", cert.verdict, "|", cert.reason, "| tie-break", cert.tie_break, "| executed:", q)
        base = ob.open_instance(path_of(s["db_id"], None), 1)
        print("plan:", " / ".join(r[1] for r in base.execute("EXPLAIN " + q).fetchall())[:1500].replace("\n", " "))
        base.close()
        for name, seed, threads in CONFIGS:
            c = ob.open_instance(path_of(s["db_id"], seed), threads)
            r = tool.run(c, q, 20.0)
            print(f"  {name:9s}", observation(r, ob.K).replace("\n", " | ")[:200])
            c.close()


if __name__ == "__main__":
    main(sys.argv[1])
