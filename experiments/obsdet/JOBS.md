# obsdet (certified observational determinism) — job log

Cluster project dir: `$PROJECT_ROOT` (`$V`). Code copied to `$V/code/obsdet/`;
outputs in `$V/runs/obsdet/`; logs in `$V/runs/obsdet/logs/<job-name>-<id>.out`. Environment `$V/env.sh`.
CPU jobs: account `<CPU_ACCOUNT>`, partition `<CPU_PARTITION>`. GPU jobs: account `<GPU_ACCOUNT>`, partition `<GPU_PARTITION>`
(1x <GPU>, 8 CPUs per GPU). E3 cost jobs are logged separately in `JOBS_E3.md`.

| Job ID | Purpose | Est. | Walltime | Resources | Script + params (code version) | Result |
|---|---|---|---|---|---|---|
| 61872170 | Certify the 1,015 R2-1 probes (v1) | 2 min | 2 h | 8 CPU, 32 GB | `run_cpu.sbatch cert_probes.py ... cert_probes_v1.jsonl` | COMPLETED 0:43; 129 unknown-table (catalog case bug) |
| 61872201 | Certify probes (v2, lower-cased DuckDB catalog) | 2 min | 2 h | 8 CPU, 32 GB | `run_cpu.sbatch cert_probes.py ... cert_probes_v2.jsonl` | COMPLETED 0:37; DET 123 / NARROW 601 / ALL 133 / UNSUPPORTED 158; 0 rewrite failures |
| 61872224 | E1 replay v2: 3 policies x 7 equivalent configurations | 30 min | 3 h | 8 CPU, 48 GB | `run_sound.sbatch` (builds seed-7 copies, `replay_sound.py` on v2) | COMPLETED 6:17; certified 0/857 diverged on DET/NARROW/ALL; raw 283/601 NARROW, 101/133 ALL; UNSUPPORTED with smart-lex fallback 39/158 |
| 61872248 | E1 adversarial suite v1 (30 cases x 30 instances x 6 orders) | 5 min | 2 h | 8 CPU, 32 GB | `run_cpu.sbatch adversarial.py adversarial_v1.json 30 6` | COMPLETED 3:31; 29/30 verdicts correct (`WHERE id = 3` gave NARROW: WHERE conjuncts ignored), 0 certified divergences |
| 61872271 | Seed-42/7 copies of 5 new DBs + E4 task list | 5 min | 2 h | 8 CPU, 32 GB | `run_prep.sbatch` (`prep_tasks2.py`, seed 1) | COMPLETED 0:17; 150 tasks (66 pilot + 84 new) |
| 61872416 | E1 v3 on the fixed certifier (WHERE conjuncts + exact-type guard): re-certify, adversarial (32 cases), replay | 15 min | 2 h | 8 CPU, 48 GB | `run_e1v3.sbatch` (certify.py md5 c845c6c9afad) | COMPLETED; DET 166 / NARROW 570 / ALL 121 / UNSUPPORTED 158; adversarial 32/32; certified 0/857 divergent (superseded by v4 after code review) |
| 61872449 | E4 v1 Qwen3-8B, 150 tasks x 11 conditions (pre-review certifier, capped counts) | 30–60 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch Qwen/Qwen3-8B qwen3_8b` (agent_det3 md5 b480133145f5) | COMPLETED ~7 min; pipeline check only, superseded by v2 |
| 61872450 | E4 v1 microsoft/phi-4, same design | 30–60 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch microsoft/phi-4 phi4` | COMPLETED ~9 min; pipeline check only, superseded by v2 |
| 61873586 | E1/E2 v4 after code-review round 1 (expression closure, grouped DISTINCT, FETCH/percent/collation/function allowlist, width-based choice, HAVING; replay censoring and exact counts; adversarial 42 cases with error and power checks) | 20 min | 2 h | 8 CPU, 48 GB | `run_e1v4.sbatch` (certify md5 ee978208b9d2, tool 48c141474b11) | COMPLETED 11:08; DET 166 / NARROW 522 / ALL 169 / UNSUPPORTED 158; adversarial 42/42; replay: certified 0/857 divergent, 0 censored; raw 269/522 NARROW, 112/169 ALL; UNSUPPORTED: raw 68, fallback 39 of 158 |
| 61873660 | E4 v2 Qwen3-8B on the v4 certifier; exact row counts; final status recorded | 10 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch Qwen/Qwen3-8B v2_qwen3_8b` (agent_det3 5aca498191ef, analyze3 a6fb18ec3b0c) | COMPLETED 7:56; raw_phys traj 60/150, correctness 16; cer_phys traj 5 (sources: UNSUPPORTED 7 tasks, runtime-error 2); superseded by v3 after code-review round 2 |
| 61873661 | E4 v2 microsoft/phi-4, same | 10 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch microsoft/phi-4 v2_phi4` | COMPLETED 11:06; raw_phys traj 34/150, correctness 3; cer_phys traj 2 (UNSUPPORTED only); superseded by v3 |
| 61874111 | E1/E2 v5 after code-review round 2 (ORDER BY ALL, GROUP BY ALL, PG relative time, Pareto width choice, nested canonical rendering, count-failure flag); adversarial 45 DuckDB + 5 PostgreSQL verdict cases, fails the job on any failed case or missing power | 25 min | 2 h | 8 CPU, 48 GB | `run_e1v5.sbatch` (certify md5 991a260cb2eb, tool md5-withheld, adversarial 2c3fb7f6ce8d) | COMPLETED 12:03; verdicts as v4; replay certified 0/857; adversarial 45/45 + 5/5 PG, power 4/4; superseded by v6 after code-review round 3 (float closure seeds, recursive fragment checks) |
| 61874112 | E4 v3 Qwen3-8B on the round-2 certifier | 10 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch Qwen/Qwen3-8B v3_qwen3_8b` (agent_det3 5aca498191ef, analyze3 bd626a80d8be) | COMPLETED 7:54; raw_phys traj 59/150, correctness 17; cer_phys 7 (UNSUPPORTED / runtime-error only); superseded by v4 |
| 61874113 | E4 v3 microsoft/phi-4 on the round-2 certifier | 12 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch microsoft/phi-4 v3_phi4` | COMPLETED 10:01; raw_phys traj 33/150, correctness 6; cer_phys 2 (UNSUPPORTED only); superseded by v4 |
| 61874148 | E1 on PostgreSQL 16 (private server e1pg; original vs seed-42 heap order x parallel workers 0/4 + repeat = 5 configurations; v5 certificates transpiled with pg_cost.to_pg) | 1 h | 4 h | 8 CPU, 40 GB | `run_e1pg.sbatch` (`replay_pg.py`) | CANCELLED at 27:48 by me: code review round 3 found it replayed DuckDB certificates instead of certifying in the PostgreSQL dialect |
| 61875301 | E1/E2 v6 after code-review round 3 (exact-typed closure seeds, representatives only in equality-safe uses, recursive fragment checks, clause allowlist, key cover by bytes); adversarial 53 DuckDB + 6 PostgreSQL cases | 25 min | 2 h | 8 CPU, 48 GB | `run_e1v6.sbatch` (certify md5 c0f9e50f3cd3, adversarial f93b9fd48a0d) | COMPLETED 16:08; DET 166 / NARROW 512 / ALL 177 / UNSUPPORTED 160; replay certified 0/855, raw 266/512 NARROW, 114/177 ALL, UNSUPPORTED raw 69 / fallback 39 of 160; adversarial 53/53 + 6/6 PG, power 4/4 (FINAL DuckDB E1/E2) |
| 61875302 | E1 on PostgreSQL, probes recertified in the PostgreSQL dialect; parallel plans recorded (starts after 61875301 starts) | 1 h | 4 h | 8 CPU, 40 GB | `run_e1pg.sbatch` (replay_pg md5 md5-withheld) | COMPLETED 28:37; PG verdicts DET 166 / NARROW 513 / ALL 175 / UNSUPPORTED 161; certified 0/836 divergent (18 censored); raw 227/509 NARROW, 57/172 ALL; parallel plans for ~93% of queries |
| 61875303 | E4 v4 Qwen3-8B on the round-3 certifier | 10 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch Qwen/Qwen3-8B v4_qwen3_8b` | COMPLETED 9:11; raw_phys traj 57/150, correctness 15; cer_phys 7 (UNSUPPORTED 8 / runtime-error 2 source tasks); paired cer-raw +0.9pp [-2.2, +3.8] (FINAL) |
| 61875304 | E4 v4 microsoft/phi-4 on the round-3 certifier | 12 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch microsoft/phi-4 v4_phi4` | COMPLETED 11:48; raw_phys traj 31/150, correctness 3; cer_phys 2 (UNSUPPORTED only); paired cer-raw +0.9pp [-0.2, +2.7] (FINAL) |
| 61875881 | Adversarial suite after code-review round 4 (PostgreSQL IN-probe relative time; MAX cases restricted to the signed zeros; ev table): 53 DuckDB + 8 PostgreSQL cases | 5 min | 2 h | 8 CPU, 32 GB | `run_cpu.sbatch adversarial.py adversarial_v6.json 30 6` (certify 7aa9c889bb18, adversarial 387d02df42bf) | COMPLETED 6:49; 53/53 DuckDB, 8/8 PostgreSQL, power 4/4 (FINAL suite) |
| 61877857 | Held-out build (review round 1): distinct statements of the E4 v4 agents (2 models, 11 DBs), frozen certifier, not-in-dev filter, distribution with per-model verdicts | 15 min | 3 h | 8 CPU, 48 GB | `run_heldout.sbatch` (`heldout_probes.py`) | SUBMITTED |
| 61877858 | Held-out DuckDB replay, 7 configurations (after 61877857) | 40 min | 2 h | 8 CPU, 32 GB | `run_cpu.sbatch replay_sound.py cert_heldout_new.jsonl sound_heldout.jsonl` | SUBMITTED |
| 61877859 | Held-out PostgreSQL replay, 11 DBs, PG-dialect certificates (after 61877857) | 1 h | 4 h | 8 CPU, 40 GB | `run_e1pg_heldout.sbatch` (server e1pgh) | SUBMITTED |
| 61877866 | E4 v5 Qwen3-8B, 15 conditions incl. strict fail-closed (str_orig/p42/p7_t1, str_orig_t8) | 15 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch Qwen/Qwen3-8B v5_qwen3_8b` (agent_det3 md5 md5-withheld, analyze3 2210aba77af9, certify 7aa9c889bb18) | SUBMITTED |
| 61877867 | E4 v5 microsoft/phi-4, same 15 conditions | 15 min | 3 h | 1x <GPU>, 8 CPU, 64 GB | `run_agent3.sbatch microsoft/phi-4 v5_phi4` | SUBMITTED |
| 61877876 | Version check: current certify.py vs stored v6 DuckDB certificates and PG-dialect certificates | 5 min | 2 h | 8 CPU, 32 GB | `run_cpu.sbatch version_check.py ...` | SUBMITTED |

## Certifier v7 (after the task-disjoint replication found two soundness defects; 2026-09-25)

Defects in v6 (`certify.py` md5 7aa9c889…), found by the task-disjoint replication (`JOBS_TASKDISJOINT.md`,
`results/final/taskdisjoint/RESULTS_TASKDISJOINT.md`): (1) the DuckDB dialect typed DECIMAL/DECIMAL division as
DECIMAL, but DuckDB 1.5.5 returns DOUBLE (verified: `typeof(1.5::DECIMAL(18,6)/3::DECIMAL(18,6))` = DOUBLE), so
SUM/AVG over such a division passed the floating-point-aggregate check; (2) `SELECT DISTINCT ... ORDER BY <non-output>`
was certified, but DuckDB sorts DISTINCT rows by an arbitrary value of a non-output key (PostgreSQL rejects the query).
v7 first draft (`certify.py` md5 adb7e26d…): DuckDB `/` typed FLOAT; under DISTINCT every ORDER BY item must match an
output, else UNSUPPORTED (`distinct-order-by-non-output`). A Codex code review of that draft
found further defects, all confirmed on the cluster: ORDER BY ordinals rebound by qualify() to duplicated output names;
USING/NATURAL joins rewritten to ON by qualify() before the fragment check; NATURAL/ASOF/POSITIONAL joins stored in
sqlglot's `method` field, which v6 never checked (DuckDB POSITIONAL JOIN pairs rows by physical position); DuckDB `//`
on DECIMAL/DOUBLE returns DOUBLE; DuckDB `1e0` is DOUBLE; DuckDB date part `julian` is DOUBLE; PostgreSQL `date_part()`
is double precision but sqlglot parses it as EXTRACT (numeric) and rewrites it; PostgreSQL `sign(double)` is double.
v7 (`certify.py` md5 0353e3ee…) fixes all of them (ORDER BY ordinals and names resolved from the statement as written,
ambiguous names rejected; join checks before and after qualify(); type inference corrected; PostgreSQL date_part
rejected). DuckDB's `scalar_subquery_error_on_multiple_rows` is true by default in 1.5.5 (checked), as the soundness
argument assumes. New adversarial cases: 14 DuckDB, 6 PostgreSQL (`adversarial.py` md5 9be181fd…); under v6 all 14
DuckDB cases and 4 PostgreSQL cases were certified wrongly. Code for v7 runs: `$V/code/obsdet_v7/` (copy of `code/obsdet`
with v7 certify.py/adversarial.py; `agent_det3.py` and the sbatch files point to `obsdet_v7`); `code/obsdet/` stays
frozen at v6 (the property-based test is running against it). Outputs under `$V/runs/obsdet/v7/`.

