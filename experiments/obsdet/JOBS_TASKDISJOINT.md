# obsdet task-disjoint replication — job log

Reviewer request: replicate E4 (agent level) and E1-H (held-out statements) on BIRD tasks disjoint from `tasks_v2`.
Cluster project dir `$V=$PROJECT_ROOT`; code `$V/code/obsdet/`; outputs
`$V/runs/obsdet/`; logs `$V/runs/obsdet/logs/<job-name>-<id>.out`; environment `$V/env.sh` (no new environment).
CPU jobs: account `<CPU_ACCOUNT>`, partition `<CPU_PARTITION>`. GPU jobs: account `<GPU_ACCOUNT>`, partition `<GPU_PARTITION>`
(1x <GPU>, 8 CPUs, 64 GB). Results and code copies: `results/final/taskdisjoint/`.

Frozen files verified on the cluster against `results/final/code/MD5SUMS.txt` before use (2026-09-25 10:29 PDT):
certify.py 7aa9c889bb18, tool.py md5-withheld, agent_det3.py md5-withheld, analyze3.py 2210aba77af9,
replay_sound.py md5-withheld, replay_pg.py md5-withheld (all match). heldout_dedup.py and strict_burden.py exist
only in the frozen snapshot; heldout_dedup.py is copied unchanged to `$V/code/obsdet/` (md5 checked in the job log).

New scripts (not frozen): `prep_tasks3.py` (task selection + check of the physical-order copies),
`run_prep3.sbatch`, `run_agent3td.sbatch` (copy of `run_agent3.sbatch` with the task file as the third argument;
command lines otherwise identical), `td_filter.py` (held-out funnel), `run_td_heldout.sbatch` (copy of
`run_heldout.sbatch` on the v6td runs), `run_e1pg_td.sbatch` (copy of `run_e1pg_heldout.sbatch` with a new server
`e1pgtd` and file arguments), `td_analyze.py` (local summary).

