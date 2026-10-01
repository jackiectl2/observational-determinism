# E1d property-based soundness test — job log

> **2026-09-25 17:45 PDT addendum.** The certifier of record is now 80705f63 (md5 80705f632bf861731a2084d2cf5c1306): 7626553a plus the rejection of schema- or catalog-qualified table names (`unknown-table`), found by the proof re-audit (`paper/PROOF_AUDIT.md`) and confirmed by jobs 61902063 and 61902354, and a docstring note. The generators name tables only by bare generated names and never emit a qualified name, so for every generated query 80705f63 returns what 7626553a returned, and the 7626553a results below hold for 80705f63 unchanged.

Code: `experiments/obsdet/proptest.py` (copied to `$V/code/obsdet/`), launcher `proptest.sbatch`.
`$V` = `$PROJECT_ROOT`. Account `<CPU_ACCOUNT>`, partition `<CPU_PARTITION>`, CPU only.
Outputs under `$V/runs/obsdet/proptest/<subdir>/`; logs `$V/runs/obsdet/proptest/logs/<job-name>-<id>.out`.
certify.py md5 7aa9c889bb189b0740e83e258b83a7c4 (unchanged).

| job id | name | purpose | resources | walltime | args | log | status |
|---|---|---|---|---|---|---|---|
| 61885724 | pt-smoke-duck | DuckDB smoke test (generator validity, timing) | 4 cpu, 8G | 0:30:00 | duck smoke 0 8 --queries 20 --instances 3 --workers 4 | logs/pt-smoke-duck-61885724.out | done 2026-09-25 10:42 PDT, 15 s; 160 queries, 0 violations |
| 61885790 | pt-duck-main | DuckDB main run: 2,000 schemas x 25 queries x 10 instances x 8 executions | 16 cpu, 32G | 4:00:00 | duck main 0 2000 --queries 25 --instances 10 --workers 16 | logs/pt-duck-main-61885790.out | done 11:02 PDT (17 min). Superseded by pt-duck-final (v1 harness counted header-only G2 differences as g2_bag and mis-tagged some queries oof:volatile) |
| 61885791 | pt-smoke-pg | PostgreSQL smoke test (private PG16 server `proptest`, socket /tmp/obsdet_e3pg_proptest) | 8 cpu, 16G | 0:30:00 | pg smoke 0 3 --queries 20 --instances 2 | logs/pt-smoke-pg-61885791.out | done 10:46 PDT, 11 s; 60 queries, 0 violations; server stopped |
| 61885820 | pt-pg-main | PostgreSQL main run v1: 240 schemas x 25 queries x 4 instances x 6 configurations | 8 cpu, 16G | 3:00:00 | pg main 0 240 --queries 25 --instances 4 | logs/pt-pg-main-61885820.out | done 10:54 PDT (~6 min). Superseded by pt-pg-final (same reasons) |
| 61886857 | pt-duck-final | DuckDB final run (proptest.py md5 68131b8b...): 2,000 schemas x 25 queries x 10 instances x 8 executions | 16 cpu, 32G | 4:00:00 | duck final 0 2000 --queries 25 --instances 10 --workers 16 | logs/pt-duck-final-61886857.out | submitted 11:04 PDT |
| 61886858 | pt-pg-final | PostgreSQL final run (same code): 400 schemas x 25 queries x 4 instances x 6 configurations (3 heap orders x serial/parallel) | 8 cpu, 16G | 3:00:00 | pg final 0 400 --queries 25 --instances 4 | logs/pt-pg-final-61886858.out | done 11:15 PDT (~10 min) |