| Job | Purpose | Est. | Walltime | Resources | Command | Status |
|---|---|---|---|---|---|---|
| 61887149 | v6 vs v7 verdict/rewrite diff on dev, held-out, task-disjoint and all E4 v5/v6td statements (DuckDB and PostgreSQL dialects) | 5 min | 2 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch v7_diff.py runs/obsdet/v7/v7_diff.json` | CANCELLED (v7 revised after code review) |
| 61887150 | Adversarial suite v7 (58 DuckDB cases incl. 5 new, 10 PostgreSQL verdict cases) | 40 min | 3 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch adversarial.py runs/obsdet/v7/adversarial_v7.json` | CANCELLED (v7 revised after code review) |
| 61887844 | v6 vs v7a (md5 0353e3ee) verdict/rewrite diff on dev, held-out, task-disjoint and all E4 v5/v6td statements, DuckDB and PostgreSQL dialects | 5 min | 2 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch v7_diff.py runs/obsdet/v7/v7_diff.json` | COMPLETED (1:27); output superseded by 61888107 |
| 61887845 | Adversarial suite v7 (67 DuckDB cases, 14 PostgreSQL verdict cases) | 40 min | 3 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch adversarial.py runs/obsdet/v7/adversarial_v7.json` | CANCELLED (v7 revised again: splice-based rewrite) |

