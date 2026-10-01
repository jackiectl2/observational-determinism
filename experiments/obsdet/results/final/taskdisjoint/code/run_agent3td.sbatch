#!/bin/bash
#SBATCH --job-name=obsdet-e4td
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# Task-disjoint E4 replication: run_agent3.sbatch (E4 v5, 15 conditions) with the task file as an argument; the
# command lines are otherwise unchanged. One model per job.
# Usage: sbatch run_agent3td.sbatch <hf_model> <out_tag> <tasks.json>
set -euo pipefail
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
source $V/env.sh
export HF_HUB_OFFLINE=1
cd $V/code/obsdet
md5sum certify.py tool.py agent_det3.py analyze3.py "$3"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python agent_det3.py --tasks "$3" --out $V/runs/obsdet/e4/dry_$2 --dry-run --limit-tasks 3
python agent_det3.py --tasks "$3" --out $V/runs/obsdet/e4/$2   --model "$1" --max-turns 8 --max-tokens 768 --max-model-len 16384
python analyze3.py $V/runs/obsdet/e4/$2 "$3"
