#!/bin/bash
#SBATCH --job-name=obsdet-prep3
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# Task-disjoint replication, step 1: select tasks_v3 (150 BIRD dev tasks disjoint from tasks_v2, same per-database
# counts, seed fixed in prep_tasks3.py) and verify the seed-42 / seed-7 physical-order copies of the 11 databases.
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet
md5sum prep_tasks3.py $V/runs/obsdet/tasks_v2.json
test ! -e $V/runs/obsdet/tasks_v3.json  # never overwrite a fixed task list
python prep_tasks3.py $V/runs/obsdet/tasks_v2.json $V/runs/obsdet/tasks_v3.json $V/runs/obsdet/tasks_v3_selection.json
