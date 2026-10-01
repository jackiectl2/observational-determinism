#!/bin/bash
#SBATCH --job-name=obsdet-tdh
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=runs/obsdet/logs/%x-%j.out
# Task-disjoint held-out build (run_heldout.sbatch on the v6td runs): distinct statements of the task-disjoint E4
# agents (both models, all conditions), frozen certifier (DuckDB dialect); td_filter.py removes statements equal to
# a development probe or to a first-held-out statement (exactly and after heldout_dedup.norm) and statements that
# fail on SF1; distribution of the kept statements. The DuckDB and PostgreSQL replays run as dependent jobs.
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
R=$V/runs/obsdet
cd $V/code/obsdet
md5sum certify.py tool.py heldout_probes.py heldout_dedup.py td_filter.py distribution.py $R/catalog.json $R/cert_probes_v6.jsonl $R/cert_heldout_all.jsonl
test ! -e $R/cert_td_all.jsonl
python heldout_probes.py $R/catalog.json $R/cert_probes_v6.jsonl $V/data/bird_duckdb/validation $R/cert_td_all.jsonl $R/e4/v6td_qwen3_8b $R/e4/v6td_phi4
python td_filter.py $R/cert_probes_v6.jsonl $R/cert_heldout_all.jsonl $R/cert_td_all.jsonl $R/cert_td_new.jsonl $R/td_funnel.json
python distribution.py $R/cert_td_new.jsonl $R/catalog.json $R/distribution_td.json $R/e4/v6td_qwen3_8b $R/e4/v6td_phi4
