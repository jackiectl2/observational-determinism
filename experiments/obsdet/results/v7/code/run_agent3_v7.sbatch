#!/bin/bash
#SBATCH --job-name=obsdet-e4v7
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=runs/obsdet/v7/logs/%x-%j.out
# E4 with certifier v7: run_agent3.sbatch (E4 v5: 15 conditions, same flags) from code/obsdet_v7 with the task file
# as an argument and outputs under runs/obsdet/v7/e4/. One model per job.
# Usage: sbatch run_agent3_v7.sbatch <hf_model> <out_tag> <tasks.json>
set -euo pipefail
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
O=$V/runs/obsdet/v7/e4
source $V/env.sh
export HF_HUB_OFFLINE=1
cd $V/code/obsdet_v7
echo "1369ffcae12b93aec06735259c146814  certify.py" | md5sum -c -  # final v7 certifier (lead, 2026-09-25); job fails otherwise
md5sum certify.py tool.py agent_det3.py analyze3.py "$3"
test ! -e $O/$2/attempts.jsonl
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python agent_det3.py --tasks "$3" --out $O/dry_$2 --dry-run --limit-tasks 3
python agent_det3.py --tasks "$3" --out $O/$2   --model "$1" --max-turns 8 --max-tokens 768 --max-model-len 16384
python analyze3.py $O/$2 "$3"
