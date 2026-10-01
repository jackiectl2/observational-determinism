#!/bin/bash
#SBATCH --job-name=obsdet-e1pg
#SBATCH --cpus-per-task=8
#SBATCH --mem=40G
#SBATCH --time=04:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# E1 on PostgreSQL 16: private server e1pg; original and seed-42 permuted heap orders of the six probe databases;
# replay raw / smart-lex / certified (v5 certificates) under 5 configurations. Server stopped on exit.
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet
trap 'python pg_setup.py stop e1pg' EXIT
python - <<PY
import pg_setup
orig = pg_setup.duck_path
pg_setup.duck_path = lambda db, sc: f"$V/data/pilot_r2_1/{db}_perm42.duckdb" if sc == "perm42" else orig(db, sc)
pg_setup.start("e1pg", "8GB")
for db in ["california_schools", "card_games", "codebase_community", "debit_card_specializing", "formula_1",
           "thrombosis_prediction"]:
    for sc in ("sf1", "perm42"):
        pg_setup.load("e1pg", db, sc)
PY
python replay_pg.py $V/runs/obsdet/cert_probes_v5.jsonl e1pg $V/runs/obsdet/sound_pg_v5.jsonl
