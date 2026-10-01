# Same Data, Different Answers: Certified Observational Determinism for LLM Data Agents

Artifact of the PVLDB Vol. 20 (VLDB 2027) submission by Tianlang Chen (University of Michigan).

LLM data agents see a database through bounded previews of query results: a header, the first rows and a row count.
SQL leaves tie order and the rows kept by `LIMIT` unspecified, so equivalent executions of the same query on the same
data can show an agent different previews. The paper defines *observational determinism* for such previews and a
static certifier that proves when a query's own `ORDER BY` fixes the preview, derives a sufficient tie-break when it
does not, and rejects the query when it can prove neither. This repository contains the certifier, the agent tool and
harness, every experiment script, the raw results behind every number in the paper, and the job logs.

## Layout

| Path | Contents |
|---|---|
| `experiments/obsdet/certify.py` | The certifier (md5 `80705f63…`, 743 lines). `certify(sql, tables, dialect)` returns a `Certificate` with verdict `DET`, `NARROW`, `ALL` or `UNSUPPORTED`, the reason, the tie-break and the rewritten statement. `smartlex(sql, n_out, dialect)` is the blanket baseline. |
| `experiments/obsdet/CERTIFIER_SPEC.md` | Every rule and reason code of the certifier, with the adversarial cases and replayed statements that exercise it. |
| `experiments/obsdet/tool.py` | The agent-facing SQL tool (runs only queries, canonical rendering, exact row counts). |
| `experiments/obsdet/agent_det3.py` | The agent harness and the raw, smart-lex, hybrid ("certified") and strict policies. The agent prompts are in `idea-stage/pilots/c3/scripts/agent_c3.py`; `idea-stage/pilots/c3/scripts/common.py` and `idea-stage/pilots/r2_1/scripts/observe.py` hold the execution helpers the tool and harness import. |
| `experiments/obsdet/replay_sound.py`, `replay_pg.py` | Soundness replays on DuckDB (7 configurations) and PostgreSQL (5 configurations). |
| `experiments/obsdet/adversarial.py`, `proptest.py` | Adversarial suite and property-based (generated-query) tests. |
| `experiments/obsdet/cost_*.py`, `pg_cost.py`, `time_certify.py` | Cost of observation and certification latency. |
| `experiments/obsdet/*_check.py`, `v6_v7_tiebreak_diff.py` | Checks run during the final audits (qualified table names, statement types, read-only tool, count path, constant comparisons, v6/v7 differences). |
| `experiments/obsdet/JOBS*.md` | Every cluster job: purpose, resources, exact command, code versions (md5) and result. |
| `experiments/obsdet/results/v7/` | Final runs: certificates, soundness replays, agent runs (`e4_v7*/summary_e4.json`, `trace.jsonl`), distributions, funnels, task lists, diffs, logs. |
| `experiments/obsdet/results/final/` | Earlier rounds, the unseen-tasks-I set (`taskdisjoint/`), the property-based runs (`proptest/`) and the catalog. |
| `experiments/obsdet/results/E3_analysis_v6.*` | Cost analysis (Table 4). |
| `figures/` | Scripts that generate every table and figure of the paper from the result files, and their outputs. |

## From the paper to the files

