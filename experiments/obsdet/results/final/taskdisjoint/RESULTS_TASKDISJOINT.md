# Task-disjoint replication of E4 (agent level) and E1-H (held-out statements)

Date: 2026-09-25 (PDT). Every job ran between 10:34 and 11:01 PDT. Job log: `experiments/obsdet/JOBS_TASKDISJOINT.md`.
Code: frozen files (md5 checked against `results/final/code/MD5SUMS.txt` before use) plus new scripts in `code/`
(`code/MD5SUMS.txt`). No frozen file was modified. Files named below are in this directory unless a path is given.

## Headline

- **Agent level.** On 150 new tasks the E4 v5 pattern holds for raw, smart-lex and hybrid. Raw previews change
  trajectories in 52 tasks (Qwen3-8B) and 37 tasks (phi-4) across physical orders. Hybrid changes 4 and 3. Every
  hybrid change comes from UNSUPPORTED statements or runtime errors, and no divergence is unattributed.
  **Strict (fail-closed) is not clean here.** In 3 tasks (Qwen3-8B 2, phi-4 1), a statement the certifier admitted
  (DET or ALL) showed different previews across physical orders. Two of these changed the trajectory and one
  changed the final result. None changed correctness.
- **Held-out statements.** We kept 1,321 new statements.
  - DuckDB: **3 of 1,003 certified previews diverged** (DET 2/315, NARROW 0/471, ALL 1/217). That is 0.30%, with an
    exact one-sided 95% upper bound of 0.77%. Nothing was censored.
  - PostgreSQL: **0 of 985 diverged**, with 18 censored.
  - The 3 DuckDB divergences are the same 3 statements the agent runs exposed.