Harness versions: v1 (main runs) md5 a3a173ca57ddb332a5ea0d53c5530bbf; final md5 68131b8b76b0d07d63b7547cfb879f6e (adds g2_header split, summary fields, reduce mode, and emits ORDER BY random() for every query tagged oof:volatile). Query generation for all other queries is identical (same seeds, same random draws).
| 61887587 | pt-post-final | minimal repros on DuckDB + PG (proptest_repro.py, server `proptest`), summaries, greedy instance reduction of DuckDB cert_div records | 4 cpu, 8G | 1:30:00 | --wrap (after 61886857) | logs/pt-post-final-61887587.out | submitted 11:24 PDT |
| 61887588 | pt-duck-v2 | DuckDB exploration with generator v2 (known-defect shapes, more functions, FILTER, EXISTS outputs, star EXCLUDE/REPLACE, alias-in-expression and subquery sort keys, more out-of-fragment kinds); fresh seeds | 16 cpu, 32G | 3:00:00 | duck explore_v2 10000 11000 --queries 25 --instances 10 --workers 16 --gen v2 | logs/pt-duck-v2-61887588.out | submitted 11:24 PDT |
| 61887589 | pt-pg-v2 | PostgreSQL exploration with generator v2 | 8 cpu, 16G | 3:00:00 | pg explore_v2 10000 10240 --queries 25 --instances 4 --gen v2 (after 61887587) | logs/pt-pg-v2-61887589.out | submitted 11:24 PDT |

proptest.py md5 308adb5f... (v2 generator behind --gen v2; v1 generation verified identical: 6/6 seeds regenerate the recorded SQL sequences of the final run). proptest_repro.py md5 67e36c8d....

## Against certifier v7 (`$V/code/obsdet_v7/certify.py`, md5 0353e3eeec5ef4da74220c9160b1d460, loaded via `--certify <path>`; code/obsdet stays at v6)

proptest.py md5 97d5e486... (adds `--certify`; generation unchanged). Outputs in separate dirs `v7_*`.

| job id | name | purpose | resources | walltime | args | log | status |
|---|---|---|---|---|---|---|---|
| 61888041 | pt7-duck-final | v7, DuckDB, generator v1, same scale/seeds as pt-duck-final | 16 cpu, 32G | 4:00:00 | duck v7_final 0 2000 --queries 25 --instances 10 --workers 16 --certify $C7 | logs/pt7-duck-final-61888041.out | submitted 11:41 PDT |
| 61888042 | pt7-duck-v2 | v7, DuckDB, generator v2, same seeds as pt-duck-v2 | 16 cpu, 32G | 3:00:00 | duck v7_explore_v2 10000 11000 ... --gen v2 --certify $C7 | logs/pt7-duck-v2-61888042.out | submitted 11:41 PDT |
| 61888043 | pt7-pg-final | v7, PostgreSQL, generator v1, same seeds as pt-pg-final (after pt-pg-v2; one PG server at a time) | 8 cpu, 16G | 3:00:00 | pg v7_final 0 400 --queries 25 --instances 4 --certify $C7 | logs/pt7-pg-final-61888043.out | submitted 11:41 PDT |
| 61888044 | pt7-pg-v2 | v7, PostgreSQL, generator v2 (after pt7-pg-final) | 8 cpu, 16G | 3:00:00 | pg v7_explore_v2 10000 10240 ... --gen v2 --certify $C7 | logs/pt7-pg-v2-61888044.out | submitted 11:41 PDT |