**v7 final** (`certify.py` md5 1369ffcae12b93aec06735259c146814, 669 lines; the intermediate v7a, md5 0353e3ee…, is kept
as `runs/obsdet/v7/certify_v7a_0353e3ee.py`). The property-based test (`JOBS_PROPTEST.md`) found that rewrites regenerated
by sqlglot change typed-literal casts (e.g. `DATE '2026-01-10'::VARCHAR` became `CAST(CAST('2026-01-10' AS TEXT) AS
DATE)`) and DuckDB's generated column names (`x IS NOT NULL` became `NOT x IS NULL`). v7 final splices the tie-break into
the statement as written (`_splice_order`) and accepts the result only if it parses to exactly the original statement
with the keys appended (else UNSUPPORTED `rewrite-splice`); smart-lex uses the same splice; group-key tie-breaks are
written as plain columns or output positions only.

| Job | Purpose | Est. | Walltime | Resources | Command | Status |
|---|---|---|---|---|---|---|
| 61888107 | v6 vs v7 (1369ffca): verdict and tie-break diff on all statement sets, both dialects | 5 min | 2 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch v7_diff.py runs/obsdet/v7/v7_diff.json` | COMPLETED (1:23) |
| 61888108 | Adversarial suite with v7 1369ffca (67 DuckDB, 14 PostgreSQL cases) | 40 min | 3 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch adversarial.py runs/obsdet/v7/adversarial_v7.json` | SUBMITTED |

