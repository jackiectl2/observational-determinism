#!/bin/bash
# Third pass (after run_replays2.sh): single-threaded DuckDB sensitivity run (throughput-bound deployment where
# concurrent attempts each get one core), with profiler CPU time logged.
set -uo pipefail
cd ${PROJECT_ROOT}/code/pilot_c3
source ../../env.sh
R=../../runs/pilot_c3
until [ -f $R/replay/ALL_DONE2 ]; do sleep 20; done
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf10_t1.jsonl --scale 10 --threads 1 > $R/replay/k8_sf10_t1.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf100_part_t1.jsonl --scale 100 --threads 1 \
  --dbs thrombosis_prediction,formula_1,debit_card_specializing,california_schools,card_games > $R/replay/k8_sf100_part_t1.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf30_codebase_t1.jsonl --scale 30 --threads 1 \
  --dbs codebase_community > $R/replay/k8_sf30_codebase_t1.log 2>&1
echo ALL_DONE > $R/replay/ALL_DONE3
