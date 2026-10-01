#!/bin/bash
#SBATCH --job-name=obsdet-v7cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=runs/obsdet/v7/logs/%x-%j.out
# Generic CPU runner for the v7 evaluation (run_cpu.sbatch from code/obsdet_v7 with the certifier md5 check):
# sbatch run_cpu_v7.sbatch <script.py> [args...]
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
cd ${PROJECT_ROOT}/code/obsdet_v7
echo "1369ffcae12b93aec06735259c146814  certify.py" | md5sum -c -  # final v7 certifier (lead, 2026-09-25); job fails otherwise
md5sum tool.py replay_sound.py "$1"
python "$@"
