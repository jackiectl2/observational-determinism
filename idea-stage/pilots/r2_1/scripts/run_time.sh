#!/bin/bash
# Step 2 overhead driver (runs inside the CPU holder via srun --overlap), after the divergence replay.
cd ${PROJECT_ROOT}/code/pilot_r2_1
source env_r21.sh
python time_observe.py --out ../../runs/pilot_r2_1/timing_v3.jsonl --reps 5
