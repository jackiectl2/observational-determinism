#!/bin/bash
#SBATCH --job-name=obsdet-e4
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# E4: greedy agent, 150 BIRD tasks x 11 conditions (raw/smartlex/certified x orig/p42/p7 at 1 thread,
# raw/certified at 8 threads); prompts deduplicated per turn; one model per job.
# Usage: sbatch run_agent3.sbatch <hf_model> <out_tag>
set -euo pipefail
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
source $V/env.sh
export HF_HUB_OFFLINE=1
cd $V/code/obsdet
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python agent_det3.py --tasks $V/runs/obsdet/tasks_v2.json --out $V/runs/obsdet/e4/dry_$2 --dry-run --limit-tasks 3
python agent_det3.py --tasks $V/runs/obsdet/tasks_v2.json --out $V/runs/obsdet/e4/$2   --model "$1" --max-turns 8 --max-tokens 768 --max-model-len 16384
python analyze3.py $V/runs/obsdet/e4/$2 $V/runs/obsdet/tasks_v2.json
