#!/bin/bash
# Sequential CPU pipeline for pilot C3 (run inside the CPU holder allocation via srun --overlap).
set -uo pipefail
cd ${PROJECT_ROOT}/code/pilot_c3
source ../../env.sh
R=../../runs/pilot_c3
mkdir -p $R/replay $R/scaled_build
# larger scale: SF100 for five DBs, SF30 for codebase_community (SF100 would not fit in memory)
for db in thrombosis_prediction formula_1 debit_card_specializing california_schools card_games; do
  [ -f ../../data/pilot_c3_scaled/${db}_x100.duckdb ] || python build_scaled.py --db $db --sf 100
done >> $R/scaled_build/build_large.log 2>&1
[ -f ../../data/pilot_c3_scaled/codebase_community_x30.duckdb ] || python build_scaled.py --db codebase_community --sf 30 >> $R/scaled_build/build_large.log 2>&1
# K=8 trace at SF1, SF10, large
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf1.jsonl --scale 1 > $R/replay/k8_sf1.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf10.jsonl --scale 10 > $R/replay/k8_sf10.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf100_part.jsonl --scale 100 \
  --dbs thrombosis_prediction,formula_1,debit_card_specializing,california_schools,card_games > $R/replay/k8_sf100_part.log 2>&1
python replay_c3.py --trace $R/agent_qwen3_8b/trace.jsonl --out $R/replay/k8_sf30_codebase.jsonl --scale 30 \
  --dbs codebase_community > $R/replay/k8_sf30_codebase.log 2>&1
# K=16 trace, attempt subsets, SF10
for k in 2 4 8 16; do
  python replay_c3.py --trace $R/agent_qwen3_8b_k16/trace.jsonl --out $R/replay/k16_sub${k}_sf10.jsonl --scale 10 --max-attempts $k > $R/replay/k16_sub${k}_sf10.log 2>&1
done
echo ALL_DONE > $R/replay/ALL_DONE
