"""Strict-policy burden from an E4 run: tasks with at least one withheld preview (strict, original order, 1 thread),
the median number withheld among them, and how their correctness compares with the hybrid policy.

Usage: python strict_burden.py <e4_run_dir> ...
"""
import json
import statistics
import sys
from collections import defaultdict


def main(*dirs):
    for d in dirs:
        ref, tasks, att = defaultdict(int), set(), {}
        for line in open(f"{d}/trace.jsonl"):
            r = json.loads(line)
            if r["cond"] == "str_orig_t1":
                tasks.add(r["task_id"])
                ref[r["task_id"]] += bool(r["meta"].get("refused"))
        for line in open(f"{d}/attempts.jsonl"):
            a = json.loads(line)
            att[(a["cond"], a["task_id"])] = a["correct"]
        aff = [t for t in tasks if ref[t]]
        lost = sum(att[("cer_orig_t1", t)] and not att[("str_orig_t1", t)] for t in aff)
        gained = sum(att[("str_orig_t1", t)] and not att[("cer_orig_t1", t)] for t in aff)
        print(f"{d}: {len(aff)}/{len(tasks)} tasks with >=1 withheld preview; median {statistics.median(ref[t] for t in aff)}"
              f" (max {max(ref[t] for t in aff)}) among them; hybrid-correct -> strict-wrong {lost}, "
              f"hybrid-wrong -> strict-correct {gained}")


if __name__ == "__main__":
    main(*sys.argv[1:])
