#!/bin/bash
#SBATCH --job-name=obsdet-e1pgtd
#SBATCH --cpus-per-task=8
#SBATCH --mem=40G
#SBATCH --time=04:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# Task-disjoint held-out statements on PostgreSQL 16: run_e1pg_heldout.sbatch with a new private server (e1pgtd,
# built the same way: original and seed-42 permuted heap orders of the 11 databases) and the input/output files as
# arguments; replay raw / smart-lex / certified (certificates in the PostgreSQL dialect) under 5 configurations.
# Server stopped on exit.
# Usage: sbatch run_e1pg_td.sbatch <cert.jsonl> <out.jsonl>
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet
md5sum certify.py tool.py replay_pg.py pg_setup.py pg_cost.py "$1"
trap 'python pg_setup.py stop e1pgtd' EXIT
python - <<PY
import pg_setup
orig = pg_setup.duck_path
pg_setup.duck_path = lambda db, sc: f"$V/data/pilot_r2_1/{db}_perm42.duckdb" if sc == "perm42" else orig(db, sc)
pg_setup.start("e1pgtd", "8GB")
for db in ["california_schools", "card_games", "codebase_community", "debit_card_specializing", "formula_1",
           "thrombosis_prediction", "student_club", "superhero", "toxicology", "european_football_2", "financial"]:
    for sc in ("sf1", "perm42"):
        pg_setup.load("e1pgtd", db, sc)
PY
python replay_pg.py "$1" e1pgtd "$2"
