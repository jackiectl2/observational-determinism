#!/bin/bash
# Steps 1-2 driver (runs inside the CPU holder via srun --overlap): divergence replay + overhead timing.
cd ${PROJECT_ROOT}/code/pilot_r2_1
source env_r21.sh
python obs_divergence.py --out ../../runs/pilot_r2_1/divergence_v2.jsonl --timing-reps 3 --timing-scales 1,10
