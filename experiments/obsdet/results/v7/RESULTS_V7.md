# Certifier v7 evaluation (final certify.py md5 1369ffcae12b93aec06735259c146814)

Date: 2026-09-25 (PDT). Every job ran between 11:46 and 12:27 PDT. Job log: `experiments/obsdet/JOBS_V7.md`.
Cluster outputs: `$V/runs/obsdet/v7/`. Local copies are in this directory (`results/v7/`). Code is in
`$V/code/obsdet_v7/`; new scripts are also in `code/` here (`code/MD5SUMS.txt`). All tables below come from
`code/v7_analyze.py`, whose full output is `v7_analyze_output.md` (machine-readable: `v7_summary.json`), unless
another source is named.

## Headline

- **No certified preview diverged anywhere.**
  - Statement sets: 0 of 3,574 supported statements on DuckDB (7 configurations, 0 censored) and 0 of 3,503 on
    PostgreSQL (5 configurations, 52 censored), over the four statement sets.
  - The clean test (second task-disjoint set, tasks_v4, whose statements were written after v7 was fixed) gives
    DuckDB 0/945 and PostgreSQL 0/930 (9 censored). The exact one-sided 95% upper bounds are 0.32% on each engine.
  - Agent runs: no same-SQL observation change originated in a DET/NARROW/ALL statement in any of the 6 E4 v7 runs
    (hybrid and strict, all groups). There is 0 unattributed divergence in every group.
- **The 3 v6 failures of the first task-disjoint set are now rejected.** In v7 they are UNSUPPORTED:
  float-aggregate (DECIMAL division) for 2, distinct-order-by-non-output for 1. Their smart-lex fallbacks are
  counted in the UNSUPPORTED columns.
- **Accuracy costs are unchanged in character.** The hybrid never differs from raw by more than about 3 points
  (every CI contains 0 except Qwen3-8B on tasks_v3, +3.1 pp [+0.7, +6.2]).
  - Strict is free for Qwen3-8B on tasks_v2 and tasks_v3, but −2.9 pp [−7.3, +1.3] vs raw and −3.8 pp [−7.6, −0.4]
    vs hybrid on tasks_v4.
  - Strict costs phi-4 3–7 points against hybrid in all three task sets.
- **Final-candidate check.** The final candidate certifier (5a2daa9e) gives identical verdicts and tie-breaks to
  1369ffca on every statement set and every new run, in both dialects (section 6).

## 1. Setup and checks

- **Certifier.** Every job checks `certify.py` against md5 1369ffcae12b93aec06735259c146814 with `md5sum -c` (the job
  fails otherwise). All 16 job logs show `certify.py: OK`. The certificate job also printed the md5 of the module
  actually imported (1369ffca, from code/obsdet_v7).
- **Code versions.**

  | Group | Files and md5 |
  |---|---|
  | Changed for v7 | certify.py 1369ffcae12b; agent_det3.py md5-withheld (differs from v6 only in its sys.path line) |
  | Unchanged from v6 | tool.py md5-withheld, analyze3.py 2210aba77af9, replay_sound.py md5-withheld, replay_pg.py md5-withheld, heldout_probes.py 5bf19bb17ed3, distribution.py 7fedeb45118a, cert_probes.py d8464edd20f0, heldout_dedup.py 31e6109e8111, td_filter.py 9c61c749027f, pg_setup.py md5-withheld, pg_cost.py 0b919cdcae7d |
  | New scripts | prep_tasks4.py, td2_filter.py, pg_check.py, run_*_v7.sbatch, run_td2_build.sbatch, v7_diff2_ext.py, v7_analyze.py (md5s in `code/MD5SUMS.txt`) |

- **Task files.** tasks_v2 3b638491274b, tasks_v3 bd7f698fda54, tasks_v4 97910ed33f95.
- **PostgreSQL.** The existing servers e1pg (dev: 6 databases × sf1/perm42) and e1pgh (11 databases × sf1/perm42)
  were reused without reloading. Before every replay, `pg_check.py` verified all 12 / 22 databases: same tables and
  row counts as the DuckDB sources, declared keys present (jobs 61888138/9, and again inside each replay job).
  Servers were stopped on exit.
- **Interim run, not used.** An earlier certificate run with the interim certify.py 0353e3ee (job 61888033) was
  paused at the lead's request. Its outputs are in `$V/runs/obsdet/v7/interim_0353e3ee/` and are not used here.
  Five queued jobs were cancelled before they started.
- **Selection of tasks_v4** (job 61888032, `tasks_v4_selection.json`, fixed at 11:42 before any run):
  - `prep_tasks4.py` is prep_tasks3.py with seed 3 and exclusions extended to tasks_v2 and tasks_v3 (question_ids,
    plus the same question text or gold SQL: 1 in formula_1, 2 in toxicology).
  - The file is 150 tasks, md5 97910ed33f95dc2b7edb2ad73fb1f407, with 0 question_ids shared with tasks_v2 or
    tasks_v3.
  - european_football_2 has no eligible task left, because its DuckDB conversion has only 3 of the 7 BIRD tables.
    The top-up rule adds one task each to the other 10 databases.
  - Per database: california_schools 11, card_games 19, codebase_community 21, debit_card_specializing 10,
    european_football_2 0, financial 11, formula_1 19, student_club 17, superhero 17, thrombosis_prediction 8,
    toxicology 17.
  - Difficulty: simple 89 / moderate 38 / challenging 23.
  - All 22 physical-order copies were verified again.

