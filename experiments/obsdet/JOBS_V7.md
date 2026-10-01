# obsdet certifier v7 — evaluation job log

Request (lead, 2026-09-25 ~11:35 PDT): rerun the evaluation with certifier v7 (dev, first held-out and task-disjoint
certificates and replays; E4 on tasks_v2 / tasks_v3; a second task-disjoint set tasks_v4 as the clean test).
Code: `$V/code/obsdet_v7/` (certify.py md5 0353e3eeec5e; tool.py, analyze3.py, replay_sound.py, replay_pg.py,
heldout_probes.py, distribution.py, cert_probes.py, pg_setup.py, pg_cost.py, heldout_dedup.py, td_filter.py identical
to code/obsdet; agent_det3.py md5-withheld differs only in its sys.path line (obsdet_v7)). `$V/code/obsdet` (frozen
v6) is not touched. Outputs: `$V/runs/obsdet/v7/`; logs `$V/runs/obsdet/v7/logs/<job-name>-<id>.out`; local copies
`results/v7/`. New scripts (in obsdet_v7 and `results/v7/code/`): prep_tasks4.py md5-withheld, pg_check.py
c4a92d8a3139, td2_filter.py e3feb86d0bb2, run_agent3_v7.sbatch 9f42b558896c, run_v7_certs.sbatch 7752005abedd,
run_pg_v7.sbatch 67982d32a927, run_td2_build.sbatch 34ea01b19346; run_cpu.sbatch (obsdet_v7 copy, cd obsdet_v7)
53c9f45d4096. The adversarial v7 run (job 61887845) belongs to the lead and is not duplicated.

| Job ID | Purpose | Resources | Walltime | Command | Log | Status / result |
|---|---|---|---|---|---|---|
| 61888032 | Select tasks_v4 (disjoint from tasks_v2 and tasks_v3, seed 3) + copy check | 8 CPU, 32 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 1 h | `run_cpu.sbatch prep_tasks4.py $R/tasks_v2.json $R/tasks_v3.json $O/tasks_v4.json $O/tasks_v4_selection.json` | `obsdet-prep4-61888032.out` | COMPLETED 1:02. **tasks_v4.json FIXED** (see below) |
| 61888033 | v7 certificates: dev (cert_probes.py, distribution.py), first held-out (heldout_probes.py on E4 v4, keep set), task-disjoint (heldout_probes.py on v6td, td_filter.py) | 8 CPU, 48 GB | 2 h | `run_v7_certs.sbatch` | `obsdet-v7cert-61888033.out` | Kept (finishing within minutes when the lead paused v7); outputs are from the INTERIM certify.py 0353e3ee and are moved to `v7/interim_0353e3ee/`, not used for results |
| 61888034 | DuckDB replay, dev (7 configurations) (afterok 61888033) | 8 CPU, 32 GB | 2 h | `run_cpu.sbatch replay_sound.py $O/cert_probes_v7.jsonl $O/sound_v7.jsonl` | `obsdet-v7sdev-61888034.out` | CANCELLED 11:43 before start (lead: pause, certify.py will change again) |
| 61888035 | DuckDB replay, first held-out (not-in-dev file, as v6) (afterok 61888033) | 8 CPU, 32 GB | 2 h | `run_cpu.sbatch replay_sound.py $O/cert_heldout_new_v7.jsonl $O/sound_heldout_v7.jsonl` | `obsdet-v7sho-61888035.out` | CANCELLED 11:43 before start (lead: pause, certify.py will change again) |
| 61888036 | DuckDB replay, task-disjoint (1,321 kept) (afterok 61888033) | 8 CPU, 32 GB | 2 h | `run_cpu.sbatch replay_sound.py $O/cert_td_new_v7.jsonl $O/sound_td_v7.jsonl` | `obsdet-v7std-61888036.out` | CANCELLED 11:43 before start (lead: pause, certify.py will change again) |
| 61888037 | PostgreSQL replay, dev, existing server e1pg (6 DBs x sf1/perm42, pg_check first) (afterok 61888033) | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pg "<6 dbs>" $O/cert_probes_v7.jsonl $O/sound_pg_v7.jsonl` | `obsdet-v7pgdev-61888037.out` | CANCELLED 11:43 before start (lead: pause, certify.py will change again) |
| 61888038 | PostgreSQL replay, first held-out then task-disjoint, existing server e1pgh (11 DBs, pg_check first) (afterok 61888033) | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pgh "<11 dbs>" $O/cert_heldout_new_v7.jsonl $O/sound_pg_heldout_v7.jsonl $O/cert_td_new_v7.jsonl $O/sound_pg_td_v7.jsonl` | `obsdet-v7pgho-61888038.out` | CANCELLED 11:43 before start (lead: pause, certify.py will change again) |

