#!/bin/bash
# Submit every E3 preview + count job (DuckDB natural SF1/x10/xmax + profile, DuckDB controlled study,
# PostgreSQL natural SF1/x10 + EXPLAIN + controlled study) for one certificate file.
# PostgreSQL: model pctxn (each policy's preview + count in one REPEATABLE READ READ ONLY transaction).
# Usage: bash cost_launch.sh <tag, e.g. v4> <cert_probes.jsonl>
set -euo pipefail
V=${PROJECT_ROOT:?set PROJECT_ROOT, see README}
C=$V/runs/obsdet/cost
cd $V/code/obsdet
T=$1; P=$2
X="--model pc --probes $P"
S="sbatch --parsable"
sub() { echo "$1 $(shift; $S "$@")"; }
sub e3-pc$T-sf1 --job-name=e3-pc$T-sf1 --mem=16G --time=01:30:00 cost_duck.sbatch natural sf1 all duck_pcnat_${T}_sf1.jsonl 12GB $X
sub e3-pc$T-x10a --job-name=e3-pc$T-x10a --mem=32G --time=02:00:00 cost_duck.sbatch natural x10 \
    california_schools,card_games,debit_card_specializing,formula_1,thrombosis_prediction duck_pcnat_${T}_x10a.jsonl 24GB $X
sub e3-pc$T-x10cc --job-name=e3-pc$T-x10cc --mem=48G --time=02:00:00 cost_duck.sbatch natural x10 codebase_community duck_pcnat_${T}_x10cc.jsonl 36GB $X
sub e3-pc$T-xmaxa --job-name=e3-pc$T-xmaxa --mem=32G --time=03:00:00 cost_duck.sbatch natural xmax \
    california_schools,debit_card_specializing,formula_1,thrombosis_prediction duck_pcnat_${T}_xmaxa.jsonl 24GB $X --profile \
    --skip-timeouts-from $C/duck_nat_x10a.jsonl
sub e3-pc$T-xmaxcg --job-name=e3-pc$T-xmaxcg --mem=64G --time=03:00:00 cost_duck.sbatch natural xmax card_games duck_pcnat_${T}_xmaxcg.jsonl 48GB $X --profile
sub e3-pc$T-xmaxcc --job-name=e3-pc$T-xmaxcc --mem=96G --time=03:00:00 cost_duck.sbatch natural xmax codebase_community duck_pcnat_${T}_xmaxcc.jsonl 72GB $X --profile \
    --skip-timeouts-from $C/duck_nat_x10cc.jsonl
sub e3-pc$T-ctl --job-name=e3-pc$T-ctl --mem=96G --time=02:00:00 --cpus-per-task=8 \
    --output=$C/logs/%x-%j.out --wrap="for s in sf1 x10 xmax; do bash cost_duck.sbatch controlled \$s all duck_pcctl_${T}.jsonl 72GB --model pc --profile || exit 1; done"
E="--export=ALL,MODEL=pctxn,SUFFIX=${T}_,CONTROLLED=1,PROBES=$P"
# One fresh server (data dir runs/obsdet/pg/<server>_<tag>) per job, so no job waits for another version's server.
for spec in "cc codebase_community 24GB 64G 06:00:00 codebase_community" "cg card_games 12GB 40G 06:00:00 card_games" \
            "cs california_schools 4GB 16G 04:00:00 california_schools" "f1 formula_1 4GB 16G 03:00:00 formula_1" \
            "small small 4GB 16G 03:00:00 debit_card_specializing thrombosis_prediction"; do
  set -- $spec
  short=$1; server=$2_$T; sb=$3; mem=$4; wall=$5; shift 5
  sub e3-pgpc$T-$short $E --job-name=e3-pgpc$T-$short --mem=$mem --time=$wall pg_cost.sbatch $server $sb "$@"
done
