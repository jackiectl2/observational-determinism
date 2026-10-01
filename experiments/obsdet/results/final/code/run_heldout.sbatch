#!/bin/bash
#SBATCH --job-name=obsdet-heldout
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# Held-out validation (review round 1): distinct statements issued by the E4 agents (both models, 11 databases),
# frozen certifier; distribution (with per-model verdicts) (the DuckDB and PostgreSQL replays of the
# statements that are not in the development set run as dependent jobs).
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
R=$V/runs/obsdet
cd $V/code/obsdet
md5sum certify.py heldout_probes.py replay_sound.py distribution.py
python heldout_probes.py $R/catalog.json $R/cert_probes_v6.jsonl $V/data/bird_duckdb/validation $R/cert_heldout_all.jsonl $R/e4/v4_qwen3_8b $R/e4/v4_phi4
python -c "import json; f=open(\"$R/cert_heldout_new.jsonl\",\"w\"); [f.write(l) for l in open(\"$R/cert_heldout_all.jsonl\") if not json.loads(l)[\"in_dev\"]]"
python distribution.py $R/cert_heldout_new.jsonl $R/catalog.json $R/distribution_heldout.json $R/e4/v4_qwen3_8b $R/e4/v4_phi4