### Pause (lead, 2026-09-25 ~11:42 PDT)

Property-based tests found that the rewrite (sqlglot regeneration of the statement) can change typed-literal casts and
auto-generated column names; certify.py v7 will change again (tie-break spliced into the statement as written).
Cancelled every queued job that runs certify.py; no E4 v7 job had been submitted. Kept: task selection, PostgreSQL
server checks (below), scripts.

### tasks_v4 (fixed 2026-09-25 11:42 PDT, before any agent run)

- `$V/runs/obsdet/v7/tasks_v4.json`, **md5 97910ed33f95dc2b7edb2ad73fb1f407**, 150 tasks, 0 question_ids shared with
  tasks_v2 or tasks_v3; note `tasks_v4_selection.json` (seed 3, procedure, per-database statistics, task ids, copy check).
- Procedure: prep_tasks4.py (md5 md5-withheld) = prep_tasks3.py with the exclusions extended to tasks_v2 and tasks_v3
  (question_ids; same question text or gold SQL: formula_1 1, toxicology 2) and seed 3; per-database targets = tasks_v2
  counts; top-up rule as tasks_v3.
- european_football_2: 0 (all 19 eligible tasks are in tasks_v2/v3; 110 of 110 remaining candidates fail on the
  3-table DuckDB conversion). Top-up (+1 each, largest tasks_v2 counts first): codebase_community:547, card_games:488,
  formula_1:982, student_club:1406, superhero:827, toxicology:330, california_schools:45, financial:192,
  debit_card_specializing:1477, thrombosis_prediction:1283.
- Per database: california_schools 11, card_games 19, codebase_community 21, debit_card_specializing 10,
  european_football_2 0, financial 11, formula_1 19, student_club 17, superhero 17, thrombosis_prediction 8,
  toxicology 17. Difficulty simple 89 / moderate 38 / challenging 23 (tasks_v3 83/41/26, tasks_v2 87/48/15).
- Physical-order copies: 22/22 ok again (same tables, counts, multisets; order differs).

