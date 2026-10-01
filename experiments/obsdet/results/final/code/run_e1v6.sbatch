#!/bin/bash
#SBATCH --job-name=obsdet-e1v6
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# E1/E2 on the certifier after code-review round 3: re-certify, distribution, replay, adversarial last (exits non-zero on
# any failed case or missing power).
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet
md5sum certify.py tool.py cert_probes.py adversarial.py replay_sound.py distribution.py
python cert_probes.py $V/runs/obsdet/catalog.json $V/runs/pilot_r2_1/divergence_v2.jsonl $V/data/bird_duckdb/validation $V/runs/obsdet/cert_probes_v6.jsonl
python distribution.py $V/runs/obsdet/cert_probes_v6.jsonl $V/runs/obsdet/catalog.json $V/runs/obsdet/distribution_v6.json
python replay_sound.py $V/runs/obsdet/cert_probes_v6.jsonl $V/runs/obsdet/sound_v6.jsonl
python adversarial.py $V/runs/obsdet/adversarial_v5.json 30 6