| Job ID | Purpose | Resources | Walltime | Command (code version) | Log | Status / result |
|---|---|---|---|---|---|---|
| 61885528 | Select tasks_v3 (seed 2) + verify seed-42/7 copies of the 11 DBs | 8 CPU, 32 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 1 h | `run_prep3.sbatch` (prep_tasks3 md5 md5-withheld) | `obsdet-prep3-61885528.out` | COMPLETED 1:08. Only 149 tasks: european_football_2 has 9 eligible tasks outside tasks_v2 (its DuckDB conversion has 3 of the 7 BIRD tables; 110 of 119 candidates' gold SQL fails). Output renamed `tasks_v3_149_superseded.json` (md5 3c0da7a0570d); never used by any run. Physical-order copies: 22/22 ok |
| 61885622 | Select tasks_v3 again with the top-up rule (shortfall filled from the database with the largest tasks_v2 count, continuing its seeded order) + copy check | 8 CPU, 32 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 1 h | `run_prep3.sbatch` (prep_tasks3 md5 md5-withheld) | `obsdet-prep3-61885622.out` | COMPLETED 0:48. **tasks_v3.json FIXED** (see below) |

### Task selection (fixed 2026-09-25 10:38 PDT, before any agent run)

- `$V/runs/obsdet/tasks_v3.json`, **md5 bd7f698fda5431cec882e22e7f94114c**, 150 tasks, 0 question_ids shared with
  tasks_v2 (md5 3b638491274b). Note: `tasks_v3_selection.json` (seed, procedure, per-database stats, task ids,
  copy check). Local copies in `results/final/taskdisjoint/`.
- Procedure (`prep_tasks3.py`, md5 md5-withheld, seed 2): BIRD dev 2025-11-06 (md5 d0553ba7a2bc); per database,
  exclude the tasks_v2 question_ids and questions whose text or gold SQL equals a tasks_v2 one (1 each in
  formula_1 and toxicology); sort by question_id, shuffle with `random.Random(2)` (databases in sorted order), take
  the first tasks whose gold SQL transpiled to DuckDB returns 1..200 rows on SF1 (rule of prep_tasks.py/2).
- Per-database counts (tasks_v2 → tasks_v3): california_schools 10→10, card_games 18→18, codebase_community
  20→**21**, debit_card_specializing 9→9, european_football_2 10→**9**, financial 10→10, formula_1 18→18,
  student_club 16→16, superhero 16→16, thrombosis_prediction 7→7, toxicology 16→16. european_football_2 has only 9
  eligible tasks left (its DuckDB conversion lacks Player/Player_Attributes/Team/Team_Attributes), so the one
  missing task is `codebase_community:601` (top-up rule). The 149 first-pass tasks are identical to job 61885528's.
- Difficulty: tasks_v3 simple 83 / moderate 41 / challenging 26 (tasks_v2: 87 / 48 / 15; not stratified in
  either list).
- Physical-order copies `$V/data/pilot_r2_1/<db>_perm{42,7}.duckdb`: all 22 exist; same tables, equal row counts
  and equal row multisets (EXCEPT ALL) as the originals; the first 20 rows in rowid order differ in every table with
  >= 2 rows.

### Runs (submitted 2026-09-25 10:38 PDT; frozen code as listed above)

| Job ID | Purpose | Resources | Walltime | Command (code version) | Log | Status / result |
|---|---|---|---|---|---|---|
| 61885650 | E4 task-disjoint, Qwen3-8B, 15 conditions (E4 v5 design) + analyze3 | 1x <GPU>, 8 CPU, 64 GB (<GPU_ACCOUNT>/<GPU_PARTITION>) | 3 h | `run_agent3td.sbatch Qwen/Qwen3-8B v6td_qwen3_8b $R/tasks_v3.json` (sbatch md5 md5-withheld) | `obsdet-e4td-61885650.out` | COMPLETED 7:53 (generation 172 s). raw_phys traj 52/150; strict: 2 same-SQL observation changes from CERTIFIED statements (DET financial:100, ALL formula_1:930) -> diagnosis job 61886477 |
| 61885651 | E4 task-disjoint, phi-4, same | 1x <GPU>, 8 CPU, 64 GB (<GPU_ACCOUNT>/<GPU_PARTITION>) | 3 h | `run_agent3td.sbatch microsoft/phi-4 v6td_phi4 $R/tasks_v3.json` | `obsdet-e4td-61885651.out` | COMPLETED 12:14. raw_phys traj 37/150; strict: 1 same-SQL observation change from a CERTIFIED statement (DET california_schools:0) |
| 61885652 | Held-out build: distinct v6td statements, frozen certifier, td_filter funnel, distribution (afterok 61885650:61885651) | 8 CPU, 48 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 3 h | `run_td_heldout.sbatch` (td_filter md5 9c61c749027f, heldout_dedup 31e6109e8111) | `obsdet-tdh-61885652.out` | COMPLETED 0:26. 1,495 distinct -> 1,321 kept (dev 1+0, first held-out 8+5, fails on SF1 160) |
| 61885653 | DuckDB replay of the task-disjoint held-out statements, 7 configurations (afterok 61885652) | 8 CPU, 32 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 2 h | `sbatch --job-name=obsdet-tdsound run_cpu.sbatch replay_sound.py $R/cert_td_new.jsonl $R/sound_td.jsonl` | `obsdet-tdsound-61885653.out` | COMPLETED 2:18. 0 censored; certified diverged DET 2/315, NARROW 0/471, ALL 1/217 (3 statements = the 3 from the agent runs); UNSUPPORTED fallback 41/318 |
| 61885654 | PostgreSQL replay, new server e1pgtd (11 DBs x sf1/perm42), PG-dialect certificates, 5 configurations (afterok 61885652) | 8 CPU, 40 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 4 h | `run_e1pg_td.sbatch $R/cert_td_new.jsonl $R/sound_pg_td.jsonl` | `obsdet-e1pgtd-61885654.out` | COMPLETED 9:10; server stopped. certified diverged 0/985 supported (18 censored); UNSUPPORTED 288 complete (30 censored). Data dir `pg/e1pgtd` (8,465 files, 2.1 GB) deleted after the results were copied (rebuildable with the same script) |
| 61886477 | Diagnosis of the 3 certified statements whose observation changed in the agent runs: frozen certificate, DuckDB result types, plan, observation under the 7 replay configurations | 8 CPU, 16 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 30 min | `sbatch --job-name=obsdet-tddiag --mem=16G --time=00:30:00 run_cpu.sbatch td_diag.py $R/td_diag_statements.json` (td_diag md5 md5-withheld) | `obsdet-tddiag-61886477.out` | COMPLETED 0:08. DuckDB 1.5.5: DECIMAL / DECIMAL -> DOUBLE (certify.py infers DECIMAL); SELECT DISTINCT x ... ORDER BY y (y not output) is planned as HASH_GROUP_BY x with first(y) -> order-dependent. All 3 statements diverge across the 7 configurations |

All jobs finished by 2026-09-25 11:01 PDT; no allocation left running. Other helper modules loaded by the frozen code
(not frozen in MD5SUMS, recorded for completeness): pilot_c3/common.py md5-withheld, pilot_c3/agent_c3.py
a894e86701f3, pilot_r2_1/observe.py md5-withheld; run_cpu.sbatch md5-withheld (matches MD5SUMS).
Results: `results/final/taskdisjoint/RESULTS_TASKDISJOINT.md`.
