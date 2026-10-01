# E3 (cost) job log

Cluster: <CLUSTER>, account `<CPU_ACCOUNT>`, partition `<CPU_PARTITION>`, CPU only, 8 cpus per job.
Root: `$PROJECT_ROOT` (below: `$V`). Logs: `$V/runs/obsdet/cost/logs/<name>-<jobid>.out`.
Probe input for all natural replays: `runs/obsdet/cert_probes_v3.jsonl` (md5 c53ded0cc48f5a8b6c724381ceafa079, 1,015 probes; certifier fixed by the lead, lead message 2026-09-25 ~06:28 PDT). Code: `code/obsdet/cost_duck.py` (+ `cost_duck.sbatch`), `pg_setup.py`, `pg_cost.py` (+ `pg_cost.sbatch`), `cost_analyze.py`.
PostgreSQL: 16.2 binaries from the pgserver wheel (`code/pilot_c6/pylib/pgserver/pginstall`), one private server per job, data dir `runs/obsdet/pg/<server>/`, unix socket `/tmp/obsdet_e3pg_<server>` on the compute node, stopped on job exit.

| Job id | Name | Purpose | Resources | Walltime | Output | Submitted (PDT) | Status |
|---|---|---|---|---|---|---|---|
| 61872428 | e3-smoke | srun smoke test of cost_duck.py (SF1, 4 card_games probes of v2 + controlled SF1); output deleted | 8 cpu, 16G | 15 min | (deleted) | 06:27 | done |
| 61873047 | e3-pgsmoke | srun smoke test of pg_setup.py/pg_cost.py (server `smoke`, california_schools SF1, 12 probes x 2 reps); data dir and output deleted | 8 cpu, 16G | 20 min | (deleted) | 06:35 | done |
| 61872453 | e3-duck-sf1 | natural probes, DuckDB SF1, all 6 DBs, 5 reps | 8 cpu, 16G (duckdb 12GB) | 1:30 | `runs/obsdet/cost/duck_nat_sf1.jsonl` | 06:32 | COMPLETED |
| 61872455 | e3-duck-x10a | natural probes, DuckDB x10, 5 DBs (not codebase_community) | 8 cpu, 32G (24GB) | 3:00 | `duck_nat_x10a.jsonl` | 06:32 | COMPLETED |
| 61872456 | e3-duck-x10cc | natural probes, DuckDB x10, codebase_community | 8 cpu, 48G (36GB) | 4:00 | `duck_nat_x10cc.jsonl` | 06:32 | COMPLETED |
| 61872457 | e3-duck-xmaxa | natural probes, DuckDB x100: california_schools, debit_card_specializing, formula_1, thrombosis_prediction; + EXPLAIN ANALYZE JSON per policy | 8 cpu, 32G (24GB) | 4:00 | `duck_nat_xmaxa.jsonl` | 06:32 | COMPLETED |
| 61872458 | e3-duck-xmaxcg | natural probes, DuckDB x100 card_games + profile | 8 cpu, 64G (48GB) | 6:00 | `duck_nat_xmaxcg.jsonl` | 06:32 | COMPLETED |
| 61872460 | e3-duck-xmaxcc | natural probes, DuckDB x30 codebase_community + profile | 8 cpu, 96G (72GB) | 6:00 | `duck_nat_xmaxcc.jsonl` | 06:32 | COMPLETED |
| 61872461 | e3-duck-ctl | controlled LIMIT study, DuckDB SF1 -> x10 -> xmax (5 tables x 3 forms) + profile | 8 cpu, 96G (72GB) | 3:00 | `duck_ctl.jsonl` | 06:32 | COMPLETED |
| 61873052 | e3-pg-cc | PG server `codebase_community` (shared_buffers 24GB): load SF1+x10, natural replay SF1->x10 (+EXPLAIN at x10), controlled study SF1/x10 | 8 cpu, 64G | 12:00 | `pg_nat_codebase_community.jsonl`, `pg_ctl_codebase_community.jsonl` | 06:38 | submitted |
| 61873053 | e3-pg-cg | PG server `card_games` (12GB): same for card_games | 8 cpu, 40G | 10:00 | `pg_nat_card_games.jsonl`, `pg_ctl_card_games.jsonl` | 06:38 | submitted |
| 61873054 | e3-pg-f1 | PG server `formula_1` (4GB): load + natural replay | 8 cpu, 16G | 6:00 | `pg_nat_formula_1.jsonl` | 06:38 | submitted |
| 61873055 | e3-pg-cs | PG server `california_schools` (4GB): load + natural replay | 8 cpu, 16G | 6:00 | `pg_nat_california_schools.jsonl` | 06:38 | submitted |
| 61873056 | e3-pg-small | PG server `small` (4GB): debit_card_specializing + thrombosis_prediction | 8 cpu, 16G | 4:00 | `pg_nat_debit_card_specializing.jsonl`, `pg_nat_thrombosis_prediction.jsonl` | 06:38 | submitted |