## 2. Soundness per statement set and engine

Counts come from `figures/gen_table_soundness.py` `row()`, imported unchanged (md5 a9a0dbd3f929). The keep set is
each set's statements:
- dev: all 1,015;
- first held-out: the heldout_dedup keep set, 1,125, from `cert_heldout_kept_v7.jsonl` (td_filter.py with no prior
  set, which reproduces heldout_dedup's 121/13/134 funnel);
- first task-disjoint: 1,321 (`cert_td_new_v7.jsonl`, the same statements as v6);
- second task-disjoint: 1,267 (`cert_td2_new.jsonl`).

Replays: replay_sound.py (DuckDB, 7 configurations) and replay_pg.py (PostgreSQL, 5 configurations, certificates in
the PostgreSQL dialect computed by the v7 certifier inside replay_pg.py).

| Statement set | Engine (configurations; source file) | Supported n (cens.) | Certified diverged | Smart-lex diverged | Raw diverged | UNSUPPORTED n (cens.) | Raw diverged | Smart-lex diverged |
|---|---|---|---|---|---|---|---|---|
| Development probes (1,015) | DuckDB (7; `sound_v7.jsonl`) | 854 (0) | **0** | 0 | 378 | 161 (0) | 69 | 39 |
|  | PostgreSQL (5; `sound_pg_v7.jsonl`) | 836 (17) | **0** | 0 | 285 | 157 (5) | 51 | 32 |
| First held-out (1,125) | DuckDB (7; `sound_heldout_v7.jsonl`) | 776 (0) | **0** | 0 | 292 | 349 (0) | 134 | 66 |
|  | PostgreSQL (5; `sound_pg_heldout_v7.jsonl`) | 759 (10) | **0** | 0 | 237 | 346 (10) | 77 | 42 |
| First task-disjoint (1,321) | DuckDB (7; `sound_td_v7.jsonl`) | 999 (0) | **0** | 0 | 394 | 322 (0) | 92 | 44 |
|  | PostgreSQL (5; `sound_pg_td_v7.jsonl`) | 978 (16) | **0** | 0 | 301 | 295 (32) | 61 | 32 |
| Second task-disjoint, clean test (1,267) | DuckDB (7; `sound_td2.jsonl`) | 945 (0) | **0** | 0 | 344 | 322 (0) | 79 | 31 |
|  | PostgreSQL (5; `sound_pg_td2.jsonl`) | 930 (9) | **0** | 0 | 276 | 302 (26) | 58 | 24 |

**Zero-count bounds.** Exact one-sided 95% upper bounds, iid-per-statement reference only (statements are clustered
by task, model and database):

| Set | DuckDB | PostgreSQL |
|---|---|---|
| dev | 0.35% (0/854) | 0.36% (0/836) |
| held-out | 0.39% (0/776) | 0.39% (0/759) |
| first task-disjoint | 0.30% (0/999) | 0.31% (0/978) |
| second task-disjoint | 0.32% (0/945) | 0.32% (0/930) |
| all sets pooled | 0.08% (0/3,574) | 0.09% (0/3,503) |

Per-verdict tables (heldout_dedup.table) are in `v7_analyze_output.md` and section 7 below.

## 3. Verdict distributions and tie-break widths (DuckDB dialect, v7)

Source: distribution.py output for each set. For the held-out and task-disjoint sets it was run on the kept
statements.

| Statement set (source file) | DET | NARROW | ALL | UNSUPPORTED | Repaired: mean appended sort columns, certified vs smart-lex | Key tie-breaks (non-output key) | No-keys ablation DET/NARROW/ALL/UNS (mean width) |
|---|---|---|---|---|---|---|---|
| Development probes (1,015) (`distribution_v7.json`) | 166 (16.4%) | 511 (50.3%) | 177 (17.4%) | 161 (15.9%) | 1.22 vs 2.96 (n = 688) | 464 (307) | 129/296/429/161 (2.48) |
| First held-out (1,125) (`distribution_heldout_v7.json`) | 189 (16.8%) | 383 (34.0%) | 204 (18.1%) | 349 (31.0%) | 1.11 vs 2.3 (n = 587) | 400 (230) | 153/205/418/349 (1.87) |
| First task-disjoint (1,321) (`distribution_td_v7.json`) | 313 (23.7%) | 471 (35.7%) | 215 (16.3%) | 322 (24.4%) | 1.12 vs 2.5 (n = 686) | 430 (262) | 244/220/535/322 (2.05) |
| Second task-disjoint, clean test (1,267) (`distribution_td2.json`) | 269 (21.2%) | 457 (36.1%) | 219 (17.3%) | 322 (25.4%) | 1.11 vs 2.58 (n = 676) | 465 (277) | 205/211/529/322 (2.16) |

**UNSUPPORTED reasons** (prefix before ':'):

- Development probes (1,015): derived-table 64, float-aggregate 48, unresolved 18, multi-statement 7, outer-or-special-join 6, nested-limit 6, cte 4, not-select 3, inexact-group-key 2, no-base-table 2, distinct-order-by-non-output 1
- First held-out (1,125): derived-table 133, no-base-table 85, float-aggregate 41, cte 34, outer-or-special-join 16, not-select 14, volatile 6, multi-statement 5, construct 5, unresolved 4, nested-limit 2, function 2, aggregate 1, distinct-order-by-non-output 1
- First task-disjoint (1,321): derived-table 123, no-base-table 85, cte 43, float-aggregate 37, nested-limit 9, outer-or-special-join 8, unresolved 6, not-select 5, multi-statement 2, function 2, distinct-order-by-non-output 2
- Second task-disjoint, clean test (1,267): derived-table 118, no-base-table 80, cte 30, float-aggregate 24, construct 15, outer-or-special-join 13, unresolved 12, not-select 9, function 9, multi-statement 3, nested-limit 3, distinct-order-by-non-output 2, inexact-group-key 2, unknown-table 2

**Changes of verdict from v6 (certify 7aa9c889) to v7 on the same statements.** Source: this directory's cert files
vs `results/final/cert_*` and `results/final/taskdisjoint/cert_td_all.jsonl`.

| Set | Verdict changes (all to UNSUPPORTED) |
|---|---|
| dev | 1: NARROW, distinct-order-by-non-output (formula_1 `SELECT DISTINCT ... ORDER BY l.milliseconds LIMIT 1`) |
| held-out | 1: NARROW, distinct-order-by-non-output (formula_1) |
| first task-disjoint | 4: the 3 v6 failures (2 DET float-aggregate, 1 ALL distinct-order-by-non-output) plus the financial `SELECT DISTINCT d.A3 ... ORDER BY COUNT(l.loan_id) DESC LIMIT 1` (ALL, distinct-order-by-non-output) |

Every other certified statement keeps its verdict. Its rewrite text changes, because the tie-break is now spliced
into the statement as written. The tie-break itself changes for 56 (dev), 57 (held-out) and 79 (task-disjoint)
statements: group-key tie-breaks are now plain columns or output positions.

The lead's `v7_diff.json` (job 61888107, in this directory) has the full per-statement v6-vs-v7 comparison,
including the PostgreSQL dialect.

## 4. Agent level: E4 v7 (15 conditions, same flags as E4 v5)

Runs:

| Run | Job | Source |
|---|---|---|
| tasks_v2, Qwen3-8B | 61888185 | `e4_v7_qwen3_8b/summary_e4.json` |
| tasks_v2, phi-4 | 61888186 | `e4_v7_phi4/summary_e4.json` |
| tasks_v3, Qwen3-8B | 61888187 | `e4_v7td_qwen3_8b/summary_e4.json` |
| tasks_v3, phi-4 | 61888188 | `e4_v7td_phi4/summary_e4.json` |
| tasks_v4, Qwen3-8B | 61888183 | `e4_v7td2_qwen3_8b/summary_e4.json` |
| tasks_v4, phi-4 | 61888184 | `e4_v7td2_phi4/summary_e4.json` |

Scripts and conventions:
- analyze3.py (frozen) and strict_burden.py (frozen copy `results/final/code/strict_burden.py`, output captured by
  v7_analyze.py).
- The certified-change scan in v7_analyze.py `certified_changes()` recomputes analyze3's same-SQL comparison and
  lists pairs whose statement was DET/NARROW/ALL in both runs.
- Counts are tasks out of 150; "cens." means the final result had more than 1,000 rows.
- Accuracy is BIRD execution accuracy (set), with bag in parentheses; min–max over the conditions of each policy.
- Paired differences are over the three physical orders at 1 thread (task-clustered bootstrap, 2,000 resamples,
  seed 0).

#### E4 v7 on tasks_v2 (E4 original tasks) (runs e4_v7_qwen3_8b, e4_v7_phi4)

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 61 / 57 / 43 / 16 | 31 / 27 / 17 (cens. 1) / 4 |
| smart-lex, 3 physical orders | 5 / 5 / 5 / 0 | 1 / 1 / 1 / 0 |
| hybrid (certified), 3 physical orders | 6 / 6 / 5 / 1 | 1 / 1 / 1 / 0 |
| strict (fail-closed), 3 physical orders | 2 / 2 / 1 / 0 | 0 / 0 / 0 / 0 |
| raw, 1 vs 8 threads | 23 / 21 / 11 / 1 | 8 / 7 / 6 / 0 |
| hybrid, 1 vs 8 threads | 2 / 2 / 2 / 0 | 1 / 1 / 1 / 0 |
| strict, 1 vs 8 threads | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

| Group | Qwen3-8B unattributed; same-SQL observation-change sources | phi-4 unattributed; same-SQL observation-change sources |
|---|---|---|
| raw, 3 physical orders | 0/150; {"raw": 70, "runtime-error": 2} | 0/150; {"raw": 55} |
| smart-lex, 3 physical orders | 0/150; {"smartlex": 8, "runtime-error": 2} | 0/150; {"smartlex": 8} |
| hybrid (certified), 3 physical orders | 0/150; {"UNSUPPORTED": 7, "runtime-error": 2} | 0/150; {"UNSUPPORTED": 8} |
| strict (fail-closed), 3 physical orders | 0/150; {"runtime-error": 2} | 0/150; {} |
| raw, 1 vs 8 threads | 0/150; {"raw": 35} | 0/150; {"raw": 22} |
| hybrid, 1 vs 8 threads | 0/150; {"runtime-error": 1, "UNSUPPORTED": 3} | 0/150; {"UNSUPPORTED": 4} |
| strict, 1 vs 8 threads | 0/150; {} | 0/150; {} |

| Accuracy, set (bag) | Qwen3-8B | phi-4 |
|---|---|---|
| raw (4 conditions) | 0.507–0.533 (0.480–0.513) | 0.433–0.453 (0.433–0.447) |
| smart-lex (3) | 0.533 (0.507) | 0.440 (0.433) |
| hybrid (4) | 0.513–0.520 (0.487–0.493) | 0.453 (0.447) |
| strict (4) | 0.547 (0.513) | 0.413 (0.400) |

| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | Qwen3-8B | phi-4 |
|---|---|---|
| cer-raw | -0.9 pp [-4.2, +2.2] | +0.9 pp [-0.2, +2.4] |
| slx-raw | +0.9 pp [-2.9, +4.9] | -0.4 pp [-2.2, +1.1] |
| cer-slx | -1.8 pp [-4.7, +0.7] | +1.3 pp [+0.0, +3.3] |
| str-raw | +2.2 pp [-1.8, +6.2] | -3.1 pp [-6.9, -0.0] |
| str-cer | +3.1 pp [+0.0, +6.4] | -4.0 pp [-7.3, -1.3] |

- Qwen3-8B: statements under hybrid/strict by verdict {"cer": {"UNSUPPORTED": 625, "NARROW": 768, "ALL": 380, "DET": 613}, "str": {"UNSUPPORTED": 181, "NARROW": 864, "ALL": 400, "DET": 769, "UNSUPPORTED/refused": 596}}
- Qwen3-8B: strict burden (strict_burden.py): 66/150 tasks with >=1 withheld preview; median 1.5 (max 6) among them; hybrid-correct -> strict-wrong 1, hybrid-wrong -> strict-correct 5
- Qwen3-8B: same-SQL observation changes from CERTIFIED statements: 0
- phi-4: statements under hybrid/strict by verdict {"cer": {"UNSUPPORTED": 507, "NARROW": 556, "ALL": 256, "DET": 388}, "str": {"UNSUPPORTED": 152, "NARROW": 652, "ALL": 316, "UNSUPPORTED/refused": 624, "DET": 512}}
- phi-4: strict burden (strict_burden.py): 57/150 tasks with >=1 withheld preview; median 2 (max 8) among them; hybrid-correct -> strict-wrong 6, hybrid-wrong -> strict-correct 0
- phi-4: same-SQL observation changes from CERTIFIED statements: 0

#### E4 v7 on tasks_v3 (first task-disjoint set) (runs e4_v7td_qwen3_8b, e4_v7td_phi4)

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 53 / 49 / 29 / 13 | 38 / 30 / 17 (cens. 1) / 8 |
| smart-lex, 3 physical orders | 4 / 4 / 4 / 1 | 1 / 1 / 0 (cens. 1) / 0 |
| hybrid (certified), 3 physical orders | 3 / 3 / 4 / 1 | 2 / 1 / 0 (cens. 1) / 0 |
| strict (fail-closed), 3 physical orders | 2 / 2 / 2 / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| raw, 1 vs 8 threads | 32 / 28 / 13 / 6 | 10 / 6 / 5 (cens. 1) / 2 |
| hybrid, 1 vs 8 threads | 1 / 1 / 1 / 1 | 0 / 0 / 0 (cens. 1) / 0 |
| strict, 1 vs 8 threads | 0 / 0 / 0 / 0 | 0 / 0 / 0 (cens. 1) / 0 |

| Group | Qwen3-8B unattributed; same-SQL observation-change sources | phi-4 unattributed; same-SQL observation-change sources |
|---|---|---|
| raw, 3 physical orders | 0/150; {"raw": 69, "runtime-error": 2} | 0/150; {"raw": 57} |
| smart-lex, 3 physical orders | 0/150; {"smartlex": 7, "runtime-error": 3} | 0/150; {"smartlex": 3} |
| hybrid (certified), 3 physical orders | 0/150; {"UNSUPPORTED": 5, "runtime-error": 2} | 0/150; {"UNSUPPORTED": 3} |
| strict (fail-closed), 3 physical orders | 0/150; {"runtime-error": 2} | 0/150; {} |
| raw, 1 vs 8 threads | 0/150; {"raw": 38, "runtime-error": 1} | 0/150; {"raw": 20} |
| hybrid, 1 vs 8 threads | 0/150; {"runtime-error": 1} | 0/150; {} |
| strict, 1 vs 8 threads | 0/150; {} | 0/150; {} |

| Accuracy, set (bag) | Qwen3-8B | phi-4 |
|---|---|---|
| raw (4 conditions) | 0.613–0.660 (0.587–0.627) | 0.447–0.467 (0.407–0.433) |
| smart-lex (3) | 0.647–0.653 (0.607–0.613) | 0.453 (0.413) |
| hybrid (4) | 0.660–0.667 (0.627–0.633) | 0.467 (0.427) |
| strict (4) | 0.653 (0.620) | 0.400 (0.360) |

| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | Qwen3-8B | phi-4 |
|---|---|---|
| cer-raw | +3.1 pp [+0.7, +6.2] | +1.3 pp [-0.9, +3.8] |
| slx-raw | +1.8 pp [-0.9, +4.7] | -0.0 pp [-2.9, +2.7] |
| cer-slx | +1.3 pp [+0.0, +3.3] | +1.3 pp [+0.0, +3.3] |
| str-raw | +2.2 pp [-1.1, +6.0] | -5.3 pp [-9.6, -1.1] |
| str-cer | -0.9 pp [-3.3, +1.3] | -6.7 pp [-10.7, -2.7] |

- Qwen3-8B: statements under hybrid/strict by verdict {"cer": {"NARROW": 784, "DET": 549, "UNSUPPORTED": 509, "ALL": 424}, "str": {"NARROW": 849, "DET": 723, "UNSUPPORTED": 180, "ALL": 440, "UNSUPPORTED/refused": 420}}
- Qwen3-8B: strict burden (strict_burden.py): 57/150 tasks with >=1 withheld preview; median 1 (max 5) among them; hybrid-correct -> strict-wrong 2, hybrid-wrong -> strict-correct 1
- Qwen3-8B: same-SQL observation changes from CERTIFIED statements: 0
- phi-4: statements under hybrid/strict by verdict {"cer": {"NARROW": 536, "UNSUPPORTED": 322, "ALL": 320, "DET": 400}, "str": {"NARROW": 604, "UNSUPPORTED": 84, "ALL": 356, "DET": 456, "UNSUPPORTED/refused": 432}}
- phi-4: strict burden (strict_burden.py): 42/150 tasks with >=1 withheld preview; median 1.0 (max 8) among them; hybrid-correct -> strict-wrong 10, hybrid-wrong -> strict-correct 0
- phi-4: same-SQL observation changes from CERTIFIED statements: 0

#### E4 v7 on tasks_v4 (second task-disjoint set) (runs e4_v7td2_qwen3_8b, e4_v7td2_phi4)

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 52 / 42 / 28 (cens. 2) / 8 | 23 / 23 / 15 (cens. 1) / 4 |
| smart-lex, 3 physical orders | 2 / 2 / 2 (cens. 2) / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| hybrid (certified), 3 physical orders | 3 / 3 / 4 (cens. 2) / 1 | 0 / 0 / 0 (cens. 1) / 0 |
| strict (fail-closed), 3 physical orders | 1 / 1 / 1 (cens. 2) / 0 | 1 / 1 / 0 (cens. 1) / 0 |
| raw, 1 vs 8 threads | 21 / 16 / 9 (cens. 1) / 0 | 6 / 5 / 2 (cens. 1) / 1 |
| hybrid, 1 vs 8 threads | 0 / 0 / 0 (cens. 2) / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| strict, 1 vs 8 threads | 0 / 0 / 0 (cens. 2) / 0 | 0 / 0 / 0 (cens. 1) / 0 |

| Group | Qwen3-8B unattributed; same-SQL observation-change sources | phi-4 unattributed; same-SQL observation-change sources |
|---|---|---|
| raw, 3 physical orders | 0/150; {"raw": 68} | 0/150; {"raw": 53} |
| smart-lex, 3 physical orders | 0/150; {"runtime-error": 1, "smartlex": 3} | 0/150; {"runtime-error": 1, "smartlex": 3} |
| hybrid (certified), 3 physical orders | 0/150; {"UNSUPPORTED": 4, "runtime-error": 1} | 0/150; {"runtime-error": 1, "UNSUPPORTED": 3} |
| strict (fail-closed), 3 physical orders | 0/150; {"runtime-error": 1} | 0/150; {"runtime-error": 1} |
| raw, 1 vs 8 threads | 0/150; {"raw": 33} | 0/150; {"raw": 17} |
| hybrid, 1 vs 8 threads | 0/150; {"UNSUPPORTED": 1} | 0/150; {"UNSUPPORTED": 2} |
| strict, 1 vs 8 threads | 0/150; {} | 0/150; {} |

| Accuracy, set (bag) | Qwen3-8B | phi-4 |
|---|---|---|
| raw (4 conditions) | 0.420–0.447 (0.393–0.440) | 0.413–0.427 (0.393–0.407) |
| smart-lex (3) | 0.440 (0.427) | 0.420 (0.407) |
| hybrid (4) | 0.440–0.447 (0.440–0.447) | 0.420 (0.400) |
| strict (4) | 0.407 (0.400) | 0.387 (0.373) |

| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | Qwen3-8B | phi-4 |
|---|---|---|
| cer-raw | +0.9 pp [-2.0, +3.8] | +0.0 pp [-1.3, +1.3] |
| slx-raw | +0.4 pp [-2.7, +3.6] | +0.0 pp [-1.3, +1.3] |
| cer-slx | +0.4 pp [+0.0, +1.3] | +0.0 pp [+0.0, +0.0] |
| str-raw | -2.9 pp [-7.3, +1.3] | -3.3 pp [-6.7, -0.4] |
| str-cer | -3.8 pp [-7.6, -0.4] | -3.3 pp [-6.7, -0.7] |

- Qwen3-8B: statements under hybrid/strict by verdict {"cer": {"NARROW": 865, "UNSUPPORTED": 543, "ALL": 464, "DET": 624}, "str": {"NARROW": 917, "UNSUPPORTED": 248, "ALL": 476, "DET": 720, "UNSUPPORTED/refused": 503}}
- Qwen3-8B: strict burden (strict_burden.py): 59/150 tasks with >=1 withheld preview; median 1 (max 7) among them; hybrid-correct -> strict-wrong 7, hybrid-wrong -> strict-correct 1
- Qwen3-8B: same-SQL observation changes from CERTIFIED statements: 0
- phi-4: statements under hybrid/strict by verdict {"cer": {"NARROW": 488, "UNSUPPORTED": 420, "ALL": 268, "DET": 412}, "str": {"NARROW": 596, "UNSUPPORTED": 172, "ALL": 276, "UNSUPPORTED/refused": 552, "DET": 504}}
- phi-4: strict burden (strict_burden.py): 55/150 tasks with >=1 withheld preview; median 1 (max 8) among them; hybrid-correct -> strict-wrong 5, hybrid-wrong -> strict-correct 0
- phi-4: same-SQL observation changes from CERTIFIED statements: 0

**Reading.**
- Hybrid changes (3 physical orders) are few: tasks_v2 6 and 1; tasks_v3 3 and 2; tasks_v4 3 and 0 (Qwen3-8B and
  phi-4). All come from UNSUPPORTED statements (smart-lex fallback) or runtime errors that quote data values.
- A final result can change with an unchanged trajectory when the final answer is itself UNSUPPORTED and
  order-dependent (e.g. Qwen3-8B tasks_v3 hybrid 3 / 3 / 4).
- Strict changes are 2 / 0, 2 / 0, 1 / 1, all from runtime errors.
- Raw changes 23–61 trajectories per model and task set, so the E4 v5 conclusions replicate on all three task sets
  under v7.

## 5. Second task-disjoint set: selection funnel (job 61888189, `td2_funnel.json`, td2_filter.py)

| Stage | Count |
|---|---|
| Distinct (db, statement) issued by the v7td2 agents (2 models, 15 conditions) | 1,468 |
| − development probe, exact / normalized (heldout_dedup.norm) | 3 / 6 |
| − first held-out statement, exact / normalized | 14 / 4 |
| − first task-disjoint statement (cert_td_all.jsonl, all 1,495), exact / normalized | 5 / 4 |
| − fails on SF1 | 165 |
| **Kept** | **1,267** (1,244 distinct after norm; 14,250 occurrences) |

- Kept by model: Qwen3-8B 801, phi-4 489 (23 issued by both).
- Kept by database: california_schools 146, card_games 147, codebase_community 129, debit_card_specializing 137,
  financial 116, formula_1 148, student_club 131, superhero 99, thrombosis_prediction 81, toxicology 133.
- Rewrites failed: 0.
- Per model, statements executed under hybrid (distribution_td2.json `e4_by_model`, v7 verdicts at run time):

  | Model | DET | NARROW | ALL | UNSUPPORTED | n |
  |---|---|---|---|---|---|
  | Qwen3-8B | 22.9% | 35.7% | 17.9% | 23.5% | 532 |
  | phi-4 | 24.8% | 30.7% | 17.5% | 27.0% | 355 |

- Occurrence-weighted verdicts: DET 27.4%, NARROW 35.5%, ALL 17.9%, UNSUPPORTED 19.2%.

## 6. Final-candidate certifier diff (lead's request; job 61888841)

- **Script.** `v7_diff2_ext.py` is the lead's `$V/runs/obsdet/v7/v7_diff2.py` (md5 de0f4277bab4) extended by two
  lines to accept `cert_*.jsonl` statement files among the extra arguments (md5 md5-withheld).
- **Inputs.** Old = `certify_v7_1369ffca.py` (1369ffca); new = `certify_candidate.py` (5a2daa9e, identical to
  `$V/code/obsdet_v7final/certify.py`). Extra inputs: the six new E4 run directories and `cert_td2_all.jsonl`.
- **Output.** `v7_diff2_newruns.json`; log `logs/obsdet-v7diff2-61888841.out`.
- **Result.** It compares (verdict, tie-break) in both the DuckDB and PostgreSQL dialects. **0 differences in every
  set:**

  | Set | Statements | Differences |
  |---|---|---|
  | dev | 1,015 | 0 |
  | heldout_all | 1,393 | 0 |
  | td_all | 1,495 | 0 |
  | E4 v5_qwen3_8b / v5_phi4 | 1,007 / 606 | 0 |
  | E4 v6td_qwen3_8b / v6td_phi4 | 948 / 584 | 0 |
  | E4 v7_qwen3_8b / v7_phi4 | 970 / 644 | 0 |
  | E4 v7td_qwen3_8b / v7td_phi4 | 907 / 556 | 0 |
  | E4 v7td2_qwen3_8b / v7td2_phi4 | 931 / 563 | 0 |
  | cert_td2_all.jsonl (all distinct td2 statements) | 1,468 | 0 |

## 7. Per-statement-set details (heldout_dedup.table per engine; from v7_analyze_output.md)

#### Development probes (`cert_probes_v7.jsonl`)

Verdicts (1015): DET 166 (16.4%), NARROW 511 (50.3%), ALL 177 (17.4%), UNSUPPORTED 161 (15.9%)
Repaired 688: mean appended sort columns 1.22 vs smart-lex 2.96; key tie-breaks 464 (non-output key 307)
UNSUPPORTED reasons: {"derived-table": 64, "float-aggregate": 48, "unresolved": 18, "multi-statement": 7, "outer-or-special-join": 6, "nested-limit": 6, "cte": 4, "not-select": 3, "inexact-group-key": 2, "no-base-table": 2, "distinct-order-by-non-output": 1}
No-keys ablation: DET 129, NARROW 296, ALL 429, UNSUPPORTED 161; mean width 2.48

duckdb: statements in file and keep set 1015 of 1015; row() = {"sup": 854, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 378, "uns": 161, "uns_cens": 0, "uns_raw": 69, "uns_slx": 39}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/166(0) NARROW=266/511(0) ALL=112/177(0) UNSUPPORTED=69/161(0)
  smartlex DET=0/166(0) NARROW=0/511(0) ALL=0/177(0) UNSUPPORTED=39/161(0)
  certifiedDET=0/166(0) NARROW=0/511(0) ALL=0/177(0) UNSUPPORTED=39/161(0)
```
postgres: statements in file and keep set 1015 of 1015; row() = {"sup": 836, "sup_cens": 17, "cer": 0, "slx": 0, "raw": 285, "uns": 157, "uns_cens": 5, "uns_raw": 51, "uns_slx": 32}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/155(11) NARROW=228/509(3) ALL=57/172(3) UNSUPPORTED=51/157(5)
  smartlex DET=0/155(11) NARROW=0/509(3) ALL=0/172(3) UNSUPPORTED=32/157(5)
  certifiedDET=0/155(11) NARROW=0/509(3) ALL=0/172(3) UNSUPPORTED=32/157(5)
```

#### First held-out (`cert_heldout_kept_v7.jsonl`)

Verdicts (1125): DET 189 (16.8%), NARROW 383 (34.0%), ALL 204 (18.1%), UNSUPPORTED 349 (31.0%)
Repaired 587: mean appended sort columns 1.11 vs smart-lex 2.3; key tie-breaks 400 (non-output key 230)
UNSUPPORTED reasons: {"derived-table": 133, "no-base-table": 85, "float-aggregate": 41, "cte": 34, "outer-or-special-join": 16, "not-select": 14, "volatile": 6, "multi-statement": 5, "construct": 5, "unresolved": 4, "nested-limit": 2, "function": 2, "aggregate": 1, "distinct-order-by-non-output": 1}
No-keys ablation: DET 153, NARROW 205, ALL 418, UNSUPPORTED 349; mean width 1.87

duckdb: statements in file and keep set 1125 of 1125; row() = {"sup": 776, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 292, "uns": 349, "uns_cens": 0, "uns_raw": 134, "uns_slx": 66}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/189(0) NARROW=178/383(0) ALL=114/204(0) UNSUPPORTED=134/349(0)
  smartlex DET=0/189(0) NARROW=0/383(0) ALL=0/204(0) UNSUPPORTED=66/349(0)
  certifiedDET=0/189(0) NARROW=0/383(0) ALL=0/204(0) UNSUPPORTED=65/349(0)
```
postgres: statements in file and keep set 1125 of 1125; row() = {"sup": 759, "sup_cens": 10, "cer": 0, "slx": 0, "raw": 237, "uns": 346, "uns_cens": 10, "uns_raw": 77, "uns_slx": 42}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/183(2) NARROW=155/373(8) ALL=82/203(0) UNSUPPORTED=77/346(10)
  smartlex DET=0/183(2) NARROW=0/373(8) ALL=0/203(0) UNSUPPORTED=42/346(10)
  certifiedDET=0/183(2) NARROW=0/373(8) ALL=0/203(0) UNSUPPORTED=42/346(10)
```

#### First task-disjoint (`cert_td_new_v7.jsonl`)

Verdicts (1321): DET 313 (23.7%), NARROW 471 (35.7%), ALL 215 (16.3%), UNSUPPORTED 322 (24.4%)
Repaired 686: mean appended sort columns 1.12 vs smart-lex 2.5; key tie-breaks 430 (non-output key 262)
UNSUPPORTED reasons: {"derived-table": 123, "no-base-table": 85, "cte": 43, "float-aggregate": 37, "nested-limit": 9, "outer-or-special-join": 8, "unresolved": 6, "not-select": 5, "multi-statement": 2, "function": 2, "distinct-order-by-non-output": 2}
No-keys ablation: DET 244, NARROW 220, ALL 535, UNSUPPORTED 322; mean width 2.05

duckdb: statements in file and keep set 1321 of 1321; row() = {"sup": 999, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 394, "uns": 322, "uns_cens": 0, "uns_raw": 92, "uns_slx": 44}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/313(0) NARROW=259/471(0) ALL=135/215(0) UNSUPPORTED=92/322(0)
  smartlex DET=0/313(0) NARROW=0/471(0) ALL=0/215(0) UNSUPPORTED=44/322(0)
  certifiedDET=0/313(0) NARROW=0/471(0) ALL=0/215(0) UNSUPPORTED=44/322(0)
```
postgres: statements in file and keep set 1321 of 1321; row() = {"sup": 978, "sup_cens": 16, "cer": 0, "slx": 0, "raw": 301, "uns": 295, "uns_cens": 32, "uns_raw": 61, "uns_slx": 32}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/304(4) NARROW=221/462(9) ALL=80/213(2) UNSUPPORTED=61/295(32)
  smartlex DET=0/304(4) NARROW=0/461(10) ALL=0/213(2) UNSUPPORTED=32/295(32)
  certifiedDET=0/304(4) NARROW=0/461(10) ALL=0/213(2) UNSUPPORTED=32/295(32)
```

#### Second task-disjoint (clean test) (`cert_td2_new.jsonl`)

Verdicts (1267): DET 269 (21.2%), NARROW 457 (36.1%), ALL 219 (17.3%), UNSUPPORTED 322 (25.4%)
Repaired 676: mean appended sort columns 1.11 vs smart-lex 2.58; key tie-breaks 465 (non-output key 277)
UNSUPPORTED reasons: {"derived-table": 118, "no-base-table": 80, "cte": 30, "float-aggregate": 24, "construct": 15, "outer-or-special-join": 13, "unresolved": 12, "not-select": 9, "function": 9, "multi-statement": 3, "nested-limit": 3, "distinct-order-by-non-output": 2, "inexact-group-key": 2, "unknown-table": 2}
No-keys ablation: DET 205, NARROW 211, ALL 529, UNSUPPORTED 322; mean width 2.16

duckdb: statements in file and keep set 1267 of 1267; row() = {"sup": 945, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 344, "uns": 322, "uns_cens": 0, "uns_raw": 79, "uns_slx": 31}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/269(0) NARROW=224/457(0) ALL=120/219(0) UNSUPPORTED=79/322(0)
  smartlex DET=0/269(0) NARROW=0/457(0) ALL=0/219(0) UNSUPPORTED=31/322(0)
  certifiedDET=0/269(0) NARROW=0/457(0) ALL=0/219(0) UNSUPPORTED=31/322(0)
```
postgres: statements in file and keep set 1267 of 1267; row() = {"sup": 930, "sup_cens": 9, "cer": 0, "slx": 0, "raw": 276, "uns": 302, "uns_cens": 26, "uns_raw": 58, "uns_slx": 24}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/267(2) NARROW=201/451(2) ALL=75/212(5) UNSUPPORTED=58/302(26)
  smartlex DET=0/267(2) NARROW=0/451(2) ALL=0/212(5) UNSUPPORTED=24/302(26)
  certifiedDET=0/267(2) NARROW=0/451(2) ALL=0/212(5) UNSUPPORTED=23/302(26)
```



## 8. Notes and anomalies

- **PostgreSQL censoring** has the same causes as before: DuckDB-specific SQL errors on PostgreSQL and
  transpilation.
- **PostgreSQL vs DuckDB verdicts** (source: `duckdb_verdict` vs `verdict` in the sound_pg files). The two dialects
  differ only where the dialects differ:

  | Set | Statements that differ |
  |---|---|
  | dev | 2 (1 ALL → NARROW key tie-break; 1 ALL → UNSUPPORTED text-to-temporal-cast) |
  | held-out | 7 (2 DET and 2 NARROW, 1 ALL → UNSUPPORTED text-to-temporal-cast; 2 DET → UNSUPPORTED `function:date_part`, a v7 rule) |
  | first task-disjoint | 9 (7 DET → UNSUPPORTED `function:date_part`; 2 UNSUPPORTED → DET, the two DECIMAL-division averages, which are exact in PostgreSQL) |
  | second task-disjoint | 6 (4 NARROW, 2 ALL → UNSUPPORTED text-to-temporal-cast) |

  Together with censoring, this is why the PostgreSQL supported counts differ from the DuckDB ones.
- **My own bug.** The first two pg_check jobs (61888111/3) failed on an import-order bug in pg_check.py (psycopg is
  on sys.path only after pg_setup is imported). It was fixed; reruns 61888138/9 passed. Those jobs only started and
  stopped the servers.
- **Files that are not mine.** `adversarial_v7.json`, `v7_diff.json`, `v7_diff2.json` and `v7_diff3.json` in this
  directory are the lead's outputs, copied along with the v7 directory.
