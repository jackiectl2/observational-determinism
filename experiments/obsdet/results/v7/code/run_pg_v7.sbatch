#!/bin/bash
#SBATCH --job-name=obsdet-v7pg
#SBATCH --cpus-per-task=8
#SBATCH --mem=40G
#SBATCH --time=04:00:00
#SBATCH --output=runs/obsdet/v7/logs/%x-%j.out
# PostgreSQL replays with certifier v7 (replay_pg.py certifies every statement in the PostgreSQL dialect) on an
# existing private server loaded by run_e1pg.sbatch (e1pg) or run_e1pg_heldout.sbatch (e1pgh); pg_check.py first
# verifies the loaded databases (present, same tables and row counts as the DuckDB sources, declared keys present).
# Server stopped on exit.
# Usage: sbatch run_pg_v7.sbatch <server> "<db> <db> ..." <cert.jsonl> <out.jsonl> [<cert.jsonl> <out.jsonl> ...]
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet_v7
echo "1369ffcae12b93aec06735259c146814  certify.py" | md5sum -c -  # final v7 certifier (lead, 2026-09-25); job fails otherwise
md5sum certify.py tool.py replay_pg.py pg_setup.py pg_cost.py pg_check.py
S=$1
DBS=$2
shift 2
trap "python pg_setup.py stop $S" EXIT
python pg_setup.py start $S 8GB
python pg_check.py $S $DBS
while [ $# -ge 2 ]; do
  test ! -e "$2"
  md5sum "$1"
  python replay_pg.py "$1" $S "$2"
  shift 2
done