| Job ID | Purpose | Resources | Walltime | Command | Log | Status / result |
|---|---|---|---|---|---|---|
| 61888111 | PostgreSQL server e1pg: start, pg_check (6 DBs x sf1/perm42), stop; no certify.py | 8 CPU, 40 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 4 h | `run_pg_v7.sbatch e1pg "<6 dbs>"` (no replay pairs) | `obsdet-pgchk-61888111.out` | FAILED 0:09 (my bug: psycopg imported before pg_setup adds its path); server started and stopped cleanly; rerun 61888138 |
| 61888113 | PostgreSQL server e1pgh: start, pg_check (11 DBs x sf1/perm42), stop; no certify.py | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pgh "<11 dbs>"` | `obsdet-pgchkh-61888113.out` | FAILED 0:08 (same bug); rerun 61888139 |
| 61888138 | e1pg check again (pg_check.py md5 952f142a85a2, import order fixed) | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pg "<6 dbs>"` | `obsdet-pgchk-61888138.out` | COMPLETED 0:20: all 12 databases ok (tables, row counts, keys) |
| 61888139 | e1pgh check again | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pgh "<11 dbs>"` | `obsdet-pgchkh-61888139.out` | COMPLETED 0:37: all 22 databases ok |

### Final v7 run (lead, 2026-09-25 ~11:45 PDT: final certify.py md5 1369ffcae12b93aec06735259c146814, 669 lines)

Every job checks `certify.py` against 1369ffcae12b93aec06735259c146814 at start (`md5sum -c`, job fails otherwise) and
prints the md5s of the modules it uses. Verified at submission (11:46 PDT): certify 1369ffcae12b, tool md5-withheld,
agent_det3 md5-withheld, analyze3 2210aba77af9, replay_sound md5-withheld, replay_pg md5-withheld, heldout_probes
5bf19bb17ed3, distribution 7fedeb45118a, cert_probes d8464edd20f0, heldout_dedup 31e6109e8111, td_filter
9c61c749027f, td2_filter e3feb86d0bb2, pg_check 952f142a85a2, pg_setup md5-withheld, pg_cost 0b919cdcae7d; sbatch:
run_agent3_v7 md5-withheld, run_v7_certs md5-withheld, run_pg_v7 md5-withheld, run_td2_build md5-withheld, run_cpu_v7
md5-withheld (new: run_cpu.sbatch + md5 check, logs in v7/logs). Task files: tasks_v2 3b638491274b, tasks_v3
bd7f698fda54, tasks_v4 97910ed33f95. GPU jobs: two chains (Qwen3-8B, phi-4), each td2 -> tasks_v2 -> tasks_v3
(afterany), so at most 2 GPU jobs run at once. The lead's adversarial run with the final version (job 61888108) is not
duplicated.

| Job ID | Purpose | Resources | Walltime | Command | Log | Status / result |
|---|---|---|---|---|---|---|
| 61888177 | v7 certificates: dev, first held-out (+ keep set), task-disjoint (+ keep set) | 8 CPU, 48 GB (<CPU_ACCOUNT>/<CPU_PARTITION>) | 2 h | `run_v7_certs.sbatch` | `obsdet-v7cert-61888177.out` | COMPLETED 1:52; certify.py OK. dev DET 166 / NARROW 511 / ALL 177 / UNSUPPORTED 161; held-out kept 1,125 (funnel 121/13/134 as v6): 189/383/204/349; task-disjoint kept 1,321 (funnel as v6): 313/471/215/322 |
| 61888178 | DuckDB replay dev, 7 cfg (afterok 61888177) | 8 CPU, 32 GB | 2 h | `run_cpu_v7.sbatch replay_sound.py $O/cert_probes_v7.jsonl $O/sound_v7.jsonl` | `obsdet-v7sdev-61888178.out` | COMPLETED 6:48; certified 0/854 (DET 0/166, NARROW 0/511, ALL 0/177), 0 censored; UNSUPPORTED fallback 39/161 |
| 61888179 | DuckDB replay first held-out (not-in-dev file) (afterok 61888177) | 8 CPU, 32 GB | 2 h | `run_cpu_v7.sbatch replay_sound.py $O/cert_heldout_new_v7.jsonl $O/sound_heldout_v7.jsonl` | `obsdet-v7sho-61888179.out` | COMPLETED 8:10; certified 0/787 over all 1,138 not-in-dev executable statements, 0 censored |
| 61888180 | DuckDB replay task-disjoint (afterok 61888177) | 8 CPU, 32 GB | 2 h | `run_cpu_v7.sbatch replay_sound.py $O/cert_td_new_v7.jsonl $O/sound_td_v7.jsonl` | `obsdet-v7std-61888180.out` | COMPLETED 3:37; certified 0/999 (DET 0/313, NARROW 0/471, ALL 0/215), 0 censored; UNSUPPORTED fallback 44/322 |
| 61888181 | PostgreSQL replay dev on e1pg (pg_check first) (afterok 61888177) | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pg "<6 dbs>" $O/cert_probes_v7.jsonl $O/sound_pg_v7.jsonl` | `obsdet-v7pgdev-61888181.out` | COMPLETED 28:10; pg_check all ok; certified 0 diverged (DET 0/155, NARROW 0/509, ALL 0/172; 17 censored); server stopped |
| 61888182 | PostgreSQL replay first held-out, then task-disjoint, on e1pgh (afterok 61888177) | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pgh "<11 dbs>" $O/cert_heldout_new_v7.jsonl $O/sound_pg_heldout_v7.jsonl $O/cert_td_new_v7.jsonl $O/sound_pg_td_v7.jsonl` | `obsdet-v7pgho-61888182.out` | COMPLETED 22:52; pg_check all ok; certified 0 diverged on held-out (keep set: 0/759, 10 censored) and task-disjoint (0/978, 16 censored); server stopped |
| 61888183 | E4 v7, Qwen3-8B, tasks_v4 | 1x <GPU>, 8 CPU, 64 GB (<GPU_ACCOUNT>/<GPU_PARTITION>) | 3 h | `run_agent3_v7.sbatch Qwen/Qwen3-8B v7td2_qwen3_8b $O/tasks_v4.json` | `obsdet-e4v7-61888183.out` | COMPLETED 9:09; no same-SQL observation change from a certified statement |
| 61888184 | E4 v7, phi-4, tasks_v4 | 1x <GPU>, 8 CPU, 64 GB | 3 h | `run_agent3_v7.sbatch microsoft/phi-4 v7td2_phi4 $O/tasks_v4.json` | `obsdet-e4v7-61888184.out` | COMPLETED 12:23; no same-SQL observation change from a certified statement |
| 61888185 | E4 v7, Qwen3-8B, tasks_v2 (afterany 61888183) | 1x <GPU>, 8 CPU, 64 GB | 3 h | `run_agent3_v7.sbatch Qwen/Qwen3-8B v7_qwen3_8b $R/tasks_v2.json` | `obsdet-e4v7-61888185.out` | COMPLETED 10:44; no same-SQL observation change from a certified statement |
| 61888186 | E4 v7, phi-4, tasks_v2 (afterany 61888184) | 1x <GPU>, 8 CPU, 64 GB | 3 h | `run_agent3_v7.sbatch microsoft/phi-4 v7_phi4 $R/tasks_v2.json` | `obsdet-e4v7-61888186.out` | COMPLETED 13:29; no same-SQL observation change from a certified statement |
| 61888187 | E4 v7, Qwen3-8B, tasks_v3 (afterany 61888185) | 1x <GPU>, 8 CPU, 64 GB | 3 h | `run_agent3_v7.sbatch Qwen/Qwen3-8B v7td_qwen3_8b $R/tasks_v3.json` | `obsdet-e4v7-61888187.out` | COMPLETED 8:43; no same-SQL observation change from a certified statement |
| 61888188 | E4 v7, phi-4, tasks_v3 (afterany 61888186) | 1x <GPU>, 8 CPU, 64 GB | 3 h | `run_agent3_v7.sbatch microsoft/phi-4 v7td_phi4 $R/tasks_v3.json` | `obsdet-e4v7-61888188.out` | COMPLETED 12:18; no same-SQL observation change from a certified statement |
| 61888189 | Second task-disjoint build: heldout_probes.py on v7td2 runs, td2_filter.py, distribution.py (afterok 61888183, 61888184, 61888177) | 8 CPU, 48 GB | 2 h | `run_td2_build.sbatch` | `obsdet-td2h-61888189.out` | COMPLETED 0:34; 1,468 distinct -> 1,267 kept |
| 61888190 | DuckDB replay second task-disjoint (afterok 61888189) | 8 CPU, 32 GB | 2 h | `run_cpu_v7.sbatch replay_sound.py $O/cert_td2_new.jsonl $O/sound_td2.jsonl` | `obsdet-v7std2-61888190.out` | COMPLETED 2:01; certified 0/945 (DET 0/269, NARROW 0/457, ALL 0/219), 0 censored; UNSUPPORTED fallback 31/322 |
| 61888191 | PostgreSQL replay second task-disjoint on e1pgh (afterok 61888189, afterany 61888182) | 8 CPU, 40 GB | 4 h | `run_pg_v7.sbatch e1pgh "<11 dbs>" $O/cert_td2_new.jsonl $O/sound_pg_td2.jsonl` | `obsdet-v7pgtd2-61888191.out` | COMPLETED 4:24; pg_check all ok; certified 0/930 (9 censored); server stopped |
| 61888841 | Certifier diff 1369ffca (runs) vs final candidate 5a2daa9e (lead's request): v7_diff2_ext.py (= lead's v7_diff2.py md5 de0f4277bab4 + reads cert_*.jsonl statement files; md5 md5-withheld) over dev, held-out, td, E4 v5/v6td traces and the 6 new E4 run dirs + cert_td2_all.jsonl (afterok 61888188) | 8 CPU, 32 GB | 2 h | `run_cpu_v7.sbatch v7_diff2_ext.py $O/certify_v7_1369ffca.py $O/certify_candidate.py $O/v7_diff2_newruns.json $O/e4/v7_* $O/e4/v7td_* $O/e4/v7td2_* $O/cert_td2_all.jsonl` | `obsdet-v7diff2-61888841.out` | COMPLETED 2:41; **0 differences** (verdict and tie-break, DuckDB and PostgreSQL dialects) on every set: dev 1,015, heldout_all 1,393, td_all 1,495, v5 606/1,007, v6td 584/948, v7 970/644, v7td 907/556, v7td2 931/563, cert_td2_all 1,468 |

All jobs above finished by 2026-09-25 12:24 PDT (diff job 12:27); no allocation of mine is running; both PostgreSQL servers
(e1pg, e1pgh) were stopped by their jobs and reused unchanged (not reloaded). Results: `results/v7/RESULTS_V7.md`.