**Certifier of record: v7 final** (`code/obsdet_v7final/certify.py`, md5 5a2daa9e4634ec90689062338fa8b23d, 719 lines;
local `experiments/obsdet/certify.py`). After 1369ffca, a second Codex review found that
sqlglot drops a unary `+` in ORDER BY (so `ORDER BY +foo` was bound to an output alias) and that names inside ORDER BY
expressions bind to input columns in DuckDB and PostgreSQL (checked on DuckDB 1.5.5) while qualify() may bind them to
outputs; PostgreSQL quoted upper-case aliases were lower-cased. The property-based test found N8 (a typed literal
followed by `::` is parsed by sqlglot with the casts inverted) and N9 (DuckDB types number literals with more than 38
digits, or beyond HUGEINT, as DOUBLE). v7 final rejects unary `+` in ORDER BY items (`order-by-unary-plus`), output
aliases used inside ORDER BY expressions (`order-by-alias-in-expression`), PostgreSQL quoted names with upper case when
ORDER BY uses names (`pg-quoted-name`), typed literals followed by `::` (`typed-literal-cast`), types long DuckDB
literals FLOAT, and tracks brackets/braces when splicing. It only adds rejections relative to 1369ffca: on dev, all
held-out, td and all E4 v5/v6td statements (both dialects) verdicts and tie-breaks are identical (job 61888620,
`runs/obsdet/v7/v7_diff3.json`), so the v7 reruns keep 1369ffca and are checked the same way afterwards.

