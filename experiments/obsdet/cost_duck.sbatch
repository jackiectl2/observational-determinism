#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --output=runs/obsdet/cost/logs/%x-%j.out
# E3 DuckDB cost replay (CPU only). Usage: sbatch --job-name=.. --mem=.. --time=.. cost_duck.sbatch
#   <mode natural|controlled> <scale sf1|x10|xmax> <dbs comma list|all> <out.jsonl> <duckdb memory_limit> [extra cost_duck.py args, e.g. --profile]
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
TMP=/tmp/obsdet_e3_${SLURM_JOB_ID}
trap 'rm -rf "$TMP"' EXIT
cd $V/code/obsdet
DBS=()
[ "$3" != "all" ] && DBS=(--dbs "$3")
echo "[job] $(date) host=$(hostname) args=$*"
python cost_duck.py "$1" --scale "$2" "${DBS[@]}" --out "$V/runs/obsdet/cost/$4" --mem "$5" --tmp "$TMP" "${@:6}"
echo "[job] done $(date)"
