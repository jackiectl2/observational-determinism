#!/bin/bash
#SBATCH --job-name=obsdet-td2h
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=runs/obsdet/v7/logs/%x-%j.out
# Second task-disjoint held-out build (as run_td_heldout.sbatch, certifier v7): distinct statements of the v7td2 agents
# (both models, all 15 conditions), td2_filter.py removes exact/normalized duplicates of the development probes, the
# first held-out statements and the first task-disjoint statements, then statements failing on SF1; distribution.
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
R=$V/runs/obsdet
O=$R/v7
cd $V/code/obsdet_v7
echo "1369ffcae12b93aec06735259c146814  certify.py" | md5sum -c -  # final v7 certifier (lead, 2026-09-25); job fails otherwise
md5sum certify.py tool.py heldout_probes.py heldout_dedup.py td2_filter.py distribution.py $R/cert_heldout_all.jsonl $R/cert_td_all.jsonl
test ! -e $O/cert_td2_all.jsonl
python heldout_probes.py $R/catalog.json $O/cert_probes_v7.jsonl $V/data/bird_duckdb/validation $O/cert_td2_all.jsonl $O/e4/v7td2_qwen3_8b $O/e4/v7td2_phi4
python td2_filter.py $O/cert_probes_v7.jsonl $R/cert_heldout_all.jsonl $R/cert_td_all.jsonl $O/cert_td2_all.jsonl $O/cert_td2_new.jsonl $O/td2_funnel.json
python distribution.py $O/cert_td2_new.jsonl $R/catalog.json $O/distribution_td2.json $O/e4/v7td2_qwen3_8b $O/e4/v7td2_phi4