## Lead update (~06:53 PDT): preview + count cost model; certifier v4 pending

The runs above (`duck_nat_*`, `duck_ctl`, `pg_nat_*`, `pg_ctl_*`, cert file v3) are kept as the table "tool as implemented in the pilot" (each policy's SQL fetched up to 100,000 rows).
New model (`--model pc`): preview = policy SQL with top-level LIMIT min(L, 20) (OFFSET kept, LIMIT 20 added if absent; AST edit), count = `SELECT count(*) FROM (<original SQL without top-level ORDER BY>)`, same count for every policy; total = preview + count. Runs on v3 below are provisional; final numbers use `cert_probes_v4.jsonl` when it exists.

| Job id | Name | Purpose | Resources | Walltime | Output | Submitted (PDT) | Status |
|---|---|---|---|---|---|---|---|
| (srun) | e3-pcsmoke | smoke test of `--model pc` (DuckDB card_games SF1 4 probes; PG server formula_1 SF1 4 probes); output deleted | 8 cpu, 16G | 20 min | (deleted) | 06:56 | done |
| 61873588 | e3-pc3-sf1 | DuckDB pc model, SF1, all DBs, v3 | 8 cpu, 16G (12GB) | 1:30 | `duck_pcnat_v3_sf1.jsonl` | 06:57 | submitted |
| 61873589 | e3-pc3-x10a | DuckDB pc, x10, 5 DBs, v3 | 8 cpu, 32G (24GB) | 2:00 | `duck_pcnat_v3_x10a.jsonl` | 06:57 | submitted |
| 61873590 | e3-pc3-x10cc | DuckDB pc, x10 codebase_community, v3 | 8 cpu, 48G (36GB) | 2:00 | `duck_pcnat_v3_x10cc.jsonl` | 06:57 | submitted |
| 61873591 | e3-pc3-xmaxa | DuckDB pc, x100 4 DBs, v3, profile of preview queries, skip list from `duck_nat_x10a.jsonl` | 8 cpu, 32G (24GB) | 3:00 | `duck_pcnat_v3_xmaxa.jsonl` | 06:57 | submitted |
| 61873592 | e3-pc3-xmaxcg | DuckDB pc, x100 card_games, v3, profile | 8 cpu, 64G (48GB) | 3:00 | `duck_pcnat_v3_xmaxcg.jsonl` | 06:57 | submitted |
| 61873593 | e3-pc3-xmaxcc | DuckDB pc, x30 codebase_community, v3, profile, skip list from `duck_nat_x10cc.jsonl` | 8 cpu, 96G (72GB) | 3:00 | `duck_pcnat_v3_xmaxcc.jsonl` | 06:57 | submitted |
| 61873599 | e3-pgpc3-cc | PG pc model, server codebase_community, SF1 + x10, EXPLAIN of previews at x10, v3, no controlled study | 8 cpu, 64G | 6:00 | `pg_pcnat_v3_codebase_community.jsonl` | 06:58 | submitted |
| 61873600 | e3-pgpc3-f1 | PG pc, server formula_1, v3 | 8 cpu, 16G | 3:00 | `pg_pcnat_v3_formula_1.jsonl` | 06:58 | submitted |
| 61873601 | e3-pgpc3-small | PG pc, server small (debit_card_specializing, thrombosis_prediction), v3 | 8 cpu, 16G | 3:00 | `pg_pcnat_v3_<db>.jsonl` | 06:58 | submitted |

### Final runs on `cert_probes_v4.jsonl` (md5 efbb39264e8d7a25401065942bb446e4, written 06:58 PDT by the lead's job 61873586 obsdet-e1v4; certify.py md5 ee978208b9d2c3b36aab69abc1308084), submitted 07:01 PDT with `bash code/obsdet/cost_launch.sh v4 runs/obsdet/cert_probes_v4.jsonl`

| Job id | Name | Purpose | Resources | Walltime | Output | Status |
|---|---|---|---|---|---|---|
| 61873662 | e3-pcv4-sf1 | DuckDB pc, SF1, all DBs | 8 cpu, 16G (12GB) | 1:30 | `duck_pcnat_v4_sf1.jsonl` | COMPLETED (superseded by v5) |
| 61873663 | e3-pcv4-x10a | DuckDB pc, x10, 5 DBs | 8 cpu, 32G (24GB) | 2:00 | `duck_pcnat_v4_x10a.jsonl` | COMPLETED (superseded by v5) |
| 61873664 | e3-pcv4-x10cc | DuckDB pc, x10 codebase_community | 8 cpu, 48G (36GB) | 2:00 | `duck_pcnat_v4_x10cc.jsonl` | COMPLETED (superseded by v5) |
| 61873665 | e3-pcv4-xmaxa | DuckDB pc, x100 4 DBs, profile of previews, skip list `duck_nat_x10a.jsonl` | 8 cpu, 32G (24GB) | 3:00 | `duck_pcnat_v4_xmaxa.jsonl` | COMPLETED (superseded by v5) |
| 61873666 | e3-pcv4-xmaxcg | DuckDB pc, x100 card_games, profile | 8 cpu, 64G (48GB) | 3:00 | `duck_pcnat_v4_xmaxcg.jsonl` | COMPLETED (superseded by v5) |
| 61873667 | e3-pcv4-xmaxcc | DuckDB pc, x30 codebase_community, profile, skip list `duck_nat_x10cc.jsonl` | 8 cpu, 96G (72GB) | 3:00 | `duck_pcnat_v4_xmaxcc.jsonl` | COMPLETED (superseded by v5) |
| 61873668 | e3-pcv4-ctl | DuckDB controlled LIMIT study, pc model, SF1 -> x10 -> xmax, profile (certify.py as fixed) | 8 cpu, 96G (72GB) | 2:00 | `duck_pcctl_v4.jsonl` | COMPLETED (superseded by v5) |
| 61873669 | e3-pgpcv4-cc | PG pc, server codebase_community, SF1 + x10, EXPLAIN of previews at x10, controlled study (after 61873599) | 8 cpu, 64G | 6:00 | `pg_pcnat_v4_codebase_community.jsonl`, `pg_pcctl_v4_codebase_community.jsonl` | COMPLETED (superseded by v5) |
| 61873670 | e3-pgpcv4-cg | PG pc, server card_games, + controlled (after 61873053) | 8 cpu, 40G | 6:00 | `pg_pcnat_v4_card_games.jsonl` (partial) | CANCELLED 07:25 (superseded by v5) |
| 61873671 | e3-pgpcv4-cs | PG pc, server california_schools (after 61873055) | 8 cpu, 16G | 4:00 | `pg_pcnat_v4_california_schools.jsonl` | CANCELLED while pending (07:18): the old pilot job 61873055 still held the server; replaced by 61874009 on a fresh data dir |
| 61874009 | e3-pgpcv4-cs2 | PG pc, new server `california_schools_v4` (fresh data dir), v4 | 8 cpu, 16G | 4:00 | `pg_pcnat_v4_california_schools.jsonl` (partial) | CANCELLED 07:25 (superseded by v5) |
| 61873672 | e3-pgpcv4-f1 | PG pc, server formula_1 | 8 cpu, 16G | 3:00 | `pg_pcnat_v4_formula_1.jsonl` | COMPLETED (superseded by v5) |
| 61873673 | e3-pgpcv4-small | PG pc, server small (after 61873601) | 8 cpu, 16G | 3:00 | `pg_pcnat_v4_<db>.jsonl` | COMPLETED (superseded by v5) |
| 61874000 | e3-pgdiag-cc | diagnostic: probe #582 (codebase_community, verdict ALL) at PG x10 under the pc model with a 45-min statement_timeout, one run per query plus plain EXPLAIN. It is the only probe whose smartlex preview and count hit the 60 s timeout at x10. | 8 cpu, 64G | 2:00 | `pg_diag_v4_582_x10.json` | COMPLETED ~08:52. Single uncensored run at PG x10: raw preview 0.148 s, smartlex preview 2,592.2 s, certified preview (`ORDER BY badges.id`, v4 certificate) 0.065 s, count 2,595.5 s. The agent's subquery `SELECT UserId FROM users` binds `UserId` to the outer `badges` (users has no UserId column), so PostgreSQL evaluates a correlated SubPlan per badges row. |

## Lead update (~07:20 PDT): certificates v5 are final; PostgreSQL observation in one read-only transaction

`runs/obsdet/cert_probes_v5.jsonl` (md5 b9f9d046726729ed5ab985798ab06940, written 07:23 PDT by the lead's job 61874111; certify.py md5 991a260cb2eb09f71e5d9757d2948698). Compared with v4, 7 probes changed verdict or rewrite, and smartlex is unchanged. The v4 runs above are superseded. Everything (all three policies and the count) is rerun on v5, so the paired, shuffled design is kept.
PostgreSQL now uses `--model pctxn`: per repetition, each policy's observation runs as `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; preview; count; COMMIT` (policies shuffled). Preview, count and whole-transaction times are recorded. The PostgreSQL total is the transaction time. Each job uses a fresh server data directory `runs/obsdet/pg/<server>_v5/`, so no job waits on another version's server.
DuckDB is unchanged (`--model pc`: the count runs as a fourth shuffled query and is charged to every policy). Submitted 07:25 PDT with `bash code/obsdet/cost_launch.sh v5 runs/obsdet/cert_probes_v5.jsonl`.

| Job id | Name | Purpose | Resources | Walltime | Output | Status |
|---|---|---|---|---|---|---|
| (srun) | e3-txnsmoke | smoke test of `--model pctxn` (fresh server `txnsmoke`, formula_1 SF1, 5 probes x 2 reps); data dir and output deleted | 8 cpu, 16G | 15 min | (deleted) | done 07:25 |
| 61874170 | e3-pcv5-sf1 | DuckDB pc, SF1, all DBs | 8 cpu, 16G (12GB) | 1:30 | `duck_pcnat_v5_sf1.jsonl` | COMPLETED (superseded by v6) |
| 61874171 | e3-pcv5-x10a | DuckDB pc, x10, 5 DBs | 8 cpu, 32G (24GB) | 2:00 | `duck_pcnat_v5_x10a.jsonl` | COMPLETED (superseded by v6) |
| 61874172 | e3-pcv5-x10cc | DuckDB pc, x10 codebase_community | 8 cpu, 48G (36GB) | 2:00 | `duck_pcnat_v5_x10cc.jsonl` | COMPLETED (superseded by v6) |
| 61874173 | e3-pcv5-xmaxa | DuckDB pc, x100 4 DBs, profile, skip list `duck_nat_x10a.jsonl` | 8 cpu, 32G (24GB) | 3:00 | `duck_pcnat_v5_xmaxa.jsonl` | COMPLETED (superseded by v6) |
| 61874174 | e3-pcv5-xmaxcg | DuckDB pc, x100 card_games, profile | 8 cpu, 64G (48GB) | 3:00 | `duck_pcnat_v5_xmaxcg.jsonl` | COMPLETED (superseded by v6) |
| 61874175 | e3-pcv5-xmaxcc | DuckDB pc, x30 codebase_community, profile, skip list `duck_nat_x10cc.jsonl` | 8 cpu, 96G (72GB) | 3:00 | `duck_pcnat_v5_xmaxcc.jsonl` | COMPLETED (superseded by v6) |
| 61874176 | e3-pcv5-ctl | DuckDB controlled LIMIT study, pc, SF1/x10/xmax, profile (certify.py v5) | 8 cpu, 96G (72GB) | 2:00 | `duck_pcctl_v5.jsonl` | COMPLETED (superseded by v6) |
| 61874177 | e3-pgpcv5-cc | PG pctxn, server `codebase_community_v5`: load SF1+x10, natural SF1->x10, EXPLAIN of previews at x10, controlled study | 8 cpu, 64G | 6:00 | `pg_pcnat_v5_codebase_community.jsonl`, `pg_pcctl_v5_codebase_community.jsonl` | COMPLETED (superseded by v6) |
| 61874178 | e3-pgpcv5-cg | PG pctxn, server `card_games_v5` (+ controlled) | 8 cpu, 40G | 6:00 | `pg_pcnat_v5_card_games.jsonl`, `pg_pcctl_v5_card_games.jsonl` | CANCELLED 07:58 after 32 min, unfinished (superseded by v6) |
| 61874179 | e3-pgpcv5-cs | PG pctxn, server `california_schools_v5` | 8 cpu, 16G | 4:00 | `pg_pcnat_v5_california_schools.jsonl` | CANCELLED 07:58 after 32 min, unfinished (superseded by v6) |
| 61874180 | e3-pgpcv5-f1 | PG pctxn, server `formula_1_v5` | 8 cpu, 16G | 3:00 | `pg_pcnat_v5_formula_1.jsonl` | COMPLETED (superseded by v6) |
| 61874181 | e3-pgpcv5-small | PG pctxn, server `small_v5` (debit_card_specializing, thrombosis_prediction) | 8 cpu, 16G | 3:00 | `pg_pcnat_v5_<db>.jsonl` | COMPLETED (superseded by v6) |

## Lead update (~07:55 PDT): certificates v6 are FINAL

`runs/obsdet/cert_probes_v6.jsonl` (md5 bea7c02ea43c20b139f6b9ef6b1104ba, 1,015 probes, written 07:58 PDT by the lead's job 61875301; certify.py md5 c0f9e50f3cd3e21a376fab451d40e95c). Verdicts: NARROW 512, ALL 177, DET 166, UNSUPPORTED 160. Compared with v5, 22 probes changed verdict or rewrite (8 NARROW→ALL, 2 NARROW→UNSUPPORTED, the rest rewrites), and smartlex is unchanged.
The unfinished v5 PostgreSQL jobs were cancelled (see above). Everything (all three policies and the count, the controlled study with the v6 certify.py, EXPLAIN/profiles) is rerun on v6 with the same launcher, submitted 07:59 PDT: `bash code/obsdet/cost_launch.sh v6 runs/obsdet/cert_probes_v6.jsonl`. DuckDB uses model pc; PostgreSQL uses model pctxn on fresh servers `runs/obsdet/pg/<server>_v6/`.

| Job id | Name | Purpose | Resources | Walltime | Output | Status |
|---|---|---|---|---|---|---|
| 61875348 | e3-pcv6-sf1 | DuckDB pc, SF1, all DBs | 8 cpu, 16G (12GB) | 1:30 | `duck_pcnat_v6_sf1.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875349 | e3-pcv6-x10a | DuckDB pc, x10, 5 DBs | 8 cpu, 32G (24GB) | 2:00 | `duck_pcnat_v6_x10a.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875350 | e3-pcv6-x10cc | DuckDB pc, x10 codebase_community | 8 cpu, 48G (36GB) | 2:00 | `duck_pcnat_v6_x10cc.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875351 | e3-pcv6-xmaxa | DuckDB pc, x100 4 DBs, profile, skip list `duck_nat_x10a.jsonl` | 8 cpu, 32G (24GB) | 3:00 | `duck_pcnat_v6_xmaxa.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875352 | e3-pcv6-xmaxcg | DuckDB pc, x100 card_games, profile | 8 cpu, 64G (48GB) | 3:00 | `duck_pcnat_v6_xmaxcg.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875353 | e3-pcv6-xmaxcc | DuckDB pc, x30 codebase_community, profile, skip list `duck_nat_x10cc.jsonl` | 8 cpu, 96G (72GB) | 3:00 | `duck_pcnat_v6_xmaxcc.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875354 | e3-pcv6-ctl | DuckDB controlled LIMIT study, pc, SF1/x10/xmax, profile (certify.py v6) | 8 cpu, 96G (72GB) | 2:00 | `duck_pcctl_v6.jsonl` | COMPLETED (FINAL DuckDB) |
| 61875355 | e3-pgpcv6-cc | PG pctxn, server `codebase_community_v6`: load SF1+x10, natural SF1->x10, EXPLAIN of previews at x10, controlled study | 8 cpu, 64G | 6:00 | `pg_pcnat_v6_codebase_community.jsonl`, `pg_pcctl_v6_codebase_community.jsonl` | COMPLETED, superseded: PG policies were transpiled DuckDB rewrites |
| 61875356 | e3-pgpcv6-cg | PG pctxn, server `card_games_v6` (+ controlled) | 8 cpu, 40G | 6:00 | `pg_pcnat_v6_card_games.jsonl`, `pg_pcctl_v6_card_games.jsonl` | CANCELLED 08:47, superseded (transpiled DuckDB rewrites) |
| 61875357 | e3-pgpcv6-cs | PG pctxn, server `california_schools_v6` | 8 cpu, 16G | 4:00 | `pg_pcnat_v6_california_schools.jsonl` | CANCELLED 08:47, superseded (transpiled DuckDB rewrites) |
| 61875358 | e3-pgpcv6-f1 | PG pctxn, server `formula_1_v6` | 8 cpu, 16G | 3:00 | `pg_pcnat_v6_formula_1.jsonl` | COMPLETED, superseded (transpiled DuckDB rewrites) |
| 61875359 | e3-pgpcv6-small | PG pctxn, server `small_v6` (debit_card_specializing, thrombosis_prediction) | 8 cpu, 16G | 3:00 | `pg_pcnat_v6_<db>.jsonl` | COMPLETED, superseded (transpiled DuckDB rewrites) |

Housekeeping (08:02 PDT): deleted the superseded PostgreSQL data directories `runs/obsdet/pg/{card_games,formula_1,california_schools,small,california_schools_v4,*_v5}` together with their `.loaded_*` markers. They can be rebuilt in minutes from the DuckDB copies. The glob also removed the markers of `*_v6` loads that had already completed; these were restored from the job logs, and the running v6 jobs were unaffected (their load step had already passed). Kept: `codebase_community` (used by diagnostic 61874000), `*_v6`, and the lead's `e1pg`.

## Lead update (~08:40 PDT, review round 1): PostgreSQL uses PostgreSQL-dialect certificates

`pg_cost.py --pgcert` builds each PostgreSQL policy the way `replay_pg.py` does:
- `raw = to_pg(sql)`;
- `cert = certify(raw, catalog with lowercased tables and columns, "postgres")`;
- `smartlex = smartlex(raw, n_out, "postgres") or raw`;
- `certified = (cert.rewritten or raw)` if the verdict is not UNSUPPORTED, else smartlex.

Previews and the count are built in the postgres dialect. Each record keeps both verdicts (`verdict` = PostgreSQL certificate, `duckdb_verdict` = v6). Before this change, pg_cost.py transpiled the DuckDB-dialect rewrites; all PostgreSQL pc/pctxn runs up to here are superseded.
Probes: v6. certify.py on the cluster: md5 7aa9c889bb189b0740e83e258b83a7c4 (round 4, which changed only the PostgreSQL relative-time rule; the DuckDB certificates of v6 are unchanged). Smoke test (srun, server formula_1_v6, 6 probes; output deleted) passed at 08:48. The servers `*_v6` were already loaded (SF1 + x10); model pctxn.

| Job id | Name | Purpose | Resources | Walltime | Output | Status |
|---|---|---|---|---|---|---|
| 61877280 | e3-pgv6pg-cc | PG pctxn + pgcert, server codebase_community_v6: natural SF1->x10 (EXPLAIN of previews at x10), controlled SF1/x10 | 8 cpu, 64G | 6:00 | `pg_pcnat_v6pg_codebase_community.jsonl`, `pg_pcctl_v6pg_codebase_community.jsonl` | COMPLETED 12:37 (FINAL PostgreSQL) |
| 61877281 | e3-pgv6pg-cg | same, server card_games_v6 (+ controlled) | 8 cpu, 40G | 6:00 | `pg_pcnat_v6pg_card_games.jsonl`, `pg_pcctl_v6pg_card_games.jsonl` | COMPLETED 44:56 (FINAL PostgreSQL) |
| 61877282 | e3-pgv6pg-cs | same, server california_schools_v6 | 8 cpu, 16G | 4:00 | `pg_pcnat_v6pg_california_schools.jsonl` | COMPLETED 1:02:41 (FINAL PostgreSQL) |
| 61877283 | e3-pgv6pg-f1 | same, server formula_1_v6 | 8 cpu, 16G | 3:00 | `pg_pcnat_v6pg_formula_1.jsonl` | COMPLETED 2:26 (FINAL PostgreSQL) |
| 61877284 | e3-pgv6pg-small | same, server small_v6 (debit_card_specializing, thrombosis_prediction) | 8 cpu, 16G | 3:00 | `pg_pcnat_v6pg_<db>.jsonl` | COMPLETED 9:23 (FINAL PostgreSQL) |
| 61877227 | e3-pgcertsmoke | srun smoke test of `--pgcert` (server formula_1_v6, 6 probes); output deleted | 8 cpu, 16G | 15 min | (deleted) | COMPLETED 08:48 |
| 61883900, 61884054 | e3-analyze | `cost_analyze.py`, final analysis, run on a compute node (an earlier run on the login node was killed after ~2 min: the bootstraps are too heavy for it) | 1 cpu, 4G | 25 min | `runs/obsdet/cost/E3_analysis_v6.{md,json}`, `_per_probe.csv` | COMPLETED ~09:58 |
| 61884068 | e3-explain323 | plain EXPLAIN of probe #323's certified and smartlex previews at PG x10 (server card_games_v6) | 2 cpu, 16G | 10 min | quoted in RESULTS_E3.md | COMPLETED ~10:00 |

Housekeeping (~10:00 PDT): deleted `runs/obsdet/pg/codebase_community` (last used by the diagnostic 61874000). Kept `runs/obsdet/pg/*_v6` (about 17 GB and 24k files, including the lead's `e1pg*`; the fileset `<FILESET>` is at about 62% of its file quota) so the final PostgreSQL runs can be repeated without reloading. They are safe to delete; reloading takes about 5 minutes.