- **Root causes.** Two defects in the frozen certifier (`certify.py` 7aa9c889bb18), neither patched:
  1. DuckDB's `/` returns DOUBLE for DECIMAL operands, but `certify.py` infers DECIMAL, so SUM/AVG over a quotient of
     DECIMALs is certified.
  2. `SELECT DISTINCT` with ORDER BY on a column that is not output is certified. DuckDB evaluates that sort key as
     `first(col)` per distinct row, which depends on physical order.

  All three statements were written right after a strict refusal. Two follow the float-aggregate hint ("cast the
  argument to DECIMAL"); one follows the nested-LIMIT refusal.

## 1. Task selection (fixed before any agent run)

- `tasks_v3.json` has md5 **bd7f698fda5431cec882e22e7f94114c** and 150 BIRD dev tasks (release 2025-11-06, md5
  d0553ba7a2bc). No question_id is shared with `tasks_v2` (md5 3b638491274b).
- The selection note is `tasks_v3_selection.json`: seed, procedure text, per-database statistics, task ids and the
  check of the physical-order copies. Script: `code/prep_tasks3.py` (md5 md5-withheld, seed 2). Jobs 61885528 and
  61885622.
- **Procedure.** The eligibility rule is the same as prep_tasks.py and prep_tasks2.py: the gold SQL, transpiled to
  DuckDB with sqlglot, returns 1..200 rows on SF1 within 30 s. Per database, in sorted order, with one
  `random.Random(2)`:
  - exclude the tasks_v2 question_ids;
  - also exclude questions whose text or gold SQL equals a tasks_v2 one after lower-casing and collapsing whitespace
    (1 in formula_1, 1 in toxicology);
  - sort the rest by question_id, shuffle, and take the first eligible tasks up to the tasks_v2 count.
- **Shortfall rule.** It was added after job 61885528 and before any agent run. european_football_2 has only 9
  eligible tasks outside tasks_v2: its DuckDB conversion has only Country, League and Match, and 110 of 119
  candidates fail. The missing task therefore comes from the database with the largest tasks_v2 count, continuing
  that database's seeded order. That task is codebase_community:601.
  - The 149-task first pass is kept as `tasks_v3_149_superseded.json` (md5 3c0da7a0570d). No run used it; its tasks
    are a subset of tasks_v3.
- **Per-database counts** (tasks_v2 → tasks_v3):

  | Database | tasks_v2 | tasks_v3 |
  |---|---|---|
  | california_schools | 10 | 10 |
  | card_games | 18 | 18 |
  | codebase_community | 20 | **21** |
  | debit_card_specializing | 9 | 9 |
  | european_football_2 | 10 | **9** |
  | financial | 10 | 10 |
  | formula_1 | 18 | 18 |
  | student_club | 16 | 16 |
  | superhero | 16 | 16 |
  | thrombosis_prediction | 7 | 7 |
  | toxicology | 16 | 16 |

- **Difficulty** was not stratified in either list:

  | Difficulty | tasks_v3 | tasks_v2 |
  |---|---|---|
  | simple | 83 | 87 |
  | moderate | 41 | 48 |
  | challenging | 26 | 15 |

- **Physical-order copies.** All 22 seed-42 and seed-7 copies that agent_det3.py opens exist. Each has the same
  tables, row counts and row multisets (EXCEPT ALL) as its original. The first 20 rows in rowid order differ in every
  table with at least 2 rows (logs `logs/obsdet-prep3-*.out`).

## 2. Runs

| Job | What | Status |
|---|---|---|
| 61885650 / 61885651 | `run_agent3td.sbatch <model> v6td_{qwen3_8b,phi4} tasks_v3.json`: E4 v5 command lines with the task file as argument; 15 conditions; greedy; ≤ 8 turns; 768 tokens; 16,384 context; HF offline; 1x <GPU> | COMPLETED 7:53 / 12:14 |
| 61885652 | `run_td_heldout.sbatch`: heldout_probes.py → td_filter.py → distribution.py | COMPLETED 0:26 |
| 61885653 | `run_cpu.sbatch replay_sound.py cert_td_new.jsonl sound_td.jsonl`: 7 DuckDB configurations | COMPLETED 2:18 |
| 61885654 | `run_e1pg_td.sbatch`: new server e1pgtd, 11 databases × {sf1, perm42}, PostgreSQL-dialect certificates, 5 configurations | COMPLETED 9:10; server stopped; data dir deleted afterwards |
| 61886477 | `td_diag.py`: diagnosis of the 3 divergent certified statements | COMPLETED 0:08 |

Run outputs: `e4_v6td_qwen3_8b/`, `e4_v6td_phi4/` (trace, attempts, turn_stats, summary_e4.json). Logs are in `logs/`.

## 3. Agent level (E4 v5 design, tasks_v3)

Source: `e4_v6td_*/summary_e4.json` from frozen analyze3.py (2210aba77af9), tabulated by `code/td_analyze.py` in
`td_analyze_output.txt` and `td_summary.json`. Counts are tasks out of 150. "cens." marks comparisons censored
because a final result had more than 1,000 rows.

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 52 / 50 / 32 / 13 | 37 / 29 / 17 (cens. 1) / 7 |
| smart-lex, 3 physical orders | 4 / 3 / 3 / 1 | 2 / 2 / 1 (cens. 1) / 0 |
| hybrid (certified), 3 physical orders | 4 / 4 / 4 / 1 | 3 / 3 / 2 (cens. 1) / 0 |
| strict (fail-closed), 3 physical orders | 4 / 4 / 3 / 1 | 2 / 2 / 0 (cens. 1) / 0 |
| raw, 1 vs 8 threads | 28 / 26 / 16 / 9 | 14 / 9 / 6 (cens. 1) / 5 |
| hybrid, 1 vs 8 threads | 2 / 2 / 2 / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| strict, 1 vs 8 threads | 1 / 0 / 0 / 0 | 0 / 0 / 0 (cens. 1) / 0 |

For comparison, the original tasks (E4 v5, same extraction) gave:
- raw, 3 physical orders: 61/58/38/16 (Qwen3-8B) and 30/27/19/3 (phi-4);
- hybrid: 6/6/5/1 and 2/2/1/0;
- strict: 2/2/1/0 and 0/0/0/0.

### Attribution

Unattributed divergence is 0/150 in every group for both models. Sources of same-SQL observation changes, as
analyze3 records them (tasks per statement kind):

| Group | Qwen3-8B | phi-4 |
|---|---|---|
| raw, 3 physical orders | raw 69, runtime-error 3 | raw 59 |
| smart-lex, 3 physical orders | smartlex 5, runtime-error 4 | smartlex 3, runtime-error 1 |
| hybrid, 3 physical orders | UNSUPPORTED 5, runtime-error 4 | UNSUPPORTED 4, runtime-error 1 |
| **strict, 3 physical orders** | runtime-error 4, **DET 1, ALL 1** | **DET 1**, runtime-error 1 |
| raw, 1 vs 8 threads | raw 38, runtime-error 1 | raw 21 |
| hybrid, 1 vs 8 threads | runtime-error 2 | none |
| strict, 1 vs 8 threads | runtime-error 1 | none |

- **Hybrid:** no change originated in a certified statement; the claim of E4 v5 holds on the new tasks.
- **Strict, per task** (first differing observation, from analyze3.task_flags):
  - Qwen3-8B, 3 physical orders:
    - card_games:522, formula_1:1006 and formula_1:976 come from runtime errors; card_games:522 is the one
      correctness change;
    - **financial:100 (DET)** changed the trajectory; correctness stayed wrong in all three runs;
    - **formula_1:930 (ALL, final answer)** changed the final result (Austrian / Canadian / Australian Grand Prix);
      correctness stayed wrong in all three runs.
  - phi-4: **california_schools:0 (DET)** changed the trajectory (correctness wrong in all runs); formula_1:955 comes
    from a runtime error.
- Zero counts carry an exact one-sided 95% upper bound of 1.98% (0/150).

### Accuracy

BIRD execution accuracy (set comparison), with the duplicate-sensitive bag version in parentheses:

| Policy | Qwen3-8B | phi-4 |
|---|---|---|
| raw (orig_t1 / orig_t8 / p42 / p7) | 0.640 / 0.620 / 0.620 / 0.627 (0.613 / 0.600 / 0.587 / 0.607) | 0.493 / 0.473 / 0.473 / 0.473 (0.453 / 0.433 / 0.427 / 0.433) |
| smart-lex (orig / p42 / p7) | 0.620 / 0.613 / 0.613 (0.580 each) | 0.493 each (0.447) |
| hybrid (orig_t1 / orig_t8 / p42 / p7) | 0.633 / 0.633 / 0.627 / 0.627 (0.600 / 0.600 / 0.593 / 0.593) | 0.493 each (0.447) |
| strict (orig_t1 / orig_t8 / p42 / p7) | 0.633 / 0.633 / 0.627 / 0.627 (0.600 / 0.600 / 0.593 / 0.593) | 0.420 each (0.373) |

Per-condition 95% bootstrap CIs are in `td_analyze_output.txt`.

### Paired accuracy differences

Over the three physical orders, with task-clustered bootstrap 95% CIs (2,000 resamples, seed 0):

| Difference | Qwen3-8B | phi-4 |
|---|---|---|
| hybrid − raw | +0.0 pp [−3.1, +3.1] | +1.3 pp [−1.3, +4.2] |
| smart-lex − raw | −1.3 pp [−4.7, +2.2] | +1.3 pp [−1.3, +4.2] |
| hybrid − smart-lex | +1.3 pp [0.0, +3.3] | 0.0 pp [0.0, 0.0] |
| strict − raw | +0.0 pp [−4.0, +4.0] | **−6.0 pp [−10.9, −1.1]** |
| strict − hybrid | +0.0 pp [−2.7, +2.7] | **−7.3 pp [−12.0, −3.3]** |

On the original tasks (E4 v5), phi-4 strict − raw was −3.6 and strict − hybrid was −4.7.

### Strict burden

- **Refused statements** over the four strict conditions: Qwen3-8B 435, phi-4 412. E4 v5 had 617 and 688.
- **Statements executed under hybrid**, by verdict:

  | Model | DET | NARROW | ALL | UNSUPPORTED (smart-lex fallback) |
  |---|---|---|---|---|
  | Qwen3-8B | 520 | 793 | 433 | 512 |
  | phi-4 | 420 | 540 | 308 | 308 |

- **Frozen `strict_burden.py`** (8af7323c6e34), run on the run directories; output in `strict_burden_td_output.txt`:

  | Model | Tasks with ≥ 1 withheld preview | Median / max withheld | Hybrid-correct → strict-wrong | Hybrid-wrong → strict-correct |
  |---|---|---|---|---|
  | Qwen3-8B | 59/150 | 1 / 6 | 2 | 2 |
  | phi-4 | 42/150 | 1 / 8 | **11** | 0 |

  On the original tasks (E4 v5): Qwen3-8B 71/150 (hybrid-correct → strict-wrong 1, hybrid-wrong → strict-correct 3);
  phi-4 56/150 (7 and 0).

## 4. Held-out statements (task-disjoint)

Built by job 61885652 (`logs/obsdet-tdh-61885652.out`):
- frozen heldout_probes.py (5bf19bb17ed3) on both v6td runs gives `cert_td_all.jsonl`;
- `code/td_filter.py` gives `cert_td_new.jsonl` and `td_funnel.json`;
- frozen distribution.py (7fedeb45118a) gives `distribution_td.json`.

td_filter reproduces the E1-H funnel exactly on the first held-out set: 121 / 13 / 134 → 1,125.

### Funnel

| Stage | Count |
|---|---|
| Distinct (db, statement) issued by the v6td agents (2 models, 15 conditions) | 1,495 |
| − equal to a development probe (exact) | 1 |
| − equal to a development probe after `heldout_dedup.norm` | 0 |
| − equal to a first-held-out statement (exact) | 8 |
| − equal to a first-held-out statement after `heldout_dedup.norm` | 5 |
| − fails on SF1 | 160 |
| **Kept task-disjoint held-out statements** | **1,321** |

- The 1,321 statements account for 13,702 occurrences, cover all 11 databases, and include 34 issued by both models.
- They form 1,283 distinct statements after `norm`.
- Rewrites failed: 0.

### Verdicts and widths (DuckDB dialect, frozen certifier)

- **Verdict distribution:**

  | Verdict | Distinct (1,321) | Occurrence-weighted |
  |---|---|---|
  | DET | 315 (23.8%) | 25.9% |
  | NARROW | 471 (35.7%) | 36.3% |
  | ALL | 217 (16.4%) | 19.6% |
  | UNSUPPORTED | 318 (24.1%) | 18.2% |

  E1-H had DET 16.8%, NARROW 34.1%, ALL 18.1%, UNSUPPORTED 30.9%.
- **Per model** (distinct statements executed under hybrid):

  | Model | DET | NARROW | ALL | UNSUPPORTED | n |
  |---|---|---|---|---|---|
  | Qwen3-8B | 22.0% | 35.6% | 18.6% | 23.8% | 500 |
  | phi-4 | 25.3% | 34.9% | 20.3% | 19.5% | 344 |

- **Width.** The 688 repaired statements (NARROW/ALL) append **1.12** sort columns on average, versus **2.49** for
  smart-lex. E1-H had 1.11 vs 2.31. Of those repairs, 614 need one column, 68 need two and 6 need three.
  - 430 are key tie-breaks, 262 of them on a key column the query does not output.
- **UNSUPPORTED reasons** (318, `distribution_td.json`):

  | Reason | Count |
  |---|---|
  | derived-table | 123 |
  | no-base-table (statement without FROM) | 85 |
  | cte | 43 |
  | float-aggregate | 35 |
  | nested-limit | 9 |
  | outer-or-special-join | 8 |
  | unresolved | 6 |
  | not-select | 5 |
  | multi-statement | 2 |
  | function | 2 |

- **By class:**

  | Class | Total | DET | NARROW | ALL | UNSUPPORTED |
  |---|---|---|---|---|---|
  | unordered SELECT | 918 | 284 | 297 | 84 | 253 |
  | DISTINCT | 151 | 3 | 35 | 99 | 14 |
  | ORDER BY + LIMIT | 89 | 8 | 60 | 9 | 12 |
  | GROUP BY | 73 | 8 | 32 | 6 | 27 |
  | LIMIT without ORDER BY | 64 | 1 | 39 | 19 | 5 |
  | ORDER BY without LIMIT | 26 | 11 | 8 | 0 | 7 |

- **Ablation without declared keys:** DET 246, NARROW 220, ALL 537, UNSUPPORTED 318; mean width 2.04.

### Soundness

Computed exactly as `figures/gen_table_soundness.py` `row()` does: the function is imported unchanged (md5
a9a0dbd3f929) by `code/td_analyze.py`, with keep = all kept statements. Per-verdict tables come from
`heldout_dedup.table`.

| Engine | Supported n (cens.) | Certified diverged | Smart-lex diverged | Raw diverged | UNSUPPORTED n (cens.) | Raw diverged | Smart-lex diverged |
|---|---|---|---|---|---|---|---|
| DuckDB, 7 configurations (`sound_td.jsonl`, job 61885653) | 1,003 (0) | **3** | 3 | 398 | 318 (0) | 89 | 41 |
| PostgreSQL, 5 configurations, PostgreSQL-dialect certificates (`sound_pg_td.jsonl`, job 61885654) | 985 (18) | **0** | 0 | 301 | 288 (30) | 62 | 32 |

- **DuckDB per verdict**, diverged / complete:

  | Policy | DET | NARROW | ALL | UNSUPPORTED |
  |---|---|---|---|---|
  | raw | 2/315 | 259/471 | 137/217 | 89/318 |
  | smart-lex | 2/315 | 0/471 | 1/217 | 41/318 |
  | certified | **2/315** | 0/471 | **1/217** | 41/318 (smart-lex fallback) |

  The 3/1,003 rate is 0.30%, with an exact one-sided 95% upper bound of 0.77% (two-sided CI [0.06, 0.87]%).
- **PostgreSQL per verdict**, diverged / complete (censored):

  | Policy | DET | NARROW | ALL | UNSUPPORTED |
  |---|---|---|---|---|
  | raw | 0/311 (4) | 221/462 (9) | 80/213 (4) | 62/288 (30) |
  | smart-lex | 0/311 (4) | 0/461 (10) | 0/213 (4) | 32/288 (30) |
  | certified | 0/311 (4) | 0/461 (10) | 0/213 (4) | 32/288 (30) |

  The PostgreSQL-dialect verdicts equal the DuckDB verdicts for all 1,321 statements; there were no transpile
  errors. The 0/985 rate has an exact one-sided 95% upper bound of 0.30%. Parallel plans were chosen for 1,124–1,142
  of the 1,287 queries per policy that EXPLAIN could plan.
- **PostgreSQL censoring** (48 statements) is caused by DuckDB-specific SQL failing on PostgreSQL. Examples:
  - integer casts of "53.7";
  - `round(double precision, integer)`;
  - division by zero (NULL in DuckDB);
  - `SPLIT(...)[0]`;
  - `sqlite_master`, DESCRIBE and PRAGMA;
  - `double % integer`;
  - "for SELECT DISTINCT, ORDER BY expressions must appear in select list" (3 statements: the formula_1 one below,
    a financial ALL statement ordering by COUNT(...) under DISTINCT, and an UNSUPPORTED nested-limit statement).

## 5. Certified divergences and their causes (frozen code, not patched)

Diagnosis job 61886477 (`logs/obsdet-tddiag-61886477.out`, DuckDB 1.5.5). Each statement's observation under the 7
replay configurations is reproduced there.

1. **financial (Qwen3-8B, str_orig_t1, financial:100, turn 7).** Certificate: DET "single-row aggregate".

   ```sql
   SELECT AVG(CAST(DATE_DIFF('day', c.birth_date, a.date) AS DECIMAL(18, 6)) / 365.25) AS average_age_at_opening
   FROM client c JOIN disp d ON c.client_id = d.client_id JOIN account a ON d.account_id = a.account_id
   JOIN district d2 ON c.district_id = d2.district_id
   WHERE c.gender = 'F' AND c.birth_date < '1950-01-01' AND d2.A2 = 'Sokolov';
   ```

   Preview: 59.63928815879535 on the original order (1 and 8 threads); 59.639288158795345 on seed 42 and seed 7.
2. **california_schools (phi-4, str_orig_t1, california_schools:0, turn 5).** Certificate: DET "single-row aggregate".

   ```sql
   SELECT AVG(CAST("Free Meal Count (K-12)" AS DECIMAL(18, 6)) / CAST("Enrollment (K-12)" AS DECIMAL(18, 6)))
     AS AvgFreeMealRate FROM frpm WHERE "County Name" = 'Alameda';
   ```

   Preview: 0.45325042040747315 (original), 0.45325042040747265 (seed 42), 0.4532504204074726 (seed 7).
   - **Cause of 1 and 2.** In DuckDB, `DECIMAL / DECIMAL` and `DECIMAL / 365.25` have type DOUBLE; the plan shows
     `CAST(... AS DOUBLE) / ...`. So AVG accumulates doubles, and the result depends on summation order.
     `certify.py` `infer()` for `exp.Div` in the DuckDB dialect returns `"DECIMAL" if a == b == "DECIMAL"`, so the
     float-aggregate check passes. On PostgreSQL, numeric division is exact and both statements are stable.
   - The pattern occurs 0 times among the supported development probes and the first held-out statements (regex
     scan), which is why E1 and E1-H could not expose it.
3. **formula_1 (Qwen3-8B, str_orig_t1, formula_1:930, turn 5, final answer).** Certificate: ALL "output tie-break",
   rewritten to `... ORDER BY results.rank, 1 ASC LIMIT 1`.

   ```sql
   SELECT DISTINCT races.name FROM races JOIN results ON races.raceId = results.raceId
   WHERE results.driverId = 1 ORDER BY results.rank LIMIT 1;
   ```

   Preview: Austrian Grand Prix (original), Canadian Grand Prix (seed 42), Australian Grand Prix (seed 7).
   - **Cause.** DuckDB accepts ORDER BY on a column that is not output under DISTINCT. It plans the statement as
     `HASH_GROUP_BY name` with aggregate `first(rank)`, then TOP_N on (first(rank), name). The sort key is an
     order-dependent representative. The certifier treats `results.rank` as a row attribute (order_cols) and completes
     the order with the output column. PostgreSQL rejects the statement, so it is censored there.
   - The same shape (ORDER BY an expression that is not output, under DISTINCT) also occurs in supported statements
     that did not diverge. A regex scan finds one development probe (formula_1, `ORDER BY l.milliseconds`) and one
     task-disjoint statement (financial, `SELECT DISTINCT d.A3 ... GROUP BY d.district_id, d.A3 ORDER BY
     COUNT(l.loan_id) DESC LIMIT 1`). Presumably the data make their sort key a function of the output there. The
     defect class is therefore older than this set; this set is the first where it shows.
4. **Why the strict policy exposes these.** Each divergent statement was the agent's next statement after a strict
   refusal:
   - financial:100: turn 6 was refused as float-aggregate (hint: "cast the argument to DECIMAL, e.g.
     AVG(CAST(x AS DECIMAL(18, 6)))").
   - california_schools:0: turn 4 was refused as float-aggregate.
   - formula_1:930: the final answer was refused as nested-limit.

   The refusal hint steers agents into the two blind spots. Under hybrid the same tasks took other paths; in
   formula_1:930 the hybrid final answer was the UNSUPPORTED nested-LIMIT query itself.

## 6. Other anomalies and notes

- **Runtime errors.** Their messages quote the first offending value, so they vary with physical order. They are a
  larger source here than in E4 v5. Examples: card_games:522 and formula_1:976/1006/955 in smart-lex, hybrid and
  strict. These are outside the contract (failed executions) and are attributed as "runtime-error" by analyze3.
- **Dry-run check.** In the dry run of `run_agent3td.sbatch` (3 california_schools tasks, gold SQL as answers),
  12 strict conversations stayed active until turn 8, because gold statements the certifier rejects are refused.
  This is expected behavior of the check and does not affect the real runs.
- **Accuracy level.** Accuracy is higher on tasks_v3 than on tasks_v2 for Qwen3-8B (0.61–0.64 vs 0.51–0.55), despite
  more challenging tasks (26 vs 15). For phi-4 it is 0.42–0.49 vs 0.41–0.45.
- **PostgreSQL server.** A new private server e1pgtd was built exactly as run_e1pg_heldout.sbatch builds e1pgh and
  stopped on exit. Its data directory (8,465 files) was deleted after the results were copied.
- **Not done.** Codex review was not requested, and nothing in the paper was edited.
