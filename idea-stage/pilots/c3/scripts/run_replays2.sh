#!/bin/bash
# Second pass (after run_replays.sh): re-run the K=8 replays with materialization cost logged separately.
set -uo pipefail
cd ${PROJECT_ROOT}/code/pilot_c3
source ../../env.sh
R=../../runs/pilot_c3
until [ -f $R/replay/ALL_DONE ]; do sleep 20; done
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf10_v2.jsonl --scale 10 > $R/replay/k8_sf10_v2.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf100_part_v2.jsonl --scale 100 \
  --dbs thrombosis_prediction,formula_1,debit_card_specializing,california_schools,card_games > $R/replay/k8_sf100_part_v2.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf30_codebase_v2.jsonl --scale 30 \
  --dbs codebase_community > $R/replay/k8_sf30_codebase_v2.log 2>&1
echo ALL_DONE > $R/replay/ALL_DONE2
