#!/bin/bash
#SBATCH --job-name=obsdet-v7cert
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=runs/obsdet/v7/logs/%x-%j.out
# Certifier v7 certificates (DuckDB dialect) in the formats of the v6 files, for the three existing statement sets:
#  dev: cert_probes.py + distribution.py (as run_e1v6.sbatch: incl. no-keys ablation and tie-break widths);
#  first held-out: heldout_probes.py on the E4 v4 runs (as run_heldout.sbatch), the not-in-dev file that the v6
#    replays used, and the kept set (td_filter.py with no prior held-out set = the heldout_dedup keep-set);
#  task-disjoint: heldout_probes.py on the v6td runs + td_filter.py (same keep rule as v6).
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
R=$V/runs/obsdet
O=$R/v7
D=$V/data/bird_duckdb/validation
cd $V/code/obsdet_v7
echo "1369ffcae12b93aec06735259c146814  certify.py" | md5sum -c -  # final v7 certifier (lead, 2026-09-25); job fails otherwise
md5sum certify.py tool.py cert_probes.py heldout_probes.py heldout_dedup.py td_filter.py distribution.py $R/catalog.json
python -c "import certify, hashlib; print('certify imported from', certify.__file__, hashlib.md5(open(certify.__file__, 'rb').read()).hexdigest())"
test ! -e $O/cert_probes_v7.jsonl
python cert_probes.py $R/catalog.json $V/runs/pilot_r2_1/divergence_v2.jsonl $D $O/cert_probes_v7.jsonl
python distribution.py $O/cert_probes_v7.jsonl $R/catalog.json $O/distribution_v7.json
python heldout_probes.py $R/catalog.json $O/cert_probes_v7.jsonl $D $O/cert_heldout_all_v7.jsonl $R/e4/v4_qwen3_8b $R/e4/v4_phi4
python -c "import json; f=open(\"$O/cert_heldout_new_v7.jsonl\",\"w\"); [f.write(l) for l in open(\"$O/cert_heldout_all_v7.jsonl\") if not json.loads(l)[\"in_dev\"]]"
: > $O/empty.jsonl
python td_filter.py $O/cert_probes_v7.jsonl $O/empty.jsonl $O/cert_heldout_all_v7.jsonl $O/cert_heldout_kept_v7.jsonl $O/heldout_funnel_v7.json
python distribution.py $O/cert_heldout_kept_v7.jsonl $R/catalog.json $O/distribution_heldout_v7.json
python heldout_probes.py $R/catalog.json $O/cert_probes_v7.jsonl $D $O/cert_td_all_v7.jsonl $R/e4/v6td_qwen3_8b $R/e4/v6td_phi4
python td_filter.py $O/cert_probes_v7.jsonl $R/cert_heldout_all.jsonl $O/cert_td_all_v7.jsonl $O/cert_td_new_v7.jsonl $O/td_funnel_v7.json
python distribution.py $O/cert_td_new_v7.jsonl $R/catalog.json $O/distribution_td_v7.json
