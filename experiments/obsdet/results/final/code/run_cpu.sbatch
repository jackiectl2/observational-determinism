#!/bin/bash
#SBATCH --job-name=obsdet-cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# Generic CPU runner for obsdet scripts: sbatch run_cpu.sbatch <script.py> [args...]
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
cd ${PROJECT_ROOT}/code/obsdet
python "$@"