| Paper | Source | Generator |
|---|---|---|
| Table 1 (agents, main tasks) | `results/v7/e4_v7_qwen3_8b/summary_e4.json`, `e4_v7_phi4/` | `figures/gen_table_agents.py` |
| Table 2 (soundness) | `results/v7/sound*_v7.jsonl`, `sound_td2.jsonl`, `sound_pg_td2.jsonl` | `figures/gen_table_soundness.py` |
| Table 3 (cost) | `results/E3_analysis_v6.json` | `figures/gen_table_cost.py` |
| Figure 3 (divergence by class and reason) | `results/v7/sound*.jsonl`, `results/v7/cert_*.jsonl` | `figures/gen_fig_divergence.py` |
| Figure 4 (coverage) | `results/v7/cert_probes_v7.jsonl`, `cert_heldout_kept_v7.jsonl`, `cert_td2_new.jsonl` | `figures/gen_fig_coverage.py` |
| Figure 5 (agents, all task sets) | `results/v7/e4_v7*/summary_e4.json` | `figures/gen_fig_agents.py` |
| Figure 6 (cost per probe, controlled study) | `results/E3_analysis_v6_per_probe.csv`, `results/E3_analysis_v6.json` | `figures/gen_fig_cost.py` |
| Other numbers in the text | `figures/text_stats.txt`, `figures/rejection_stats.txt`, `results/v7/time_certify.json`, `results/final/proptest/` | `figures/text_stats.py`, `figures/rejection_stats.py` |
| Task lists and seeds | `results/final/tasks_v2.json` (main), `results/final/taskdisjoint/tasks_v3*.json` (unseen I), `results/v7/tasks_v4*.json` (unseen II) | `prep_tasks2.py`, `prep_tasks3.py`; `idea-stage/pilots/c3/scripts/prep_tasks.py` |

## Using the certifier

The certifier needs Python 3.12 and `sqlglot` 30.19.0; the experiments used DuckDB 1.5.5, PostgreSQL 16.2 and vLLM 0.30.0
(`experiments/obsdet/results/env_versions.json`).

```python
import json
from certify import certify
catalog = json.load(open("results/final/catalog.json"))          # column types and validated keys per database
c = certify("SELECT Id, DisplayName FROM users ORDER BY Id LIMIT 3", catalog["codebase_community"], "duckdb")
print(c.verdict, c.reason, c.tie_break, c.rewritten)
```

The guarantees hold under the assumptions of Section 3.4 of the paper; the tool enforces the ones about the session
(one database state per call, validated keys, canonical rendering). Premise (vi) — that the front end reads each
statement as the engine does — is tested, not proved.

## Reproducing the experiments

The scripts were run as Slurm jobs on a university cluster; `JOBS*.md` gives the exact commands. The databases are the
BIRD development set (https://bird-bench.github.io/), converted to DuckDB and, for the PostgreSQL experiments, loaded
by `pg_setup.py`. The agent runs used Qwen3-8B and microsoft/phi-4 served by vLLM with greedy decoding.

To run them on another Slurm cluster, copy `cluster.env.example` to `cluster.env`, fill it in, `source cluster.env`,
and submit from `$PROJECT_ROOT`. The scripts read the project directory from `PROJECT_ROOT`; `sbatch` takes the account
and partition from `SBATCH_ACCOUNT` and `SBATCH_PARTITION`, and job logs go to paths relative to the submission
directory. GPU jobs request one GPU (`--gres=gpu:1`).

**Redactions.** Cluster-specific values were replaced for publication: the project directory by `$PROJECT_ROOT`
(in the Python scripts, `os.environ["PROJECT_ROOT"]`, with `import os` added where a script lacked it), the home directory by `$HOME`, and in the job logs and records
the Slurm accounts, partitions, filesystem, cluster name and GPU model by `<CPU_ACCOUNT>`, `<GPU_ACCOUNT>`,
`<CPU_PARTITION>`, `<GPU_PARTITION>`, `<FILESET>`, `<CLUSTER>` and `<GPU>`. In addition, the `#SBATCH` account and
partition lines were removed, `--gres=gpu:<model>:1` became `--gres=gpu:1`, temporary directories named after the
user became `/tmp/obsdet_*`, and an internal housekeeping note (`JOBS.md`), a comment (`env_r21.sh`), review-session identifiers and the internal
review traces were removed. The code md5 values recorded in `JOBS*.md`, `MD5SUMS.txt`, the job logs and the result
files refer to the scripts as they ran. They are kept for files this redaction left unchanged, such as every
`certify.py`. For redacted files they read `md5-withheld`, since the original value would let anyone confirm a guess
of a redacted value. Nothing else changed.

## License

Code: MIT (see `LICENSE`). The result files contain queries over, and rows of, the BIRD databases, which BIRD
distributes under CC BY-SA 4.0.
