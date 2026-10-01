#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --output=runs/obsdet/cost/logs/%x-%j.out
# E3 PostgreSQL (CPU only): start a private server (data dir runs/obsdet/pg/<server>), load each <db> at sf1 and
# x10 (once), replay the natural probes (EXPLAIN at x10) and, for codebase_community / card_games, the
# controlled LIMIT study (EXPLAIN at both scales); stop the server on exit.
# Usage: sbatch --job-name=.. --mem=.. --time=.. [--export=ALL,MODEL=pc,PROBES=<cert jsonl>] pg_cost.sbatch <server> <shared_buffers> <db> [<db> ...]
# MODEL=fetch (default; outputs pg_nat_/pg_ctl_), pc or pctxn (preview + count; outputs pg_pcnat_/pg_pcctl_);
# SUFFIX is appended to the output prefix (e.g. v4_); CONTROLLED=0 skips the controlled study;
# PGCERT=1 certifies the transpiled SQL in the postgres dialect (as replay_pg.py).
set -euo pipefail
source ${PROJECT_ROOT}/env.sh
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
cd $V/code/obsdet
S=$1; SB=$2; shift 2
MODEL=${MODEL:-fetch}; PROBES=${PROBES:-$V/runs/obsdet/cert_probes_v3.jsonl}
PGC=(); [ "${PGCERT:-0}" = 1 ] && PGC=(--pgcert)
if [ "$MODEL" = pc ] || [ "$MODEL" = pctxn ]; then NAT=pg_pcnat_${SUFFIX:-}; CTL=pg_pcctl_${SUFFIX:-}; else NAT=pg_nat_; CTL=pg_ctl_; fi
trap 'python pg_setup.py stop $S' EXIT
echo "[job] $(date) host=$(hostname) server=$S dbs=$* model=$MODEL probes=$PROBES pgcert=${PGCERT:-0}"
python pg_setup.py start $S $SB
for db in "$@"; do
  for sc in sf1 x10; do
    M=$V/runs/obsdet/pg/.loaded_${S}_${db}_${sc}
    [ -f $M ] || { python pg_setup.py load $S $db $sc && touch $M; }
  done
done
for db in "$@"; do
  python pg_cost.py natural $S $db --scales sf1,x10 --explain-scales x10 --model $MODEL --probes $PROBES "${PGC[@]}" --out $V/runs/obsdet/cost/${NAT}$db.jsonl
  [ "${CONTROLLED:-1}" = 1 ] && case $db in codebase_community|card_games)
    python pg_cost.py controlled $S $db --scales sf1,x10 --explain-scales sf1,x10 --model $MODEL "${PGC[@]}" --out $V/runs/obsdet/cost/${CTL}$db.jsonl;;
  esac
done
echo "[job] done $(date)"
