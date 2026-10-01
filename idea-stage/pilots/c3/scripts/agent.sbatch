#!/bin/bash
#SBATCH --job-name=c3-agent
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=runs/pilot_c3/logs/%x-%j.out
# Pilot C3: ReAct text-to-SQL agent, Qwen3-8B (thinking off), K=8 attempts x 66 BIRD dev tasks, <=8 turns.
set -euo pipefail
cd ${PROJECT_ROOT}/code/pilot_c3
source ../../env.sh
nvidia-smi --query-gpu=name,memory.total --format=csv
python agent_c3.py --tasks ../../runs/pilot_c3/tasks.json --out ../../runs/pilot_c3/agent_qwen3_8b \
  --model Qwen/Qwen3-8B --k 8 --max-turns 8 --temperature 0.8 --top-p 0.95 --max-tokens 768 --max-model-len 16384