Note 11:42 PDT: removed the dependency of 61887589 (pt-pg-v2) on 61887587 (its PostgreSQL part had finished and the server was stopped; only the DuckDB instance reduction was still running).
Interim report with all v6 violations sent to the lead at ~11:40 PDT.
| 61888101 | pt7-duck-v3 | v7, DuckDB, generator v3 (v2 + syntax whose sqlglot regeneration may differ: typed-literal casts, ::, ^/**, simple CASE, IS [NOT] DISTINCT FROM, IS TRUE, POSITION/SUBSTRING FROM/TRIM BOTH, EXTRACT, INTERVAL, bitwise ops, GLOB/SIMILAR TO, IFNULL, quoted aliases); fresh seeds | 16 cpu, 32G | 3:00:00 | duck v7_explore_v3 20000 21000 --queries 25 --instances 10 --workers 16 --gen v3 --certify $C7 | logs/pt7-duck-v3-61888101.out | submitted 11:43 PDT |
| 61888102 | pt7-pg-v3 | v7, PostgreSQL, generator v3 (after pt7-pg-v2) | 8 cpu, 16G | 3:00:00 | pg v7_explore_v3 20000 20240 --queries 25 --instances 4 --gen v3 --certify $C7 | logs/pt7-pg-v3-61888102.out | submitted 11:43 PDT |

proptest.py md5 7e44876a... adds --gen v3 (v1 and v2 generation verified unchanged: 5/5 seeds each regenerate the recorded SQL sequences). pt7-duck-final, pt7-duck-v2 and pt-pg-v2 started on md5 97d5e486 (identical generation for v1/v2).

### Superseded: runs against v7a (0353e3ee)

The lead replaced v7a by the final v7 (md5 1369ffcae12b93aec06735259c146814, same path) at ~11:50 PDT. Jobs 61888041, 61888042 (done), 61888043 (had started, cancelled), 61888044, 61888101, 61888102 loaded or would have loaded v7a:
cancelled at 11:51 PDT, and their outputs were moved to `$V/runs/obsdet/proptest/v7a_*` (not reported as v7 results). The one finished v7a run (DuckDB generator v2) had 0 cert_div, 8 cert_fail and 143 g2_header queries.

### Against the final v7 (md5 1369ffca..., `--certify $C7 --certify-md5 1369ffcae12b93aec06735259c146814`)

proptest.py md5 17f2e8eb... (the md5 is now taken of the exact bytes loaded; `--certify-md5` refuses other files; g2_header is also checked with LIMIT/OFFSET). proptest_repro.py md5 20e86780....

| job id | name | purpose | resources | walltime | args | log | status |
|---|---|---|---|---|---|---|---|
| 61888344 | pt7-duck-final | v7, DuckDB, generator v1 (same seeds/scale as pt-duck-final) | 16 cpu, 32G | 4:00:00 | duck v7_final 0 2000 --queries 25 --instances 10 --workers 16 | logs/pt7-duck-final-61888344.out | submitted 11:52 PDT |
| 61888345 | pt7-duck-v2 | v7, DuckDB, generator v2 (same seeds as pt-duck-v2) | 16 cpu, 32G | 3:00:00 | duck v7_explore_v2 10000 11000 ... --gen v2 | logs/pt7-duck-v2-61888345.out | submitted 11:52 PDT |
| 61888346 | pt7-duck-v3 | v7, DuckDB, generator v3 (fresh seeds) | 16 cpu, 32G | 3:00:00 | duck v7_explore_v3 20000 21000 ... --gen v3 | logs/pt7-duck-v3-61888346.out | submitted 11:52 PDT |
| 61888347 | pt7-pg-final | v7, PostgreSQL, generator v1 (same seeds/scale as pt-pg-final) | 8 cpu, 16G | 3:00:00 | pg v7_final 0 400 --queries 25 --instances 4 | logs/pt7-pg-final-61888347.out | submitted 11:52 PDT |
| 61888348 | pt7-pg-v2 | v7, PostgreSQL, generator v2 (after 61888347) | 8 cpu, 16G | 3:00:00 | pg v7_explore_v2 10000 10240 ... --gen v2 | logs/pt7-pg-v2-61888348.out | submitted 11:52 PDT |
| 61888349 | pt7-pg-v3 | v7, PostgreSQL, generator v3 (after 61888348) | 8 cpu, 16G | 3:00:00 | pg v7_explore_v3 20000 20240 ... --gen v3 | logs/pt7-pg-v3-61888349.out | submitted 11:52 PDT |
| 61888350 | pt7-repro | minimal repros on DuckDB + PG against v7 and v6 (after 61888349) | 4 cpu, 8G | 0:45:00 | --wrap proptest_repro.py ... --pg [--certify $C7] | logs/pt7-repro-61888350.out | submitted 11:52 PDT |

pt-pg-v2 (61887589, v6, generator v2) finished at 11:47 PDT.

### Generator v4 (literal typing: typed literal then ::, literals beyond DECIMAL(38)/HUGEINT, hex/underscore literals; also injected into SUM/AVG)

proptest.py md5 2229d0ff... (adds --gen v4 and root-cause labels N8/N9; v1-v3 generation unchanged). proptest_repro.py md5 1aeca8a8... (adds R8, R9).
Violations N8 (typed literal then ::) and N9 (literal beyond 38 digits) against the final v7 were found by targeted probes at 12:04 PDT and reported to the lead at 12:05 and 12:07 PDT.

| job id | name | purpose | resources | walltime | args | log | status |
|---|---|---|---|---|---|---|---|
| 61888634 | pt7-duck-v4 | v7, DuckDB, generator v4, fresh seeds | 16 cpu, 32G | 3:00:00 | duck v7_explore_v4 30000 31000 --queries 25 --instances 10 --workers 16 --gen v4 --certify $C7 --certify-md5 1369ffca... | logs/pt7-duck-v4-61888634.out | submitted 12:08 PDT |
| 61888635 | pt6-duck-v4 | v6, DuckDB, generator v4, same seeds (which certifier versions a class affects) | 16 cpu, 32G | 3:00:00 | duck v6_explore_v4 30000 31000 ... --gen v4 --certify code/obsdet/certify.py --certify-md5 7aa9c889 | logs/pt6-duck-v4-61888635.out | submitted 12:08 PDT |
| 61888636 | pt7-pg-v4 | v7, PostgreSQL, generator v4 (after pt7-repro) | 8 cpu, 16G | 3:00:00 | pg v7_explore_v4 30000 30240 ... --gen v4 | logs/pt7-pg-v4-61888636.out | submitted 12:08 PDT |

### Superseded: 1369ffca ("v7b") runs

At 12:13 PDT the lead designated `$V/code/obsdet_v7final/certify.py` (md5 5a2daa9e4634ec90689062338fa8b23d, "v7final") as the version of record.
Finished 1369ffca runs (DuckDB v1-final, v2, v3; PostgreSQL v1-final, v2) were kept and relabelled `v7b_*`. Cancelled at 12:13 PDT: 61888349 (pt7-pg-v3, had just started), 61888350 (pt7-repro), 61888634 (pt7-duck-v4), 61888636 (pt7-pg-v4), and 61888635 (pt6-duck-v4; its partial output is in `cancelled_v6_explore_v4_oldgen`, and v4 was then extended).
v7b results (for the record): DuckDB v1-final 50,000 queries, v2 25,000 and v3 25,000 queries, and PG v1-final 10,000 queries: 0 cert_div, 0 G2 bag/limit/header; cert_fail = N4 only (DuckDB 5 / 6 / 2 queries, PG 3).
N8 and N9 were found against 1369ffca by targeted probes.

### Against v7final (md5 5a2daa9e..., `--certify $V/code/obsdet_v7final/certify.py --certify-md5 5a2daa9e4634ec90689062338fa8b23d`); outputs `v7f_*`

proptest.py md5 460057f9... (v4 adds the ORDER BY binding forms unary +/- on ordinals/aliases/columns, parenthesised aliases/ordinals, case-flipped and quoted alias spellings, quoted upper-case aliases equal to input column names; v1-v3 generation verified unchanged).

| job id | name | purpose | resources | walltime | args | log | status |
|---|---|---|---|---|---|---|---|
| 61888724 | pt7f-duck-v1 | v7final, DuckDB, generator v1 (same seeds/scale as the v6 final) | 16 cpu, 32G | 3:00:00 | duck v7f_final 0 2000 --queries 25 --instances 10 --workers 16 --gen v1 | logs/pt7f-duck-v1-61888724.out | submitted 12:14 PDT |
| 61888725 | pt7f-duck-v2 | v7final, DuckDB, generator v2 | 16 cpu, 32G | 3:00:00 | duck v7f_explore_v2 10000 11000 ... --gen v2 | logs/pt7f-duck-v2-61888725.out | submitted 12:14 PDT |
| 61888726 | pt7f-duck-v3 | v7final, DuckDB, generator v3 | 16 cpu, 32G | 3:00:00 | duck v7f_explore_v3 20000 21000 ... --gen v3 | logs/pt7f-duck-v3-61888726.out | submitted 12:14 PDT |
| 61888727 | pt7f-duck-v4 | v7final, DuckDB, generator v4 | 16 cpu, 32G | 3:00:00 | duck v7f_explore_v4 30000 31000 ... --gen v4 | logs/pt7f-duck-v4-61888727.out | submitted 12:14 PDT |
| 61888728 | pt6-duck-v4 | v6, DuckDB, generator v4 (same seeds; which versions a class affects) | 16 cpu, 32G | 3:00:00 | duck v6_explore_v4 30000 31000 ... --gen v4 --certify code/obsdet/certify.py --certify-md5 7aa9c889 | logs/pt6-duck-v4-61888728.out | submitted 12:14 PDT |
| 61888729 | pt7f-pg-v1 | v7final, PostgreSQL, generator v1 (same seeds/scale as the v6 final) | 8 cpu, 16G | 3:00:00 | pg v7f_final 0 400 --queries 25 --instances 4 --gen v1 | logs/pt7f-pg-v1-61888729.out | submitted 12:14 PDT |
| 61888730 | pt7f-pg-v2 | v7final, PostgreSQL, generator v2 (after 61888729) | 8 cpu, 16G | 3:00:00 | pg v7f_explore_v2 10000 10240 ... --gen v2 | logs/pt7f-pg-v2-61888730.out | submitted 12:14 PDT |
| 61888731 | pt7f-pg-v3 | v7final, PostgreSQL, generator v3 (after 61888730) | 8 cpu, 16G | 3:00:00 | pg v7f_explore_v3 20000 20240 ... --gen v3 | logs/pt7f-pg-v3-61888731.out | submitted 12:14 PDT |
| 61888732 | pt7f-pg-v4 | v7final, PostgreSQL, generator v4 (after 61888731) | 8 cpu, 16G | 3:00:00 | pg v7f_explore_v4 30000 30240 ... --gen v4 | logs/pt7f-pg-v4-61888732.out | submitted 12:14 PDT |
| 61888733 | pt7f-repro | minimal repros (R1-R9) on DuckDB + PG against v7final and v6 (after 61888732) | 4 cpu, 8G | 0:45:00 | --wrap proptest_repro.py ... --pg [--certify v7final] | logs/pt7f-repro-61888733.out | submitted 12:14 PDT |

### 5a2daa9e runs completed (kept, relabelled `v7final-5a2daa9e_*`)

The lead replaced v7final by 66ead3df (stricter-only) at ~12:40 PDT. Every 5a2daa9e job had finished except pt7f-repro (61888733). That job refused to start because of the md5 guard: the file on disk was then 66ead3df.
5a2daa9e results: DuckDB generators v1/v2/v3/v4 (50,000 + 3 x 25,000 queries) and PostgreSQL v1/v2/v3/v4 (10,000 + 3 x 6,000 queries): 0 cert_div, 0 g2_bag, 0 g2_limit, 0 g2_header, 0 fail-closed leaks. cert_fail (N4 only): DuckDB 5/6/2/5 queries, PG 3/3/3/0.

### Against v7final 66ead3df (version of record; `--certify $V/code/obsdet_v7final/certify.py --certify-md5 66ead3dffadfab4b7c7111a0117075b2`); outputs `v7final-66ead3df_*`

proptest.py md5 098c2dcc... (adds --gen v5: BIGINT near 2^53, UBIGINT near 2^64, DECIMAL(38,0), DECIMAL(38,10) and DOUBLE-near-2^53 columns from separate random streams, and e-notation constant equalities; v1/v2/v4 generation verified unchanged). proptest_repro.py md5 3a4615c0... (adds R11, R12).

| job id | name | purpose | resources | walltime | args | log |
|---|---|---|---|---|---|---|
| 61889586-61889590 | pt7r-duck-v1..v5 | 66ead3df, DuckDB, generators v1 (seeds 0-2000), v2 (10000-11000), v3 (20000-21000), v4 (30000-31000), v5 (40000-41000); 25 queries x 10 instances x 8 executions | 16 cpu, 32G each | 3:00:00 | duck v7final-66ead3df_{final,explore_v2..v5} ... | logs/pt7r-duck-v*-<id>.out |
| 61889591 | pt6-duck-v5 | v6, DuckDB, generator v5 (classification) | 16 cpu, 32G | 3:00:00 | duck v6_explore_v5 40000 41000 ... --gen v5 --certify code/obsdet/certify.py | logs/pt6-duck-v5-61889591.out |
| 61889592-61889596 | pt7r-pg-v1..v5 | 66ead3df, PostgreSQL, generators v1 (0-400), v2 (10000-10240), v3 (20000-20240), v4 (30000-30240), v5 (40000-40240); chained, one server at a time | 8 cpu, 16G each | 3:00:00 | pg v7final-66ead3df_* ... | logs/pt7r-pg-v*-<id>.out |
| 61889597 | pt7r-repro | repro cases R1-R12 on DuckDB + PG against 66ead3df, 5a2daa9e, 1369ffca, 0353e3ee, v6 (after the PG chain) | 4 cpu, 8G | 1:00:00 | --wrap | logs/pt7r-repro-61889597.out |

All submitted 12:54 PDT.

### 66ead3df PostgreSQL jobs re-pointed; runs against 7626553a (final)

At ~13:05 PDT the lead replaced `code/obsdet_v7final/certify.py` by 7626553a (stricter-only). The pending 66ead3df PostgreSQL jobs 61889593-61889596 and the repro job 61889597 would have failed the md5 guard, so they were cancelled at 13:10 PDT and resubmitted against the saved copy `runs/obsdet/v7/certify_candidate2.py` (md5 66ead3df...). pt7r-pg-v1 (61889592), running since 12:55, had loaded 66ead3df.
proptest.py md5 ab424fa3... (adds --gen v6: TIMESTAMP / TIMESTAMP WITH TIME ZONE columns with values around the 2018 America/New_York DST changes, session TimeZone America/New_York on both engines; CHAR(3) / VARCHAR columns with trailing blanks; targeted ts = tz and ch = vc predicates and joins. DuckDB queries whose preview contains TIMESTAMPTZ cannot be fetched without pytz and are discarded and counted as `harness:pytz`. v1 and v5 generation verified unchanged). proptest_repro.py md5 024f7af0... (adds R13 DST, R14 CHAR/VARCHAR; PostgreSQL sessions use TimeZone America/New_York).

| job id | name | purpose | resources | walltime | args | log |
|---|---|---|---|---|---|---|
| 61890181-61890184 | pt7r-pg-v2..v5 | 66ead3df (copy candidate2), PostgreSQL, generators v2-v5 (chained after 61889592) | 8 cpu, 16G each | 3:00:00 | pg v7final-66ead3df_explore_v2..v5 ... --certify runs/obsdet/v7/certify_candidate2.py --certify-md5 66ead3df... | logs/pt7r-pg-v*-<id>.out |
| 61890185 | pt7z-pg-v1 | **7626553a**, PostgreSQL, generator v1 (seeds 0-400) | 8 cpu, 16G | 3:00:00 | pg v7final-7626553a_final 0 400 --queries 25 --instances 4 --gen v1 --certify code/obsdet_v7final/certify.py --certify-md5 7626553a... | logs/pt7z-pg-v1-61890185.out |
| 61890186 | pt7z-pg-v6 | **7626553a**, PostgreSQL, generator v6 (seeds 50000-50240) | 8 cpu, 16G | 3:00:00 | pg v7final-7626553a_explore_v6 50000 50240 ... --gen v6 | logs/pt7z-pg-v6-61890186.out |
| 61890187 | pt7z-duck-v1 | **7626553a**, DuckDB, generator v1 (seeds 0-2000) | 16 cpu, 32G | 3:00:00 | duck v7final-7626553a_final 0 2000 --queries 25 --instances 10 --workers 16 --gen v1 ... | logs/pt7z-duck-v1-61890187.out |
| 61890188 | pt7z-duck-v6 | **7626553a**, DuckDB, generator v6 (seeds 50000-51000) | 16 cpu, 32G | 3:00:00 | duck v7final-7626553a_explore_v6 50000 51000 ... --gen v6 | logs/pt7z-duck-v6-61890188.out |
| 61890189 | pt-repro-all | repro cases R1-R14 on DuckDB + PG against 7626553a, 66ead3df, 5a2daa9e, 1369ffca, 0353e3ee, v6 (after the PG chain) | 4 cpu, 8G | 1:30:00 | --wrap | logs/pt-repro-all-61890189.out |

All submitted 13:11 PDT.

13:36 PDT: pt7z-duck-v6 (61890188) crashed (generator bug: `* REPLACE (expr AS col)` asked `expr()` for the new TS class). Fixed: a class without expression kinds yields a leaf; v1/v4/v5 generation verified unchanged. DuckDB previews that fail only because the client lacks pytz are counted as `harness_pytz`, not cert_fail. Resubmitted as pt7z-duck-v6b (id in the next line). pt7z-duck-v1 (61890187, **7626553a**, G1) finished: 0 cert_div, 0 G2, 0 leaks, 5 cert_fail (N4).
| 61890649 | pt7z-duck-v6b | **7626553a**, DuckDB, generator v6 (seeds 50000-51000), rerun after the generator fix (proptest.py md5 15c57b1f...) | 16 cpu, 32G | 3:00:00 | duck v7final-7626553a_explore_v6 50000 51000 --queries 25 --instances 10 --workers 16 --gen v6 --certify code/obsdet_v7final/certify.py --certify-md5 7626553a... | logs/pt7z-duck-v6b-61890649.out |
13:57 PDT: pt7z-pg-v6 (61890186) crashed on its first schema: the default of `m.get('pgtype', PGTYPES[m['cls']])` is evaluated eagerly and fails for the TS class. Fixed (`m.get('pgtype') or ...`), proptest.py md5 028e6ee6.... pt7z-pg-v1 (61890185, **7626553a**, PG G1) finished: 0 cert_div, 0 G2, 3 cert_fail (N4). pt7z-duck-v6b (61890649, **7626553a**, DuckDB G6) finished: 0 cert_div, 0 G2, 0 leaks, 13 cert_fail (N4), 646 queries discarded as harness:pytz. pt-repro-all (61890189) finished: `repro_all/repro_<version>.json` for all six versions.

| job id | name | purpose | resources | walltime | args | log |
|---|---|---|---|---|---|---|
| 61894099 | pt7z-pg-v6b | **7626553a**, PostgreSQL, generator v6 (rerun after the fix) | 8 cpu, 16G | 3:00:00 | pg v7final-7626553a_explore_v6 50000 50240 --queries 25 --instances 4 --gen v6 --certify code/obsdet_v7final/certify.py --certify-md5 7626553a... | logs/pt7z-pg-v6b-61894099.out |
14:00 PDT: partial outputs of the cancelled runs were moved to `partial_cancelled/` subfolders and are excluded from all summaries: v7a_final (duck 1,100/2,000, pg 151/400 schemas), v7a_explore_v3 (910/1,000), v7b_explore_v3 pg (3/240), v7b_explore_v4 (490/1,000). Their meta md5 fields were written by an early version of `certifier_id()` that hashed the file at call time, not the loaded bytes, and are not reliable.

| job id | name | purpose | resources | walltime | log |
|---|---|---|---|---|---|
| 61894135 | pt-summaries | re-summarise all 19 complete run directories with the final classification code (after 61894099) | 2 cpu, 16G | 1:00:00 | logs/pt-summaries-61894135.out |
| 61894161 / 61894162 | pt7d-duck-v6 / pt7d-pg-v6 | power check: generator v6 against 66ead3df (copy candidate2) on DuckDB (seeds 50000-51000) and PostgreSQL (50000-50240, after 61894099); outputs `v7final-66ead3df_explore_v6` | 16 cpu 32G / 8 cpu 16G | 3:00:00 | logs/pt7d-*-<id>.out |

### Final status (14:25 PDT)

- pt7z-pg-v6b (61894099, **7626553a**, PG G6): 0 cert_div, 0 G2, 4 cert_fail (N4). pt-summaries (61894135): all 19 complete runs re-summarised with the final classification code.
- pt7d-duck-v6 / pt7d-pg-v6 (61894161 / 61894162, 66ead3df, G6 power check): 5 / 1 cert_div queries, all N12 (TIMESTAMP = TIMESTAMPTZ across the DST gap; CHAR = VARCHAR), versus 0 for 7626553a on the same seeds.
- **Runs against 7626553a (version of record):** 61890187 (DuckDB G1), 61890649 (DuckDB G6), 61890185 (PG G1), 61894099 (PG G6), plus the 7626553a part of 61890189 (repro cases). All clean except N4.
- Final code: proptest.py md5 4065b48d197345edfd82f4bd47cc894c, proptest_repro.py md5 024f7af015f47c0e07e9c466431beb58, proptest.sbatch md5 md5-withheld (identical copies in $V/code/obsdet/). $V/code/obsdet/certify.py (cluster) unchanged at 7aa9c889 (v6). The LOCAL experiments/obsdet/certify.py now has md5 7626553a (v7final): the lead replaced it; this work never modified any certify.py.
- No PostgreSQL server of this work is left running: every job stopped `proptest` on exit (trap + finally).
- Results: experiments/obsdet/results/final/proptest/PROPTEST.md.
