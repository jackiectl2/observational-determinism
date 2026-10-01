#!/bin/bash
#SBATCH --output=runs/obsdet/proptest/logs/%x-%j.out
# E1d property-based soundness test of certify.py (CPU only).
# Usage: sbatch --job-name=.. --cpus-per-task=N --mem=.. --time=.. proptest.sbatch <duck|pg> <out_subdir> <seed_lo> <seed_hi> [proptest.py options]
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet
echo "[job] $(date) host=$(hostname) cpus=${SLURM_CPUS_PER_TASK:-?} args=$*"
if [ "$1" = pg ]; then trap 'python pg_setup.py stop proptest >/dev/null 2>&1 || true' EXIT; fi
python proptest.py "$1" "$V/runs/obsdet/proptest/$2" "$3" "$4" "${@:5}"
echo "[job] done $(date)"
