"""E1 soundness replay: does each observation policy give the same agent-visible preview across equivalent
DuckDB executions?

Policies: raw (query as issued), smartlex (existing ORDER BY, then every output column), certified (DET:
unchanged; NARROW/ALL: rewritten; UNSUPPORTED: smart-lex fallback, reported separately).
Configurations: original / permuted (seeds 42, 7) physical order x 1 / 8 threads, plus a repeated
8-thread run; every configuration is a private in-memory instance (its own thread setting).
Observation = the study's tool (tool.py: exact row count, canonical signed zero) with the C3 rendering
(header, first 20 rows, row count), compared as text. A probe/policy is censored unless all 7 runs succeed.

Usage: python replay_sound.py <cert_probes.jsonl> <out.jsonl>
"""
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

V = os.environ["PROJECT_ROOT"]
sys.path.insert(0, f"{V}/code/pilot_c3")
sys.path.insert(0, f"{V}/code/pilot_r2_1")
from common import db_path  # noqa: E402
from agent_c3 import observation  # noqa: E402
import observe as ob  # noqa: E402
import tool  # noqa: E402

CONFIGS = [("orig_t1", None, 1), ("orig_t8a", None, 8), ("orig_t8b", None, 8), ("p42_t1", 42, 1),
           ("p42_t8", 42, 8), ("p7_t1", 7, 1), ("p7_t8", 7, 8)]


def path_of(db, seed):
    return db_path(db) if seed is None else f"{V}/data/pilot_r2_1/{db}_perm{seed}.duckdb"


def main(cert_path, out_path):
    probes = [json.loads(l) for l in open(cert_path)]
    probes = [p for p in probes if "exec_error" not in p]
    by_db = defaultdict(list)
    for p in probes:
        by_db[p["db_id"]].append(p)
    out = open(out_path, "w")
    summ = Counter()
    for db, ps in sorted(by_db.items()):
        cons = {name: ob.open_instance(path_of(db, seed), threads) for name, seed, threads in CONFIGS}
        for p in ps:
            sqls = {"raw": p["sql"], "smartlex": p.get("smartlex") or p["sql"],
                    "certified": (p["rewritten"] or p["sql"]) if p["verdict"] != "UNSUPPORTED"
                    else (p.get("smartlex") or p["sql"])}
            rec = {"db_id": db, "sql": p["sql"], "verdict": p["verdict"], "occurrences": p["occurrences"], "policies": {}}
            for pol, q in sqls.items():
                hashes, errs, times = [], 0, []
                for name, _, _ in CONFIGS:
                    r = tool.run(cons[name], q, 20.0)
                    if not r["success"] or r["truncated"]:
                        errs += 1
                        continue
                    hashes.append(hashlib.sha1(observation(r, ob.K).encode()).hexdigest())
                    times.append(r["runtime"])
                # divergence is defined only when every configuration produced an observation; otherwise censored
                complete = len(hashes) == len(CONFIGS)
                rec["policies"][pol] = {"diverged": (len(set(hashes)) > 1) if complete else None, "n_ok": len(hashes),
                                        "n_err": errs, "median_s": sorted(times)[len(times) // 2] if times else None}
                summ[(pol, p["verdict"], rec["policies"][pol]["diverged"])] += 1
            out.write(json.dumps(rec) + "\n")
        for c in cons.values():
            c.close()
        print(db, "done", flush=True)
    out.close()
    print("\npolicy x verdict: diverged / complete (censored: not observed in every configuration)")
    for pol in ("raw", "smartlex", "certified"):
        for v in ("DET", "NARROW", "ALL", "UNSUPPORTED"):
            d, n = summ[(pol, v, True)], summ[(pol, v, True)] + summ[(pol, v, False)]
            print(f"  {pol:9s} {v:11s} {d}/{n}  censored {summ[(pol, v, None)]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
