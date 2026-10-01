#!/bin/bash
#SBATCH --job-name=r21-agent-greedy-v2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=runs/pilot_r2_1/logs/%x-%j.out
# Pilot R2-1 step 3: Qwen3-8B greedy (T=0), 66 BIRD tasks x 7 conditions (orig/permuted physical order,
# DuckDB 1/8 threads, raw vs canonical OBSERVE v2), <= 8 turns; identical prompts generated once per turn.
set -euo pipefail
cd ${PROJECT_ROOT}/code/pilot_r2_1
source env_r21.sh
nvidia-smi --query-gpu=name,memory.total --format=csv
python agent_det.py --tasks ../../runs/pilot_c3/tasks.json --out ../../runs/pilot_r2_1/agent_greedy_v2 \
  --model Qwen/Qwen3-8B --max-turns 8 --max-tokens 768 --max-model-len 16384 --seed-perm 42