| Job | Purpose | Est. | Walltime | Resources | Command | Status |
|---|---|---|---|---|---|---|
| 61888514 | 1369ffca vs candidate diff (first try) | 2 min | 2 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | `run_cpu.sbatch runs/obsdet/v7/v7_diff2.py ...` | FAILED (import path; fixed) |
| 61888564 | 1369ffca vs candidate c0ee9386 diff | 2 min | 2 h | same | `run_cpu.sbatch runs/obsdet/v7/v7_diff2.py ... v7_diff2.json` | COMPLETED (only `; -- comment` statements differed; that change was dropped) |
| 61888620 | 1369ffca vs v7 final (5a2daa9e) diff | 2 min | 2 h | same | `run_cpu.sbatch runs/obsdet/v7/v7_diff2.py ... v7_diff3.json` | COMPLETED (0 differences on all sets) |
| 61888662 | Adversarial suite with v7 final (73 DuckDB, 16 PostgreSQL cases; adversarial.py md5 cbd47c63) | 45 min | 3 h | same | `code/obsdet_v7final: run_cpu.sbatch adversarial.py runs/obsdet/v7/adversarial_v7final.json` | COMPLETED 24:38 (5a2daa9e): 73/73 cases, 0 certified divergences, 0 certified failed executions, power 8/8; 16/16 PostgreSQL verdict checks OK |
| 61889323 | 1369ffca vs 66ead3df diff (`runs/obsdet/v7/certify_candidate2.py`) | 3 min | 2 h | same | `run_cpu.sbatch code/obsdet_v7/v7_diff2_ext.py runs/obsdet/v7/certify_v7_1369ffca.py runs/obsdet/v7/certify_candidate2.py ...` | COMPLETED 2:45; 0 differences on every set (dev 1,015, heldout_all 1,393, td_all 1,495, E4 v5/v6td/v7/v7td/v7td2 traces, cert_td2_all 1,468) |
| 61889364 | Adversarial suite with 66ead3df | 25 min | 3 h | same | `code/obsdet_v7final: run_cpu.sbatch adversarial.py ...` | CANCELLED at 12:56 PDT (certify.py was being replaced by 7626553a; partial output not used) |
| 61889511 | 1369ffca vs 7626553a diff (`runs/obsdet/v7/certify_candidate3.py`) | 3 min | 2 h | same | as 61889323 with certify_candidate3.py | COMPLETED 2:49; 0 differences on every set (same sets as 61889323) |
| 61889789 | Adversarial suite with 7626553a (first submission) | 25 min | 3 h | same | as 61889821 | CANCELLED after 23 s (adversarial.py was being updated to md5 877ae29b) |
| 61889821 | Adversarial suite with the final certifier (75 DuckDB, 18 PostgreSQL cases; certify.py 7626553a, adversarial.py 877ae29b, both in place before the job started at 12:57:15 PDT) | 25 min | 3 h | same | `code/obsdet_v7final: run_cpu.sbatch adversarial.py runs/obsdet/v7/adversarial_v7final.json` | COMPLETED 25:37: 75/75 cases, 0 certified divergences, 0 certified failed executions, power 8/8; 18/18 PostgreSQL verdict checks OK (`logs/obsdet-adv7f-61889821.out`) |

**Certifier of record: final (md5 7626553a38a7b0dcf648b4d665c540bd, 739 lines).** The proof audit
(`paper/PROOF_AUDIT.md`) led to two more stricter-only revisions after 5a2daa9e: 66ead3df (constants and equalities only
without lossy coercion) and 7626553a (temporal equalities only between identical declared types; no text FD or constant
on blank-padded CHAR). Jobs 61889323 and 61889511 show that both return the same verdicts and tie-breaks as 1369ffca
(the certifier of the v7 runs) on every evaluated statement, so the v7 results stand for the final certifier.

### Certification latency (Round-2 paper review, 2026-09-25 14:25 PDT)

