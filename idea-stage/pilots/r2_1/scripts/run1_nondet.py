# Run 1 (no prompt de-duplication): identical turn-1 prompts across the 7 conditions -> did greedy vLLM
# produce the same first SQL? Measures LLM-serving nondeterminism (batch variance), independent of the DB.
import collections
import itertools
import json
import os
import sys

R = os.environ["PROJECT_ROOT"] + "/runs/pilot_r2_1"
tr = [json.loads(l) for l in open(f"{R}/agent_greedy/trace.jsonl")]
t1 = collections.defaultdict(dict)
for t in tr:
    if t["turn"] == 1:
        t1[t["task_id"]][t["cond"]] = t["sql"]
conds = sorted({c for v in t1.values() for c in v})
n = len(t1)
differ = sum(len(set(v.values())) > 1 for v in t1.values())
pair = [sum(v.get(a) != v.get(b) for v in t1.values()) / n for a, b in itertools.combinations(conds, 2)]
out = {"n_tasks": n, "tasks_turn1_sql_differs_across_7_identical_prompts": differ,
       "frac": differ / n, "mean_pairwise_frac": sum(pair) / len(pair), "max_pairwise_frac": max(pair)}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(out)