| Job | Purpose | Est. | Walltime | Resources | Command | Status |
|---|---|---|---|---|---|---|
| 61895574 | Online cost of certification: per-probe median of 5 timings of certify() (DuckDB and PostgreSQL dialects) and smartlex() over the 1,015 development probes, plus the one-time key validation (catalog.py's check) on the SF1 DuckDB files; `time_certify.py` md5 8ec5462b, certify.py 7626553a | 5 min | 1 h | <CPU_ACCOUNT> <CPU_PARTITION>, 4 CPU, 8 GB | `code/obsdet_v7final: sbatch --cpus-per-task=4 --mem=8G --time=01:00:00 run_cpu.sbatch time_certify.py runs/obsdet/catalog.json runs/obsdet/v7/cert_probes_v7.jsonl runs/obsdet/v7/sound_pg_v7.jsonl data/bird_duckdb/validation runs/obsdet/v7/time_certify.json 5` | COMPLETED 0:45: certify() median 2.611 ms (p99 8.765, max 45.5) DuckDB, 2.624 ms (p99 8.845) PostgreSQL; smartlex() 0.922 ms; key validation 0.881 s total at SF1 (66 keys); `results/v7/time_certify.json`, log `results/v7/logs/obsdet-timecert-61895574.out` |

### Schema-qualified table names (proof re-audit, 2026-09-25 17:26 PDT)

The proof re-audit (`paper/PROOF_AUDIT.md`, run 2) flagged a candidate: `_sources()` kept only the bare table name, so a
statement naming `evil.t` could be certified with the catalog's key on `t`. Candidate fix ec6cb74c (741 lines): a
schema- or catalog-qualified name keeps its qualifiers and matches no catalog table (`unknown-table`, fail closed).

| Job | Purpose | Est. | Walltime | Resources | Command | Status |
|---|---|---|---|---|---|---|
| 61902063 | Unit check: qualified names on 7626553a (old) vs ec6cb74c (new), both dialects; `qualified_check.py` md5 ee81d28e | 1 min | 30 min | <CPU_ACCOUNT> <CPU_PARTITION>, 2 CPU, 4 GB | `code/obsdet_v7: sbatch --job-name=obsdet-qualchk --cpus-per-task=2 --mem=4G --time=00:30:00 run_cpu.sbatch qualified_check.py runs/obsdet/v7/certify_candidate3.py runs/obsdet/v7/certify_candidate4.py runs/obsdet/v7/qualified_check.json` | COMPLETED 0:03: the defect is real — 7626553a returns DET for `SELECT x FROM evil.t ORDER BY id LIMIT 1` (and for `main.t`, `public.t`, three-part names, a join and an IN subquery over `evil.t`) in both dialects; ec6cb74c returns UNSUPPORTED/unknown-table for all of them and DET for the unqualified control; 11/11 expectations met (`logs/obsdet-qualchk-61902063.out`, `runs/obsdet/v7/qualified_check.json`) |
| 61902064 | 1369ffca vs ec6cb74c diff (`runs/obsdet/v7/certify_candidate4.py`) on every evaluated set | 3 min | 2 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | as 61889511 with certify_candidate4.py, output `runs/obsdet/v7/v7_diff6.json` | COMPLETED 2:47; 0 differences on every set (same 14 sets as 61889511, both dialects; `logs/obsdet-v7diff6-61902064.out`) |

**Certifier of record from about 2026-09-25 17:33 PDT (superseded at 17:36 PDT, see below): ec6cb74c (md5 ec6cb74cfd376fc5cece1c58a8a50d84, 741 lines; local `experiments/obsdet/certify.py`, cluster `runs/obsdet/v7/certify_candidate4.py`).** It differs from 7626553a only for schema- or catalog-qualified table names, which it rejects; job 61902064 shows the same verdicts and tie-breaks as 1369ffca on every evaluated statement, so the v7 results stand for it. The adversarial suite (61889821), the property-based runs (JOBS_PROPTEST.md) and the latency job (61895574) ran on 7626553a; none of their statements names a qualified table, so their results hold for ec6cb74c unchanged. `code/obsdet_v7final/certify.py` on the cluster stays 7626553a, the version those jobs recorded.

**Docstring revision (proof re-audit round 2, issue 5).** The module docstring now says that the verdict meanings are
those the paper's rules prove and that the code's reading of SQL is premise (vi). certify.py md5
80705f632bf861731a2084d2cf5c1306, 743 lines; the only difference from ec6cb74c is those two docstring lines.

| Job | Purpose | Est. | Walltime | Resources | Command | Status |
|---|---|---|---|---|---|---|
| 61902354 | Unit check on 80705f63 (`runs/obsdet/v7/certify_candidate5.py`) vs 7626553a | 1 min | 30 min | <CPU_ACCOUNT> <CPU_PARTITION>, 2 CPU, 4 GB | as 61902063 with certify_candidate5.py, output `qualified_check2.json` | COMPLETED 0:04; 11/11 expectations met |
| 61902355 | 1369ffca vs 80705f63 diff on every evaluated set | 3 min | 2 h | <CPU_ACCOUNT> <CPU_PARTITION>, 8 CPU, 32 GB | as 61902064 with certify_candidate5.py, output `runs/obsdet/v7/v7_diff7.json` | COMPLETED 2:50; 0 differences on every set (same 14 sets) |
| 61902889 | Namespace facts for the blind review's BR-01: DDL on read-only DuckDB connections, relations named like each catalog table in every evaluated database, non-SELECT statements in the E4 traces, not-select statements in the certificate sets; `namespace_check.py` md5 15677fa5 | 2 min | 30 min | <CPU_ACCOUNT> <CPU_PARTITION>, 2 CPU, 8 GB | `code/obsdet_v7: sbatch --job-name=obsdet-nscheck --cpus-per-task=2 --mem=8G --time=00:30:00 run_cpu.sbatch namespace_check.py runs/obsdet/catalog.json data/bird_duckdb/validation runs/obsdet/v7/namespace_check.json <4 cert files> <E4 v5, v6td, v7, v7td, v7td2 trace dirs>` | COMPLETED 0:08 (see below) |

**Certifier of record since 2026-09-25 17:36 PDT (verified by 17:45 PDT): 80705f63 (md5 80705f632bf861731a2084d2cf5c1306, 743 lines; local
`experiments/obsdet/certify.py`, cluster `runs/obsdet/v7/certify_candidate5.py`).** It supersedes ec6cb74c (same code,
two more docstring lines); everything said above about ec6cb74c holds for it (jobs 61902354, 61902355).

### Name binding and state changes in the agent tool (proof blind review BR-01, 2026-09-25 17:45-18:05 PDT)

The blind proof review claimed that an unqualified table name could resolve outside the catalog (search_path, temporary
tables). Facts (`namespace_check.py`, job 61902889): a read-only DuckDB connection accepts CREATE TEMP TABLE/VIEW;
every catalog table name denotes exactly one relation in each of the 11 databases; across all E4 traces agents sent no
CREATE, ATTACH, USE, SET, INSERT, UPDATE, DELETE, DROP, ALTER or COPY statement (only queries, PRAGMA/DESCRIBE/SHOW
lookups and statements that failed). A first harness guard (namespace fingerprint per call) was written and then
**reverted**: on the old code it never alarmed, because each tool call runs on a fresh cursor, so temporary tables and
session settings die with the call, and DuckDB refuses `SET GLOBAL search_path`/`schema` (jobs 61903339/61903340 had a
wrong test expectation; 61903401/61903402 show 0 unsound certificates with and without the guard). What does fail on
the E4 instance (`observe.open_instance`: a writable in-memory copy on which `SET` reaches every later cursor) is a
statement that changes the database or a setting: `readonly_tool_check.py` (job 61903973, v7 code) gives 8 unsound
certificates (CREATE OR REPLACE TABLE, INSERT of a duplicate key, SET default_null_order, ATTACH ':memory:' plus a
qualified query), and 0 with the final code (job 61903974). The final tool therefore runs only statements that DuckDB
parses as queries (`tool.is_query`; DuckDB's SELECT type includes DESCRIBE, SHOW and PRAGMA table_info). Job 61903554
(`statement_types_check.py`) shows that every agent statement in the E4 traces that parsed is of that type (78,407
statements; 464 parse errors and some comment-only statements, which the engine rejects as before), so the filter
would not have changed any recorded call.

| Job | Purpose | Status |
|---|---|---|
| 61903339 / 61903340 | First guard check, v7 code / guarded code (`namespace_guard_check.py` md5 95eec4a1) | COMPLETED; expectations wrong (temporary tables do not outlive a call); superseded |
| 61903401 / 61903402 | Guard check by process-isolated scenarios (md5 c62a8b15) | COMPLETED; 0 unsound certificates for both; guard reverted |
| 61903452 / 61903453 | Name binding: v7 code / final certifier 80705f63 with the v7 tool and harness (md5 62eedc5d) | COMPLETED; v7: 2 unsound (ATTACH a file + `other.users`); final: 0 |
| 61903554 | Statement types, setting leaks, all E4 agent statements (`statement_types_check.py` md5 md5-withheld) | COMPLETED 0:10; SET reaches later cursors; agents' parsed statements all SELECT-type |
| 61903934 / 61903935 | Read-only tool check, first submission | FAILED (script computed a truth for `m.users` on a fresh instance); fixed |
| 61903973 / 61903974 | Read-only tool check (`readonly_tool_check.py` md5 md5-withheld), v7 code / final code (tool.py d5408a0b, certify 80705f63, v7 harness) | COMPLETED; v7: 8 unsound; final: 0 |

**Tool of record since 2026-09-25 18:02 PDT: `experiments/obsdet/tool.py` md5 d5408a0b, 57 lines** (the v7 tool plus
`is_query`); the E4 harness `agent_det3.py` is unchanged. Result files: `results/v7/{namespace_check,statement_types,
name_binding_*,readonly_tool_*,namespace_guard2_*,qualified_check*,v7_diff6,v7_diff7}.json`, logs in `results/v7/logs/`.

### Blind review 2 of the proof re-audit (2026-09-25 18:10-18:25 PDT)

BR-01 claimed that `x = <exact numeric literal>` compares as DOUBLE when the exact common decimal would exceed 38
digits, so that two stored values could both equal the literal. **Refuted by measurement** (job 61905448 on 1369ffca,
7626553a and 80705f63; job 61905604 on 80705f63 with three more cases, `constant_coercion_check.py` md5 4f09fad1): in
DuckDB 1.5.5 every literal of up to 38 digits compares exactly (0 or 1 matching row where DOUBLE would match 2); the
only lossy case is a 39-digit literal, which DuckDB and the certifier both type DOUBLE, so no constant is created and
the verdict is ALL with `x` appended (a total order; the script's `unsound` flag for that case counts ALL and is wrong).
BR-02 (a failed exact count left the call successful; a trailing line comment made the count fail) is real: job
61905605 (`count_path_check.py` md5 md5-withheld) gives 3 contract violations for the v7 tool and 0 for the fixed tool
(md5-withheld: newlines around the counted statement; a failed count makes the call fail). No recorded call is affected:
0 of the 78,958 E4 trace records had a failed count, and the soundness replays already treated a successful but
still truncated result as censored (`replay_sound.py` line 53).

| Job | Purpose | Status |
|---|---|---|
| 61905448 | Constant coercion, 9 cases, three certifiers | COMPLETED 0:04; no lossy comparison |
| 61905604 | Constant coercion, 12 cases, 80705f63 | COMPLETED 0:07; lossy only for the 39-digit literal (verdict ALL) |
| 61905605 | Count path, v7 tool vs md5-withheld, with and without a simulated count failure | COMPLETED 0:10; violations old 3, new 0 |

**Tool of record since 2026-09-25 18:22 PDT: tool.py md5 md5-withheld, 58 lines** (d5408a0b plus the count fixes).

### Blind review 2, follow-up (2026-09-25 18:28-18:40 PDT)

The reviewer withdrew BR-01 after the measurements and closed BR-02 and BR-04, then raised BR-05 (the coercion
script counted an ALL verdict as unsound; fixed: only DET on a lossy predicate counts) and BR-06 (a catalog table
literally named `s.t` could collide with the qualified reference `s.t` after `_sources()` joins the parts with dots).
BR-06 is **not reachable**: with such a catalog, sqlglot's qualification already fails and the certifier returns
UNSUPPORTED (`unresolved:OptimizeError`) on 80705f63 (job 61906593). A tuple-key change (7555f24d) was written, checked
(jobs 61906593, 61906594: 0 differences on every set) and **reverted**, since the current code never fails on that
input; `qualified_check.py` keeps the case. certify.py is again 80705f63.

| Job | Purpose | Status |
|---|---|---|
| 61906593 | `qualified_check.py` (md5 027f92b2) on 80705f63 vs 7555f24d, with the dotted-name case in its own catalog | COMPLETED; 13/13 expectations met by both; the dotted case is UNSUPPORTED (unresolved) on both |
| 61906594 | 1369ffca vs 7555f24d diff | COMPLETED 2:46; 0 differences on every set; candidate reverted |
| 61906595 | Constant coercion, 12 cases, corrected criterion (`constant_coercion_check.py` md5 1b3fda5b) | COMPLETED 0:02; 1 lossy case (39 digits, verdict ALL), 0 DET on a lossy predicate |


### Claim-audit evidence added (2026-09-25 19:05 PDT, local, no cluster compute)

- `v6_v7_tiebreak_diff.py` (md5 e6fbeecb) → `results/v7/v6_v7_tiebreak_diff.json`: DuckDB certificates of v6 vs v7 per
  statement; on the paper's sets 1/1/4 verdict changes (all to UNSUPPORTED) and 0+6+1 = 7 tie-break changes apart from
  identifier quoting.
- `results/v7/provenance_sacct.txt`: scheduler records (Submit/Start/End, America/Detroit) of the selection,
  certification and agent-run jobs behind the paper's chronology (61872271 ... 61888188).
