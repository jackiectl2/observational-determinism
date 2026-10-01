# PROPTEST — property-based soundness testing of the SQL certifier (E1d)

> **2026-09-25 17:45 PDT addendum.** The certifier of record is now 80705f63 (md5 80705f632bf861731a2084d2cf5c1306): 7626553a plus the rejection of schema- or catalog-qualified table names (`unknown-table`), found by the proof re-audit (`paper/PROOF_AUDIT.md`) and confirmed by jobs 61902063 and 61902354, and a docstring note. The generators name tables only by bare generated names and never emit a qualified name, so for every generated query 80705f63 returns what 7626553a returned, and the 7626553a results below hold for 80705f63 unchanged.

Date: 2026-09-25. Code: `experiments/obsdet/proptest.py` (generator, harness, summary, instance reduction),
`experiments/obsdet/proptest_repro.py` (hand-minimised repro cases), launcher `experiments/obsdet/proptest.sbatch`,
job log `experiments/obsdet/JOBS_PROPTEST.md`. Cluster outputs: `$V/runs/obsdet/proptest/`
(`$V` = `$PROJECT_ROOT`); summaries copied here.

## Certifier versions tested

| label | md5 | where | status |
|---|---|---|---|
| **v6** | 7aa9c889bb189b0740e83e258b83a7c4 | `$V/code/obsdet/certify.py` (frozen; was also `experiments/obsdet/certify.py` when this work started) | tested at full scale |
| v7a | 0353e3eeec5ef4da74220c9160b1d460 | `$V/runs/obsdet/v7/certify_v7a_0353e3ee.py` | superseded; repro cases + one DuckDB G2 run |
| v7b | 1369ffcae12b93aec06735259c146814 | `$V/runs/obsdet/v7/certify_v7_1369ffca.py` | superseded; repro cases + DuckDB G1-G3, PG G1-G2 |
| v7c | 5a2daa9e4634ec90689062338fa8b23d | `$V/runs/obsdet/v7/certify_candidate.py` | superseded; full scale G1-G4 on both engines |
| v7d | 66ead3dffadfab4b7c7111a0117075b2 | `$V/runs/obsdet/v7/certify_candidate2.py` | superseded (stricter-only successor below); full scale G1-G5 on both engines |
| **v7final** | 7626553a38a7b0dcf648b4d665c540bd | `$V/code/obsdet_v7final/certify.py` (the local `experiments/obsdet/certify.py` now also has this md5; it was replaced by the lead, not by this work) | **version of record**; G1 (full scale) and G6 on both engines + all repro cases |

Runs after 11:52 PDT loaded their certifier through `--certify <path> --certify-md5 <md5>`. The md5 is taken of
the exact bytes executed, a mismatch aborts the run (the guard stopped one queued job after a certifier file was replaced), and
each run's `*_meta.jsonl` records it.
The early v6 runs (G1 final and G2 exploration) predate the `--certify` option. They imported the frozen
`certify.py`, whose md5 was checked by hand at submission (`JOBS_PROPTEST.md`). The later v6 runs (G4, G5) used
`--certify ... --certify-md5 7aa9c889`.

## Method

**Schemas.** Each seed gives a schema with 3-5 tables, each with a declared key: INTEGER `id`, VARCHAR `code`,
DATE `d`, or a composite (INTEGER, INTEGER) / (INTEGER, VARCHAR) key. 20% of keyed tables get a second UNIQUE
VARCHAR key, and 30% of schemas get an extra keyless table. Tables have FK-like INTEGER columns referencing
earlier single-INTEGER-key tables (with duplicates, dangling values and NULLs), and 3-5 more columns. These are
INTEGER, DECIMAL(10,2), VARCHAR (small alphabet with case variants, `''`, trailing blanks, `'1'`/`'01'`), DATE,
DOUBLE (always 0.0 and -0.0; NaN in 10% of domains) and BOOLEAN, each nullable with probability 0.5 and drawn
from 2-5 values to force ties. Column names repeat across tables (`id`, `name`, `x`, ...), so unqualified
names, shadowing aliases and USING/NATURAL joins are meaningful.

**Instances.** Each table has 0-20 rows (0 is possible). Keys are unique and non-null in every instance: an
assert checks every declared key.

**Queries (generators G1-G6; CLI `--gen v1..v6`).** Each later generator extends the previous one. A later
generator only draws extra random numbers when it is enabled, and G1/G2/G4/G5 queries were verified to
regenerate byte-for-byte after each extension.
- **G1:** 1-3 FROM tables (repeated tables allowed), joined by
  - FK = key, non-key equality, theta, CROSS JOIN, or comma joins with WHERE conditions;
  - out of fragment: LEFT, USING, NATURAL.

  SELECT lists hold columns, immutable expressions (arithmetic, `/`, `%`, CASE, COALESCE, LOWER/UPPER,
  SUBSTRING, LEFT, TRIM, `||`, LENGTH, YEAR/MONTH, ABS, SIGN, ROUND, CAST between all classes incl.
  DOUBLE -> VARCHAR, TRY_CAST, date + int) and scalar subqueries (correlated/uncorrelated aggregates, key
  lookups, possibly multi-row). WHERE uses:
  - constants, IS [NOT] NULL, column equalities within and across types (incl. INT = DECIMAL, INT = DOUBLE,
    TEXT = INT), comparisons, BETWEEN, IN lists;
  - [NOT] IN / [NOT] EXISTS subqueries, scalar-subquery comparisons, OR.

  Queries are plain, grouped (GROUP BY columns or expressions incl. DOUBLE keys, by expression / ordinal /
  alias) or global aggregates. Aggregates are COUNT(*), COUNT, COUNT(DISTINCT), MIN/MAX over every class, and
  SUM/AVG over INT/DEC/DOUBLE, with aggregate wrappers (`+1`, CAST AS VARCHAR, `1/agg`, ROUND, COALESCE, CASE).
  Further constructs:
  - HAVING; DISTINCT;
  - ORDER BY ordinals, aliases (incl. aliases shadowing input columns, parenthesised), output expressions,
    non-output columns and expressions, grouped keys, aggregates, and ORDER BY ALL, each with ASC/DESC and
    NULLS FIRST/LAST;
  - LIMIT 0-10 and OFFSET.

  15% of queries carry an out-of-fragment construct: window function, derived table, set operation (UNION
  [ALL] / EXCEPT / INTERSECT), CTE, LEFT/USING/NATURAL join, `random()`, order-dependent aggregate
  (STRING_AGG, FIRST, ANY_VALUE, LIST, ARG_MAX), GROUP BY ALL, DISTINCT ON, LIMIT inside an IN subquery,
  HASH/MD5, or QUALIFY.
- **G2:** about 30 more allowlisted functions: GREATEST/LEAST, FLOOR/CEIL, NULLIF, `//`, STRPOS, DATE_DIFF,
  QUARTER/DAYOFWEEK, LN/LOG/LOG10/EXP/SQRT/POW, REPLACE, SPLIT_PART, CONCAT, CONCAT_WS, RIGHT, STRFTIME, SUBSTR,
  IF, `::`, DATE_TRUNC, LIKE/ILIKE, REGEXP_MATCHES, exponent literals (`1e-1`), and mixed-type
  CASE/COALESCE/GREATEST branches. It also adds:
  - aggregate FILTER clauses, EXISTS outputs;
  - star EXCLUDE/REPLACE;
  - ORDER BY an alias inside an expression, and scalar-subquery sort keys;
  - unqualified names inside subqueries;
  - DISTINCT with a non-output ORDER BY key (known defect K2);
  - more out-of-fragment kinds: COLLATE, percent LIMIT, USING SAMPLE, window inside a subquery, ROLLUP.
- **G3:** syntax whose sqlglot re-generation may differ: typed-literal casts (`DATE '..'::VARCHAR`,
  `TIMESTAMP '..'::DATE`), `^`/`**`, simple CASE, IS [NOT] DISTINCT FROM, IS TRUE, POSITION(.. IN ..),
  SUBSTRING(.. FROM .. FOR ..), TRIM(BOTH ..), EXTRACT, INTERVAL arithmetic, DATE_ADD, bitwise operators,
  GLOB, SIMILAR TO, IFNULL, `.5` literals, quoted aliases (`"Mixed Case"`, `"c 1"`, `"C2"`).
- **G4:** literals whose DuckDB type differs from sqlglot's parse: `DECIMAL '0.1'::DOUBLE`,
  `BIGINT '3'::REAL`, literals beyond DECIMAL(38) or HUGEINT, hex and underscore literals. These are also
  injected into SUM/AVG arguments. G4 adds ORDER BY binding forms: unary +/- on ordinals, aliases and columns;
  parenthesised ordinals and aliases; case-flipped or quoted alias spellings; and quoted upper-case aliases
  equal to input column names (DuckDB matches identifiers case-insensitively).
- **G5:** columns at precision limits, drawn from separate random streams: BIGINT near 2^53, UBIGINT near
  2^64, DECIMAL(38,0), DECIMAL(38,10) and DOUBLE near 2^53. G5 adds e-notation constants
  (`big = 9007199254740992e0`, `d38a = 1.2345678901234568e27`) and cross-type numeric equalities.
- **G6:** TIMESTAMP and TIMESTAMP WITH TIME ZONE columns with values around the 2018 America/New_York DST
  changes (02:30 and 03:30 on 2018-03-11; 01:30 on 2018-11-04). Both engines run with session TimeZone
  America/New_York. G6 also adds CHAR(3) and VARCHAR columns with trailing blanks, and targeted
  `ts = tz` / `ch = vc` predicates and joins.

  Harness limitation: the DuckDB Python client needs `pytz` to fetch TIMESTAMPTZ values, and it could not be
  installed (workspace rule). DuckDB G6 queries whose preview contains a TIMESTAMPTZ value were therefore
  discarded (`harness:pytz`, counted). TIMESTAMPTZ columns are still used in their predicates and joins.
  PostgreSQL has no such limitation.

Queries that DuckDB rejects when binding on the first instance are discarded and counted; the rejection rate
is about 2% for G1. Queries with runtime errors are kept.

**Executions.**
- DuckDB 1.5.5, 8 executions per instance: the instance is loaded in shuffled insertion order (3 shuffles x
  threads 1/4), plus two more shuffles with `preserve_insertion_order=false` (threads 4) and
  `debug_force_external=true` (threads 1).
- PostgreSQL 16.2, 6 configurations per instance: a private server (`pg_setup.start("proptest")`, data under
  `$V/runs/obsdet/pg/proptest/`, socket `/tmp/obsdet_e3pg_proptest`, stopped on exit), 3 heap orders
  (shuffled INSERT, then PRIMARY KEY/UNIQUE and ANALYZE) x serial / parallel-enabled (as `replay_pg.py`:
  `max_parallel_workers_per_gather 4`, parallel costs and minimum scan sizes zeroed). Queries are transpiled
  with `pg_cost.to_pg` and certified in the postgres dialect.

**Observation.** The canonical observation is the header, the exact row count and the first 20 rows rendered
with `tool.canon` (signed zero rendered as 0.0), hashed per execution.

**Checks** (per query and instance):
- `cert_div` — the certified query (DET: the raw query; NARROW/ALL: `rewritten`) gives more than one
  observation over its successful executions. **Soundness violation.**
- `cert_fail` — in some execution the raw query succeeds and the certified query fails.
- `g2_bag` — without LIMIT/OFFSET, the rewrite's result bag differs from the raw query's bag in the same
  execution.
- `g2_limit` — with LIMIT/OFFSET, the rewrite's rows are not a sub-bag of the raw query's unlimited result, or
  its count is not min(L, max(n − O, 0)).
- `g2_header` — the rewrite's header differs from the raw query's (checked with and without LIMIT since
  v7c; before, only without).
- Fail-closed leaks: a query carrying an out-of-fragment construct, or a spec-excluded shape (float SUM/AVG,
  GROUP BY float), that gets a non-UNSUPPORTED verdict. Tags follow DuckDB typing, so in PostgreSQL some
  "leaks" are exact there: `1e0` is numeric, integer `/` is integer division, and `to_pg` emits `ROUND(x::DECIMAL, n)`.
- Certifier crashes. None occurred in any run.
- **Power:** whether the RAW query's observation diverges.

**Minimisation.**
- `proptest.py reduce` shrinks each distinct `cert_div` instance by greedy row deletion, re-checking the
  divergence over 24 shuffled loads. All 67 distinct v6 G1 violations reduced to 2-6 rows.
- `proptest_repro.py` holds hand-minimised cases R1-R14. They run on both engines against all six certifier
  versions (`repro_all/`).

## Headline

- **v7final (7626553a, version of record): no soundness violation found.**
  - DuckDB: 75,000 generated queries (G1 50,000 at the same seeds and scale as the v6 final run, plus G6 25,000), 6.0M raw
    statement executions.
  - PostgreSQL: 16,000 queries (G1 10,000, G6 6,000), 384k raw statement executions.
  - Results: 0 certified previews that differ across executions (`cert_div`), 0 G2 bag, 0 G2 limit, 0 header changes, 0
    fail-closed leaks, 0 certifier crashes. The only failures are N4 (value-quoting runtime errors, outside the
    formal contract).
  - v7final also passes every hand-minimised repro case R1-R14 on both engines, except R4b (N4, which fails on
    every version).
- The same checks at the same scale found **12 violation classes in earlier versions: 10 new (N1-N3, N6-N12) and
  the 2 known ones (K1, K2)**, plus N4 (outside the contract) and N5 (completeness only).
  - Found by the random runs first: N1, N2, N3, N6, N7 and K1, K2.
  - Found first by targeted probes, then by the random generators: N8, N9.
  - Also found, independently, by the lead's code or proof review: N10, N11, N12. The random runs report them as
    well (against v6 for N10/N11, against v7d for N12).
- **Power.** The raw (uncertified) preview diverged across equivalent executions for 36-41% of NARROW and 41-46%
  of ALL queries on DuckDB, and 25-29% / 27-36% on PostgreSQL. So the executions do produce different tie orders.
  - For v6 the harness observed 67 (G1) to 225 (G5) diverging certified queries per DuckDB run.
  - On PostgreSQL, 75% of certified G1 queries got a parallel plan (Gather with workers) in the parallel-enabled
    configuration: 4,296 of 5,749 for v7final.
  - For N12 specifically, the random G6 run found 5 (DuckDB) + 1 (PostgreSQL) diverging queries against v7d
    (66ead3df) and 0 against v7final on the same seeds.

## Violation classes and the certifier versions they affect

Affected versions follow from the repro matrix below (every case run against all six versions on both engines) and from the random runs.

| class | what goes wrong | root cause | affected | found by | distinct queries in random runs (cert_div unless noted) | repro |
|---|---|---|---|---|---|---|
| **N1** | Duplicate output names: two outputs named `id`, an alias equal to another output's name, names equal up to case (`"NAME"` vs `name`), or `SELECT *` over a join. `ORDER BY 1` / `ORDER BY name` is bound to the wrong output, so DET or a too-weak tie-break is certified. | v6 `certify.py` lines 422-440: `qualify()` rewrites `ORDER BY 1` into `ORDER BY <name>`, and `alias_to_pos` keeps the last output with that name | v6 | G1 (first smoke-scale run) | v6: DuckDB G1 66, G2 28, G4 42, G5 33; PG G1 6, G2 1 | R1a, R1b, R1c |
| **N2** | USING and NATURAL joins (outside F) are certified | the fragment check (lines 307-310) runs on `qualify()`'s output, where USING is already rewritten to ON; NATURAL is `args["method"]`, not `kind` | v6 | G1 fail-closed check | v6 DuckDB G1: 452/499 USING and 433/499 NATURAL queries certified (they diverged only via N1) | R1c |
| **N3** | The NARROW/ALL rewrite renames output columns: the header differs from the raw query's | the rewrite is sqlglot's re-generation of the whole statement, and DuckDB names unaliased expressions by their text (`a.x IS NOT NULL` becomes `NOT a.x IS NULL`) | v6, v7a | G1 (`g2_header`) | v6 DuckDB G1 57, G2 139; v7a G2 143 (g2_header) | R3 |
| N4 | The certified query fails where the raw one succeeds: value-quoting runtime errors (CAST of `'a'`/inf/NaN, DECIMAL(38) overflow, a scalar subquery returning more than one row) on rows the raw LIMIT/OFFSET plan never evaluates | the appended sort evaluates the projection on all rows | **all versions incl. v7final**; outside the formal contract (runtime errors that quote data values) | G1 (`cert_fail`) | 0-13 per run (tables below) | R4b |
| N5 | completeness only: sqlglot `qualify()` raises an AssertionError when `ORDER BY <ordinal>` points at an unaliased scalar-subquery output, and the query becomes UNSUPPORTED (fails closed) | sqlglot | all | G1 | v6 DuckDB G1 365 of 38,607 in-fragment queries; v7final 362 (PG 88) | - |
| **N6** | An exponent literal (`1e-1`) is typed DECIMAL, but DuckDB types it DOUBLE, so a float SUM/AVG is certified | `infer()` types every number literal DECIMAL/INT | v6 | G2 | v6 G2 3, G4 2, G5 2 | R5 |
| **N7** | A typed literal followed by `::` (`DATE '2026-01-10'::VARCHAR`) is parsed by sqlglot as `CAST(CAST('2026-01-10' AS TEXT) AS DATE)`. The re-generated rewrite then changes values (`< '2026-1-5'` TRUE becomes FALSE), types (TIMESTAMP becomes DATE and back), or bindability (`LENGTH(DATE)`). | sqlglot DuckDB parser + rewrite by re-generation | v6, v7a | G2 (`cert_fail`, binder errors), confirmed by probe | v6 G2 5 cert_fail records; v6 G4: 310 g2_bag, 234 g2_limit, 90 cert_fail records | R7a, R7b, R7c |
| **N8** | The same mis-parse types `DECIMAL '0.1'::DOUBLE` as DECIMAL, so a float SUM/AVG is certified | `infer()` reads the mis-parsed AST (v7b's splice fixed only the rewrite) | v6, v7a, v7b | targeted probe against v7b, then G4 | v6 G4 3, G5 14 | R8 |
| **N9** | A number literal with more than 38 digits, or beyond HUGEINT, is DOUBLE in DuckDB but typed exact, so a float SUM/AVG is certified | `infer()` | v6, v7a, v7b | targeted probe against v7b, then G4 | v6 G4 21, G5 19 | R9 |
| **N10** | Unary plus in ORDER BY (`ORDER BY +1`, `+alias`): sqlglot drops the `+`, so the certifier binds an ordinal or alias while DuckDB sorts by the constant or column expression | sqlglot | v6, v7a, v7b | G4 (vs v6); also the lead's code review | v6 G4 83, G5 81 | R10 |
| **N11** | A lossy numeric constant: `big = 9007199254740992e0` matches both 2^53 and 2^53+1 (the BIGINT is cast to DOUBLE); likewise UBIGINT near 2^64 and DECIMAL(38,0)/(38,10) vs `1.2345678901234568e27`. The constant nevertheless "pins" the column. | constant FD recorded for inexact literals | v6, v7a, v7b, v7c | G5 (vs v6); also the lead's proof review | v6 G5 26 | R11, R12 |
| **N12** | TIMESTAMP = TIMESTAMPTZ compares through the session time zone (2018-03-11 02:30 and 03:30 in New York are one instant: DuckDB and PostgreSQL). CHAR(3) = VARCHAR ignores trailing blanks (PostgreSQL). The equality FD is unsound in both cases. | temporal/text equality FDs between non-identical declared types | v6, v7a, v7b, v7c, v7d | the lead's proof review; G6 finds it against v7d | v7d G6: DuckDB 5, PG 1 (v7final: 0 on the same seeds) | R13 (DuckDB), R14 (PG) |
| K1 (known) | SUM/AVG over DECIMAL/DECIMAL division (DOUBLE in DuckDB) | `infer()` Div | v6 | G1 | v6 G1 1 | R2 |
| K2 (known) | SELECT DISTINCT with a non-output ORDER BY key (DuckDB keeps an arbitrary key per row; PostgreSQL rejects it) | fragment check | v6 | G2 | v6 G2 46, G4 47, G5 48 | R6 |

Fixes, as observed on the repro cases:
- v7a fixed N1, N2, N6, K1, K2.
- v7b fixed N3 and N7 (the tie-break is spliced into the statement as written).
- v7c fixed N8, N9, N10.
- v7d fixed N11.
- v7final fixed N12.

N4 is present in every version, and N5 costs about 1% of in-fragment queries.

## Scale actually run, verdicts and power (every complete run; runs against **v7final = 7626553a** are marked bold)

Queries = generated queries that DuckDB binds on the first instance (all later checks use these); "drawn / rejected" counts the binder/parser rejections and the `harness:pytz` discards (G6). Raw statement executions = queries x instances x executions. "Raw preview diverged" = share of NARROW/ALL queries whose RAW query showed more than one observation on at least one instance (the test's power).

| certifier | engine | gen | queries | drawn / rejected | inst x exec | raw statement executions | DET / NARROW / ALL / UNSUP | raw preview diverged: NARROW, ALL (queries) |
|---|---|---|---|---|---|---|---|---|
| v6 | DuckDB | G1 | 50,000 | 50,984 / BinderException 984 | 10 x 8 | 4,000,000 | 18,798 / 15,882 / 4,072 / 11,248 | 40.5%, 45.6% |
| v6 | PostgreSQL | G1 | 10,000 | 10,207 / BinderException 207 | 4 x 6 | 240,000 | 2,854 / 2,491 / 737 / 3,918 | 26.9%, 33.8% |
| v6 | DuckDB | G2 | 25,000 | 25,973 / BinderException 963, ParserException 10 | 10 x 8 | 2,000,000 | 8,815 / 8,242 / 2,302 / 5,641 | 40.2%, 45.2% |
| v6 | PostgreSQL | G2 | 6,000 | 6,240 / BinderException 238, ParserException 2 | 4 x 6 | 143,976 | 1,583 / 1,566 / 504 / 2,346 | 27.1%, 30.8% |
| v6 | DuckDB | G4 | 25,000 | 27,877 / BinderException 2667, ParserException 210 | 10 x 8 | 2,000,000 | 9,102 / 8,076 / 2,246 / 5,576 | 40.6%, 46.1% |
| v6 | DuckDB | G5 | 25,000 | 27,831 / ParserException 199, BinderException 2632 | 10 x 8 | 2,000,000 | 8,666 / 8,299 / 2,448 / 5,587 | 39.2%, 44.3% |
| v7a | DuckDB | G2 | 25,000 | 25,973 / BinderException 963, ParserException 10 | 10 x 8 | 2,000,000 | 7,646 / 8,289 / 2,153 / 6,912 | 37.7%, 45.2% |
| v7b | DuckDB | G1 | 50,000 | 50,984 / BinderException 984 | 10 x 8 | 4,000,000 | 16,663 / 16,350 / 4,219 / 12,768 | 38.0%, 44.5% |
| v7b | PostgreSQL | G1 | 10,000 | 10,207 / BinderException 207 | 4 x 6 | 240,000 | 2,490 / 2,571 / 751 / 4,188 | 25.6%, 33.2% |
| v7b | DuckDB | G2 | 25,000 | 25,973 / BinderException 963, ParserException 10 | 10 x 8 | 2,000,000 | 7,646 / 8,208 / 2,234 / 6,912 | 37.9%, 44.2% |
| v7b | PostgreSQL | G2 | 6,000 | 6,240 / BinderException 238, ParserException 2 | 4 x 6 | 143,976 | 1,371 / 1,561 / 495 / 2,572 | 26.7%, 31.1% |
| v7b | DuckDB | G3 | 25,000 | 25,993 / BinderException 973, ParserException 20 | 10 x 8 | 2,000,000 | 7,606 / 8,177 / 2,302 / 6,915 | 38.8%, 43.3% |
| v7c | DuckDB | G1 | 50,000 | 50,984 / BinderException 984 | 10 x 8 | 4,000,000 | 16,554 / 16,112 / 4,182 / 13,152 | 38.2%, 44.7% |
| v7c | PostgreSQL | G1 | 10,000 | 10,207 / BinderException 207 | 4 x 6 | 240,000 | 2,472 / 2,531 / 746 / 4,251 | 25.9%, 33.2% |
| v7c | DuckDB | G2 | 25,000 | 25,973 / BinderException 963, ParserException 10 | 10 x 8 | 2,000,000 | 7,439 / 7,638 / 2,149 / 7,774 | 38.9%, 45.2% |
| v7c | PostgreSQL | G2 | 6,000 | 6,240 / BinderException 238, ParserException 2 | 4 x 6 | 143,976 | 1,333 / 1,432 / 469 / 2,765 | 28.5%, 32.6% |
| v7c | DuckDB | G3 | 25,000 | 25,993 / BinderException 973, ParserException 20 | 10 x 8 | 2,000,000 | 7,212 / 7,432 / 2,191 / 8,165 | 39.5%, 44.2% |
| v7c | PostgreSQL | G3 | 6,000 | 6,227 / BinderException 218, ParserException 9 | 4 x 6 | 143,976 | 1,257 / 1,494 / 415 / 2,833 | 26.6%, 31.6% |
| v7c | DuckDB | G4 | 25,000 | 27,877 / BinderException 2667, ParserException 210 | 10 x 8 | 2,000,000 | 6,215 / 6,386 / 2,277 / 10,122 | 38.7%, 43.0% |
| v7c | PostgreSQL | G4 | 6,000 | 6,675 / BinderException 623, ParserException 52 | 4 x 6 | 144,000 | 1,208 / 1,378 / 493 / 2,921 | 27.4%, 35.7% |
| v7d | DuckDB | G1 | 50,000 | 50,984 / BinderException 984 | 10 x 8 | 4,000,000 | 16,543 / 16,117 / 4,188 / 13,152 | 38.2%, 44.5% |
| v7d | PostgreSQL | G1 | 10,000 | 10,207 / BinderException 207 | 4 x 6 | 240,000 | 2,467 / 2,536 / 746 / 4,251 | 25.8%, 33.2% |
| v7d | DuckDB | G2 | 25,000 | 25,973 / BinderException 963, ParserException 10 | 10 x 8 | 2,000,000 | 7,435 / 7,642 / 2,149 / 7,774 | 38.9%, 45.1% |
| v7d | PostgreSQL | G2 | 6,000 | 6,240 / BinderException 238, ParserException 2 | 4 x 6 | 143,976 | 1,333 / 1,432 / 469 / 2,765 | 28.5%, 32.6% |
| v7d | DuckDB | G3 | 25,000 | 25,993 / BinderException 973, ParserException 20 | 10 x 8 | 2,000,000 | 7,205 / 7,434 / 2,196 / 8,165 | 39.4%, 43.9% |
| v7d | PostgreSQL | G3 | 6,000 | 6,227 / BinderException 218, ParserException 9 | 4 x 6 | 143,976 | 1,256 / 1,494 / 416 / 2,833 | 26.6%, 31.5% |
| v7d | DuckDB | G4 | 25,000 | 27,877 / BinderException 2667, ParserException 210 | 10 x 8 | 2,000,000 | 6,213 / 6,383 / 2,282 / 10,122 | 38.7%, 43.0% |
| v7d | PostgreSQL | G4 | 6,000 | 6,675 / BinderException 623, ParserException 52 | 4 x 6 | 144,000 | 1,206 / 1,376 / 497 / 2,921 | 27.4%, 35.4% |
| v7d | DuckDB | G5 | 25,000 | 27,831 / ParserException 199, BinderException 2632 | 10 x 8 | 2,000,000 | 5,772 / 6,607 / 2,492 / 10,129 | 36.4%, 40.7% |
| v7d | PostgreSQL | G5 | 6,000 | 6,651 / BinderException 595, ParserException 56 | 4 x 6 | 143,976 | 1,173 / 1,500 / 544 / 2,782 | 26.1%, 26.8% |
| v7d | DuckDB | G6 | 25,000 | 28,753 / BinderException 2900, harness:pytz 646, ParserException 207 | 10 x 8 | 2,000,000 | 5,768 / 6,677 / 2,611 / 9,944 | 39.3%, 43.5% |
| v7d | PostgreSQL | G6 | 6,000 | 6,915 / BinderException 723, harness:pytz 152, ParserException 40 | 4 x 6 | 143,976 | 1,220 / 1,445 / 559 / 2,775 | 26.1%, 31.5% |
| **v7final** | DuckDB | G1 | 50,000 | 50,984 / BinderException 984 | 10 x 8 | 4,000,000 | 16,543 / 16,117 / 4,188 / 13,152 | 38.2%, 44.6% |
| **v7final** | PostgreSQL | G1 | 10,000 | 10,207 / BinderException 207 | 4 x 6 | 240,000 | 2,467 / 2,536 / 746 / 4,251 | 25.8%, 33.2% |
| **v7final** | DuckDB | G6 | 25,000 | 28,753 / BinderException 2900, harness:pytz 646, ParserException 207 | 10 x 8 | 2,000,000 | 5,748 / 6,680 / 2,628 / 9,944 | 39.1%, 43.7% |
| **v7final** | PostgreSQL | G6 | 6,000 | 6,915 / BinderException 723, harness:pytz 152, ParserException 40 | 4 x 6 | 143,976 | 1,212 / 1,448 / 564 / 2,775 | 26.0%, 31.4% |

## Violations per run

cert_div root causes are counted over distinct SQL texts; the classification is heuristic (`proptest.py root_cause`) and was checked by hand on samples of every class. cert_fail causes are counted over violation records (up to 5 per schema and kind). **Fail-closed leak** tags use DuckDB typing: on PostgreSQL, `agg:sum/avg:dbl` queries are exact there (PostgreSQL types `1e0` as numeric, integer `/` is integer division, and `to_pg` emits `ROUND(x::DECIMAL, n)`), and none of them diverged. On DuckDB every version from v7a on has 0 leaks.

| certifier | engine | gen | cert_div queries (pairs) | cert_div root causes (distinct SQL) | cert_fail queries: causes | g2_bag | g2_limit | g2_header | fail-closed leaks |
|---|---|---|---|---|---|---|---|---|---|
| v6 | DuckDB | G1 | 67 (259) | K1 1, N1 66 | 5: N4 13 (records) | 0 | 0 | 57 | oof:using 452, oof:natural 433, agg:avg:dbl 8, agg:sum:dbl 16 |
| v6 | PostgreSQL | G1 | 6 (11) | N1 6 | 3: N4 3 (records) | 0 | 0 | 0 | oof:using 80, oof:natural 70, agg:avg:dbl 4, agg:sum:dbl 2 |
| v6 | DuckDB | G2 | 78 (229) | K2 46, N1 28, N6 3 | 8: N4 17, N7 5 (records) | 0 | 0 | 139 | oof:using 194, agg:sum:dbl 56, oof:natural 183, agg:avg:dbl 26 |
| v6 | PostgreSQL | G2 | 1 (1) | N1 1 | 3: N4 5 (records) | 0 | 0 | 0 | oof:using 38, oof:natural 31, agg:sum:dbl 15, agg:avg:dbl 5 |
| v6 | DuckDB | G4 | 201 (853) | K2 47, N1 42, N10 83, N6 2, N8 3, N9 21 | 31: N4 49, N7 90 (records) | 65 | 63 | 655 | agg:avg:dbl 277, agg:sum:dbl 492, oof:natural 181, oof:using 184 |
| v6 | DuckDB | G5 | 225 (822) | K2 48, N1 33, N10 81, N11 26, N6 2, N8 14, N9 19 | 51: N4 125, N7 71 (records) | 69 | 57 | 731 | agg:sum:dbl 529, agg:avg:dbl 248, oof:natural 174, oof:using 162 |
| v7a | DuckDB | G2 | 0 (0) | - | 8: N4 17, N7 5 (records) | 0 | 0 | 143 | 0 |
| v7b | DuckDB | G1 | 0 (0) | - | 5: N4 13 (records) | 0 | 0 | 0 | 0 |
| v7b | PostgreSQL | G1 | 0 (0) | - | 3: N4 3 (records) | 0 | 0 | 0 | agg:avg:dbl 4, agg:sum:dbl 2 |
| v7b | DuckDB | G2 | 0 (0) | - | 6: N4 12 (records) | 0 | 0 | 0 | 0 |
| v7b | PostgreSQL | G2 | 0 (0) | - | 3: N4 5 (records) | 0 | 0 | 0 | agg:sum:dbl 15, agg:avg:dbl 4 |
| v7b | DuckDB | G3 | 0 (0) | - | 2: N4 4 (records) | 0 | 0 | 0 | 0 |
| v7c | DuckDB | G1 | 0 (0) | - | 5: N4 13 (records) | 0 | 0 | 0 | 0 |
| v7c | PostgreSQL | G1 | 0 (0) | - | 3: N4 3 (records) | 0 | 0 | 0 | agg:avg:dbl 4, agg:sum:dbl 2 |
| v7c | DuckDB | G2 | 0 (0) | - | 6: N4 12 (records) | 0 | 0 | 0 | 0 |
| v7c | PostgreSQL | G2 | 0 (0) | - | 3: N4 5 (records) | 0 | 0 | 0 | agg:sum:dbl 13, agg:avg:dbl 4 |
| v7c | DuckDB | G3 | 0 (0) | - | 2: N4 4 (records) | 0 | 0 | 0 | 0 |
| v7c | PostgreSQL | G3 | 0 (0) | - | 3: N4 3 (records) | 0 | 0 | 0 | agg:avg:dbl 5, agg:sum:dbl 4 |
| v7c | DuckDB | G4 | 0 (0) | - | 5: N4 10 (records) | 0 | 0 | 0 | 0 |
| v7c | PostgreSQL | G4 | 0 (0) | - | 0: - | 0 | 0 | 0 | agg:sum:dbl 77, agg:avg:dbl 49 |
| v7d | DuckDB | G1 | 0 (0) | - | 5: N4 13 (records) | 0 | 0 | 0 | 0 |
| v7d | PostgreSQL | G1 | 0 (0) | - | 3: N4 3 (records) | 0 | 0 | 0 | agg:avg:dbl 4, agg:sum:dbl 2 |
| v7d | DuckDB | G2 | 0 (0) | - | 6: N4 12 (records) | 0 | 0 | 0 | 0 |
| v7d | PostgreSQL | G2 | 0 (0) | - | 3: N4 5 (records) | 0 | 0 | 0 | agg:sum:dbl 13, agg:avg:dbl 4 |
| v7d | DuckDB | G3 | 0 (0) | - | 2: N4 4 (records) | 0 | 0 | 0 | 0 |
| v7d | PostgreSQL | G3 | 0 (0) | - | 3: N4 3 (records) | 0 | 0 | 0 | agg:avg:dbl 5, agg:sum:dbl 4 |
| v7d | DuckDB | G4 | 0 (0) | - | 5: N4 10 (records) | 0 | 0 | 0 | 0 |
| v7d | PostgreSQL | G4 | 0 (0) | - | 0: - | 0 | 0 | 0 | agg:sum:dbl 77, agg:avg:dbl 49 |
| v7d | DuckDB | G5 | 0 (0) | - | 5: N4 11 (records) | 0 | 0 | 0 | 0 |
| v7d | PostgreSQL | G5 | 0 (0) | - | 1: N4 1 (records) | 0 | 0 | 0 | agg:avg:dbl 38, agg:sum:dbl 92 |
| v7d | DuckDB | G6 | 5 (13) | N12 5 | 13: N4 47 (records) | 0 | 0 | 0 | 0 |
| v7d | PostgreSQL | G6 | 1 (2) | N12 1 | 4: N4 4 (records) | 0 | 0 | 0 | agg:sum:dbl 68, agg:avg:dbl 40 |
| **v7final** | DuckDB | G1 | 0 (0) | - | 5: N4 13 (records) | 0 | 0 | 0 | 0 |
| **v7final** | PostgreSQL | G1 | 0 (0) | - | 3: N4 3 (records) | 0 | 0 | 0 | agg:avg:dbl 4, agg:sum:dbl 2 |
| **v7final** | DuckDB | G6 | 0 (0) | - | 13: N4 47 (records) | 0 | 0 | 0 | 0 |
| **v7final** | PostgreSQL | G6 | 0 (0) | - | 4: N4 4 (records) | 0 | 0 | 0 | agg:sum:dbl 68, agg:avg:dbl 40 |

Totals: v7final DuckDB 75,000 queries / 6,000,000 raw executions, PostgreSQL 16,000 / 383,976; v7d 175,000 / 14.0M and 40,000 / 959,904; v7c 125,000 / 10.0M and 28,000 / 671,952; v7b 100,000 / 8.0M and 16,000 / 383,976; v7a 25,000 / 2.0M (DuckDB only); v6 125,000 / 10.0M and 16,000 / 383,976.

## Minimal repro cases on all six versions

`proptest_repro.py` runs each case with the certificate of each version. DuckDB: 24 executions (shuffled insertion, threads 1/4). PostgreSQL: 3 heap orders x serial/parallel, TimeZone America/New_York. A cell shows the verdict and, in bold, what went wrong for the certified query: several distinct previews (soundness violation), failure where the raw query succeeds, a header renamed, or rows that differ from the raw query without LIMIT (G2). "ok" = one preview, same header and bag as raw. Files: `repro_all/repro_<version>.json`.

| case (duckdb) | v6 7aa9c889 | v7a 0353e3ee | v7b 1369ffca | v7c 5a2daa9e | v7d 66ead3df | v7final 7626553a |
|---|---|---|---|---|---|---|
| R1a | DET: **2 previews** | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R1b | NARROW: **6 previews** | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R1c | NARROW: **2 previews** | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R1d | NARROW ok | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R10 | DET: **6 previews** | DET: **6 previews** | DET: **6 previews** | UNSUP | UNSUP | UNSUP |
| R2 | DET: **2 previews** | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R5 | DET: **2 previews** | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R8 | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | UNSUP | UNSUP | UNSUP |
| R9 | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | UNSUP | UNSUP | UNSUP |
| R11 | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | ALL ok | ALL ok |
| R12 | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | NARROW ok | NARROW ok |
| R13 | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | ALL ok |
| R14 | DET ok | DET ok | DET ok | DET ok | DET ok | NARROW ok |
| R6 | ALL: **2 previews** | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R3 | NARROW: **header renamed** | NARROW: **header renamed** | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R7a | NARROW: **rows differ from raw** | NARROW: **rows differ from raw** | NARROW ok | UNSUP | UNSUP | UNSUP |
| R7b | NARROW: **fails 0/24 (raw 24)** | NARROW: **fails 0/24 (raw 24)** | NARROW ok | UNSUP | UNSUP | UNSUP |
| R7c | NARROW: **rows differ from raw** | NARROW: **rows differ from raw** | NARROW ok | UNSUP | UNSUP | UNSUP |
| R4b | ALL: **fails 0/24 (raw 15)** | ALL: **fails 0/24 (raw 15)** | ALL: **fails 0/24 (raw 15)** | ALL: **fails 0/24 (raw 15)** | ALL: **fails 0/24 (raw 15)** | ALL: **fails 0/24 (raw 15)** |

| case (postgres) | v6 7aa9c889 | v7a 0353e3ee | v7b 1369ffca | v7c 5a2daa9e | v7d 66ead3df | v7final 7626553a |
|---|---|---|---|---|---|---|
| R1a | DET: **2 previews** | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R1b | NARROW: **6 previews** | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R1c | NARROW: **2 previews** | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R1d | NARROW: raw fails | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R10 | DET ok | DET ok | DET ok | DET ok | DET ok | DET ok |
| R2 | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R5 | DET ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R8 | DET ok | DET ok | DET ok | DET ok | DET ok | DET ok |
| R9 | DET ok | DET ok | DET ok | DET ok | DET ok | DET ok |
| R11 | DET ok | DET ok | DET ok | DET ok | DET ok | DET ok |
| R12 | DET ok | DET ok | DET ok | DET ok | DET ok | DET ok |
| R13 | DET ok | DET ok | DET ok | DET ok | DET ok | ALL ok |
| R14 | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | DET: **2 previews** | NARROW ok |
| R6 | ALL: raw fails | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R3 | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok | NARROW ok |
| R7a | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R7b | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R7c | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP | UNSUP |
| R4b | ALL: **fails 0/6 (raw 2)** | ALL: **fails 0/6 (raw 2)** | ALL: **fails 0/6 (raw 2)** | ALL: **fails 0/6 (raw 2)** | ALL: **fails 0/6 (raw 2)** | ALL: **fails 0/6 (raw 2)** |

PostgreSQL reads differ from DuckDB because the PostgreSQL pipeline executes sqlglot's transpiled SQL (`pg_cost.to_pg`), so the certifier analyses exactly what runs. As a result N6/N8/N9/N10/N11 do not arise there: `1e0` and long literals are numeric, and the unary `+` is dropped in the executed SQL too. N3/N7 do not arise because PostgreSQL names unaliased columns `?column?` and typed text-to-temporal casts are UNSUPPORTED.

**R13 on PostgreSQL.** v6-v7d certify it DET although it is unsound; the preview happened to be stable in the 6 configurations of this 2-row instance. The random G6 run is the scale check (v7d: 1 PostgreSQL divergence, a CHAR = VARCHAR join). v7final returns ALL.

**R1d** (names equal up to case) did not diverge on its minimal instance under v6. The random runs found 5 such v6 divergences, counted under N1. v7a onwards reject it (ambiguous ORDER BY name).

### The cases

| case | what | schema (key) | rows | query (DuckDB syntax) |
|---|---|---|---|---|
| R1a | duplicate output name: ORDER BY 1 is resolved to the other output named g (DET claimed) | t(id INTEGER, g VARCHAR) key ['id'] | t: (1, 'a'), (2, 'a'), (3, 'b') | `SELECT t.g, t.id AS g FROM t ORDER BY 1` |
| R1b | duplicate output name from two aliases: ORDER BY 1 resolved to b.id, tie-break a.id | t(id INTEGER) key ['id'] | t: (1), (2), (3) | `SELECT a.id, b.id FROM t a, t b ORDER BY 1` |
| R1c | star over a USING join (spec: UNSUPPORTED) expands to two outputs named id | t(id INTEGER, x INTEGER) key ['id']; u(id INTEGER, x INTEGER) key ['id'] | t: (1, 1), (2, 1); u: (1, 1), (2, 1) | `SELECT * FROM t a JOIN u b USING (x) ORDER BY 1` |
| R1d | output names equal up to case ("NAME" vs name): ORDER BY name bound to the other output | t(id INTEGER, name VARCHAR, x INTEGER) key ['id'] | t: (1, 'a', 1), (2, 'b', 1), (3, 'c', 2) | `SELECT t.x AS "NAME", t.name FROM t ORDER BY name` |
| R10 | unary plus in ORDER BY: sqlglot drops it, so +1 is taken as ordinal 1; DuckDB sorts by the constant | t(id INTEGER, g VARCHAR) key ['id'] | t: (1, 'b'), (2, 'a'), (3, 'c') | `SELECT t.g FROM t ORDER BY +1` |
| R2 | SUM over DECIMAL / DECIMAL: typed DECIMAL by the certifier, DOUBLE in DuckDB (DET claimed) | t(id INTEGER, g INTEGER, a DECIMAL(10,2), b DECIMAL(10,2)) key ['id'] | t: (1, 1, '1.00', '10.00'), (2, 1, '2.00', '10.00'), (3, 1, '3.00', '10.00') | `SELECT t.g, SUM(t.a / t.b) FROM t GROUP BY t.g ORDER BY t.g` |
| R5 | SUM over a scientific-notation literal: 1e-1 typed DECIMAL by the certifier, DOUBLE in DuckDB | t(id INTEGER, g INTEGER, x INTEGER) key ['id'] | t: (1, 1, 1), (2, 1, 2), (3, 1, 3) | `SELECT t.g, SUM(t.x * 1e-1) FROM t GROUP BY t.g ORDER BY t.g` |
| R8 | typed literal then :: (DECIMAL '0.1'::DOUBLE): sqlglot parses DECIMAL('0.1'::DOUBLE), DuckDB DOUBLE | t(id INTEGER, x INTEGER) key ['id'] | t: (1, 1), (2, 2), (3, 3) | `SELECT SUM(t.x * DECIMAL '0.1'::DOUBLE) FROM t` |
| R9 | literal with more than 38 digits: DOUBLE in DuckDB, typed exact by the certifier | t(id INTEGER, x INTEGER) key ['id'] | t: (1, 1), (2, 2), (3, 3) | `SELECT SUM(t.x * 0.1000000000000000000000000000000000000001) FROM t` |
| R11 | BIGINT = e-notation literal compares in DOUBLE (lossy): the constant does not pin the column | t(id INTEGER, big BIGINT) key ['id'] | t: (1, 9007199254740992), (2, 9007199254740993), (3, 7) | `SELECT t.big FROM t WHERE t.big = 9007199254740992e0 LIMIT 1` |
| R12 | same, grouped: two groups pass the lossy constant filter | t(id INTEGER, big BIGINT) key ['id'] | t: (1, 9007199254740992), (2, 9007199254740993), (3, 7) | `SELECT t.big, COUNT(*) FROM t WHERE t.big = 9007199254740992e0 GROUP BY t.big` |
| R13 | TIMESTAMP = TIMESTAMPTZ through the session time zone: 02:30 and 03:30 on 2018-03-11 (New York) are one instant | t(id INTEGER, ts TIMESTAMP) key ['id']; u(id INTEGER, tz TIMESTAMP WITH TIME ZONE) key ['id'] | t: (1, '2018-03-11 02:30:00'), (2, '2018-03-11 03:30:00'); u: (1, '2018-03-11 07:30:00+00') | `SELECT t.ts FROM t JOIN u ON t.ts = u.tz ORDER BY u.tz` |
| R14 | CHAR(3) = VARCHAR ignores trailing blanks (PostgreSQL): 'a' and 'a ' both match | t(id INTEGER, ch CHAR(3)) key ['id']; u(id INTEGER, vc VARCHAR) key ['id'] | t: (1, 'a'); u: (1, 'a'), (2, 'a ') | `SELECT u.vc FROM t JOIN u ON t.ch = u.vc ORDER BY t.ch` |
| R6 | (known defect 2) SELECT DISTINCT with a non-output ORDER BY key | r(id INTEGER, name VARCHAR) key ['id']; s(id INTEGER, r_id INTEGER, rank INTEGER) key ['id'] | r: (1, 'a'), (2, 'b'); s: (1, 1, 5), (2, 1, 3), (3, 2, 4) | `SELECT DISTINCT r.name FROM r JOIN s ON s.r_id = r.id ORDER BY s.rank LIMIT 1` |
| R3 | header renamed by the regenerated rewrite (bag unchanged; not a G2 violation) | t(id INTEGER, x INTEGER) key ['id'] | t: (1, None), (2, 5) | `SELECT a.x IS NOT NULL, a.x FROM t a` |
| R7a | typed literal + cast (DATE 'x'::VARCHAR) re-parsed as DATE(x::VARCHAR): rewrite changes the result | t(id INTEGER, g INTEGER) key ['id'] | t: (1, 1), (2, 1) | `SELECT t.g, DATE '2026-01-10'::VARCHAR < '2026-1-5' AS c FROM t` |
| R7b | same parse: the rewrite no longer binds (LENGTH(DATE)) | t(id INTEGER, g INTEGER) key ['id'] | t: (1, 1), (2, 1) | `SELECT t.g, LENGTH(DATE '2026-01-10'::VARCHAR) AS c FROM t` |
| R7c | same parse: TIMESTAMP 'x'::DATE becomes CAST(CAST(x AS DATE) AS TIMESTAMP) (rendering changes) | t(id INTEGER, g INTEGER) key ['id'] | t: (1, 1), (2, 1) | `SELECT t.g, TIMESTAMP '2026-01-10 10:00:00'::DATE AS c FROM t` |
| R4b | certified execution fails where the raw query succeeds (LIMIT stops before the bad row) | t(id INTEGER, s VARCHAR) key ['id'] | t: (1, '7'), (2, 'x') | `SELECT CAST(t.s AS INTEGER) FROM t WHERE t.id = 1 OR t.s = 'x' LIMIT 1` |

Reduced instances from the random runs: `repro_all/v6_G1_duck_reduced_instances.json`. All 67 distinct v6 G1 DuckDB violations (66 N1, 1 K1) reproduce, reduced to 2-6 rows by greedy row deletion; each record holds the schema, the minimal instance, the query and the certificate. The full violation records (schema + instance + two differing observations per `cert_div`) are in `runs/<run>/*_violations.jsonl`. For the two largest runs they are in `*_violations_extract.jsonl` (cert_div, cert_fail and g2 kinds only).

## Other findings and limitations

- **N4 remains in v7final.** On DuckDB (G1) 5 queries: CAST of `'a'`, `'A'`, `'b'`, inf, -inf or NaN to INTEGER; on PostgreSQL 3: invalid input syntax, and a subquery returning more than one row. The raw query succeeds only in executions whose LIMIT stops before the offending row: R4b's raw query succeeds in 15 of 24 DuckDB executions, and its certified query in 0 of 24.

  These are runtime errors that quote data values, which the contract excludes (METHOD_FORMAL: "runtime errors whose messages quote data values ... are outside the contract and reported separately"). The asymmetry is still visible to a user of the tool.
- **N5 / completeness.** 362 of 38,607 in-fragment G1 DuckDB queries (0.9%) are UNSUPPORTED because of the sqlglot AssertionError; 88 of 7,687 on PostgreSQL. Other v7final UNSUPPORTED reasons among in-fragment queries are by design:
  - order-by-alias-in-expression (506);
  - inexact-min-max-in-expression (392);
  - distinct-order-by-non-output (373);
  - PostgreSQL text-to-temporal-cast (1,326).
- **Harness limitations.**
  - (i) The DuckDB Python client cannot fetch TIMESTAMPTZ values without `pytz`, which cannot be installed under the workspace rules. 646 DuckDB G6 queries (2.2% of those drawn) were discarded for this reason. TIMESTAMPTZ columns still appear in their predicates and joins, so R13/N12 remain covered on DuckDB.
  - (ii) With tables of at most 20 rows, DuckDB's intra-query parallelism rarely engages. Its variation comes from the shuffled insertion orders plus `preserve_insertion_order=false` and `debug_force_external`. PostgreSQL's zero-cost parallel plans do engage.
  - (iii) Generated schemas have no collations, views or tables wider than 11 columns; keyless tables get duplicate rows only by chance.
  - (iv) The random generators missed N8 and N9 until G4 added their exact shapes. A clean run shows the absence of violations only for the shapes the generators produce; see the coverage table.

## Files

- `experiments/obsdet/proptest.py` — generators G1-G6, harness, summary, `reduce`; `experiments/obsdet/proptest.sbatch`; `experiments/obsdet/proptest_repro.py` — repro cases R1-R14. Final md5s are listed in `JOBS_PROPTEST.md`.
- `experiments/obsdet/JOBS_PROPTEST.md` — every job: purpose, resources, walltime, id, log, and the certifier md5.
- `experiments/obsdet/results/final/proptest/runs/<run>/` — per run: `duck_summary.json` / `pg_summary.json` (scale, verdicts, power, violations, root causes, coverage, leaks), `summary_print.txt`, `*_meta.jsonl` (per schema: attempts, rejections, seconds, certifier md5), and violation records.
  - Local `v6_final` and `v6_explore_v2` are cluster `final` and `explore_v2`.
  - `v7final-5a2daa9e_*` = v7c, `v7final-66ead3df_*` = v7d, `v7final-7626553a_*` = v7final.
- `experiments/obsdet/results/final/proptest/repro_all/` — repro results for all six versions, and the reduced v6 instances.
- Cluster: `$V/runs/obsdet/proptest/`: all per-query records (`*_queries.jsonl`, one line per query with tags, verdict, counters) and logs; partial or cancelled runs are in `*/partial_cancelled/` and `cancelled_*`.

Reproduce one run, e.g. v7final G1 on DuckDB:

    sbatch --cpus-per-task=16 --mem=32G --time=3:00:00 proptest.sbatch duck <out> 0 2000 --queries 25 --instances 10 --workers 16 --gen v1 --certify $V/code/obsdet_v7final/certify.py --certify-md5 7626553a38a7b0dcf648b4d665c540bd

## Appendix: generator coverage (DuckDB; queries per construct tag)

The first block of columns is G1 against v7final (50,000 queries): verdict counts and the number of queries whose raw preview diverged. The remaining columns are query counts for G2-G5 (runs against v7d, same generator) and G6 (against v7final). Tags: `expr:<class>:<kind>` expressions; `agg:*` aggregates; `where:*`, `join:*`, `group:*`, `having:*`, `order:*`, `out:*`, `alias:*`, `subq:*` clauses; `oof:*` out-of-fragment constructs (must be UNSUPPORTED); `limit`/`offset`; `ref:unqualified*` unqualified names.

| construct (tag) | G1 (v7final): queries | DET | NARROW | ALL | UNSUP | raw diverged | G2: queries | G3: queries | G4: queries | G5: queries | G6 (v7final): queries |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `agg:arg_float_literal` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 875 | 894 | 785 |
| `agg:arg_has_division` | 304 | 0 | 0 | 0 | 304 | 37 | 132 | 126 | 99 | 110 | 117 |
| `agg:avg` | 3,941 | 1271 | 965 | 101 | 1604 | 434 | 1,970 | 1,952 | 1,973 | 1,836 | 1,812 |
| `agg:avg:dbl` | 847 | 0 | 0 | 0 | 847 | 95 | 399 | 397 | 656 | 601 | 592 |
| `agg:avg:dec` | 1,599 | 662 | 479 | 44 | 414 | 166 | 797 | 799 | 694 | 662 | 622 |
| `agg:avg:int` | 1,640 | 636 | 506 | 59 | 439 | 185 | 841 | 809 | 684 | 633 | 643 |
| `agg:count` | 3,874 | 1550 | 1170 | 158 | 996 | 482 | 2,036 | 2,003 | 1,968 | 1,911 | 1,885 |
| `agg:count:bool` | 704 | 303 | 198 | 34 | 169 | 93 | 360 | 328 | 340 | 375 | 353 |
| `agg:count:date` | 684 | 275 | 212 | 30 | 167 | 86 | 357 | 326 | 337 | 331 | 338 |
| `agg:count:dbl` | 678 | 253 | 223 | 21 | 181 | 95 | 347 | 348 | 376 | 297 | 341 |
| `agg:count:dec` | 631 | 253 | 197 | 23 | 158 | 72 | 334 | 354 | 328 | 342 | 304 |
| `agg:count:int` | 678 | 272 | 201 | 29 | 176 | 74 | 360 | 370 | 330 | 316 | 324 |
| `agg:count:text` | 662 | 276 | 179 | 25 | 182 | 77 | 352 | 355 | 331 | 325 | 295 |
| `agg:count_distinct` | 3,918 | 1553 | 1142 | 156 | 1067 | 560 | 2,032 | 1,925 | 1,884 | 1,874 | 1,963 |
| `agg:count_distinct:bool` | 673 | 275 | 188 | 22 | 188 | 92 | 348 | 328 | 331 | 299 | 337 |
| `agg:count_distinct:date` | 680 | 281 | 193 | 23 | 183 | 104 | 373 | 331 | 314 | 340 | 359 |
| `agg:count_distinct:dbl` | 629 | 257 | 181 | 26 | 165 | 92 | 343 | 316 | 335 | 346 | 329 |
| `agg:count_distinct:dec` | 707 | 260 | 216 | 31 | 200 | 104 | 349 | 344 | 329 | 340 | 329 |
| `agg:count_distinct:int` | 665 | 269 | 193 | 30 | 173 | 87 | 361 | 333 | 326 | 308 | 329 |
| `agg:count_distinct:text` | 727 | 298 | 212 | 25 | 192 | 102 | 368 | 345 | 318 | 318 | 352 |
| `agg:count_star` | 3,979 | 1592 | 1208 | 165 | 1014 | 480 | 2,042 | 1,932 | 1,960 | 1,872 | 1,879 |
| `agg:filter` | 0 | 0 | 0 | 0 | 0 | 0 | 1,654 | 1,663 | 1,540 | 1,496 | 1,560 |
| `agg:max` | 7,520 | 2846 | 2222 | 253 | 2199 | 872 | 3,881 | 3,930 | 3,603 | 3,622 | 3,543 |
| `agg:max:bool` | 1,343 | 533 | 402 | 54 | 354 | 148 | 732 | 715 | 662 | 692 | 654 |
| `agg:max:date` | 1,365 | 489 | 413 | 45 | 418 | 150 | 682 | 746 | 664 | 652 | 648 |
| `agg:max:dbl` | 1,326 | 442 | 354 | 43 | 487 | 158 | 679 | 690 | 668 | 607 | 657 |
| `agg:max:dec` | 1,366 | 527 | 412 | 35 | 392 | 159 | 740 | 708 | 633 | 657 | 628 |
| `agg:max:int` | 1,383 | 547 | 422 | 60 | 354 | 153 | 664 | 718 | 596 | 643 | 631 |
| `agg:max:text` | 1,363 | 559 | 395 | 33 | 376 | 159 | 698 | 692 | 648 | 659 | 593 |
| `agg:min` | 7,552 | 2817 | 2223 | 257 | 2255 | 926 | 3,860 | 3,823 | 3,700 | 3,469 | 3,610 |
| `agg:min:bool` | 1,384 | 535 | 416 | 48 | 385 | 160 | 705 | 758 | 678 | 609 | 648 |
| `agg:min:date` | 1,356 | 515 | 367 | 45 | 429 | 173 | 735 | 689 | 642 | 615 | 618 |
| `agg:min:dbl` | 1,327 | 463 | 350 | 42 | 472 | 174 | 675 | 655 | 664 | 629 | 662 |
| `agg:min:dec` | 1,368 | 528 | 416 | 52 | 372 | 143 | 660 | 662 | 650 | 646 | 638 |
| `agg:min:int` | 1,338 | 513 | 405 | 47 | 373 | 147 | 703 | 706 | 668 | 602 | 669 |
| `agg:min:text` | 1,422 | 547 | 434 | 33 | 408 | 179 | 687 | 695 | 693 | 628 | 654 |
| `agg:sum` | 7,505 | 2454 | 1919 | 201 | 2931 | 838 | 3,892 | 3,745 | 3,600 | 3,546 | 3,488 |
| `agg:sum:dbl` | 1,555 | 0 | 0 | 0 | 1555 | 182 | 850 | 834 | 1,223 | 1,248 | 1,160 |
| `agg:sum:dec` | 3,280 | 1295 | 1008 | 115 | 862 | 350 | 1,635 | 1,584 | 1,268 | 1,294 | 1,277 |
| `agg:sum:int` | 3,214 | 1275 | 997 | 94 | 848 | 343 | 1,652 | 1,554 | 1,342 | 1,241 | 1,274 |
| `agg:wrap:bool` | 489 | 238 | 118 | 12 | 121 | 34 | 281 | 259 | 243 | 247 | 252 |
| `agg:wrap:case` | 1,029 | 429 | 248 | 23 | 329 | 90 | 503 | 470 | 534 | 482 | 483 |
| `agg:wrap:cast_text` | 1,773 | 703 | 405 | 38 | 627 | 154 | 885 | 862 | 859 | 822 | 839 |
| `agg:wrap:coalesce` | 1,772 | 720 | 395 | 36 | 621 | 157 | 887 | 857 | 841 | 834 | 883 |
| `agg:wrap:date` | 532 | 188 | 114 | 11 | 219 | 41 | 242 | 249 | 242 | 217 | 260 |
| `agg:wrap:dbl` | 1,510 | 304 | 190 | 13 | 1003 | 151 | 758 | 727 | 846 | 792 | 852 |
| `agg:wrap:dec` | 1,157 | 528 | 279 | 30 | 320 | 75 | 592 | 521 | 457 | 477 | 473 |
| `agg:wrap:int` | 3,266 | 1471 | 840 | 99 | 856 | 322 | 1,710 | 1,531 | 1,578 | 1,569 | 1,499 |
| `agg:wrap:plus` | 1,022 | 395 | 222 | 17 | 388 | 86 | 523 | 442 | 465 | 471 | 484 |
| `agg:wrap:recip` | 973 | 378 | 210 | 30 | 355 | 111 | 536 | 505 | 455 | 471 | 479 |
| `agg:wrap:round` | 999 | 380 | 225 | 31 | 363 | 90 | 512 | 463 | 507 | 486 | 440 |
| `agg:wrap:text` | 530 | 221 | 145 | 8 | 156 | 56 | 235 | 282 | 252 | 244 | 245 |
| `alias:fresh` | 18,429 | 5530 | 7124 | 1147 | 4628 | 4366 | 9,398 | 9,353 | 9,215 | 9,328 | 9,304 |
| `alias:shadow` | 12,723 | 3592 | 4658 | 758 | 3715 | 3035 | 6,253 | 6,068 | 6,227 | 6,283 | 6,254 |
| `distinct` | 6,510 | 2057 | 1943 | 744 | 1766 | 1662 | 3,370 | 3,287 | 3,220 | 3,279 | 3,204 |
| `expr:bool:andor` | 1,015 | 354 | 383 | 81 | 197 | 228 | 324 | 181 | 169 | 152 | 154 |
| `expr:bool:between` | 0 | 0 | 0 | 0 | 0 | 0 | 285 | 182 | 139 | 155 | 186 |
| `expr:bool:cmp` | 2,054 | 658 | 843 | 159 | 394 | 455 | 585 | 337 | 330 | 349 | 350 |
| `expr:bool:distinct_from` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 164 | 149 | 188 | 171 |
| `expr:bool:glob` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 166 | 175 | 165 | 153 |
| `expr:bool:in_list` | 0 | 0 | 0 | 0 | 0 | 0 | 291 | 173 | 159 | 176 | 164 |
| `expr:bool:is_true` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 179 | 184 | 170 | 161 |
| `expr:bool:isnull` | 1,085 | 335 | 427 | 90 | 233 | 249 | 284 | 179 | 157 | 184 | 165 |
| `expr:bool:like` | 0 | 0 | 0 | 0 | 0 | 0 | 258 | 192 | 177 | 158 | 147 |
| `expr:bool:not` | 1,013 | 310 | 393 | 79 | 231 | 240 | 275 | 173 | 178 | 205 | 161 |
| `expr:bool:not_prec` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 180 | 175 | 160 | 154 |
| `expr:bool:regexp` | 0 | 0 | 0 | 0 | 0 | 0 | 280 | 199 | 177 | 171 | 162 |
| `expr:bool:similar` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 168 | 190 | 184 | 182 |
| `expr:date:add` | 1,676 | 497 | 652 | 88 | 439 | 356 | 676 | 410 | 361 | 362 | 364 |
| `expr:date:case` | 1,663 | 491 | 689 | 122 | 361 | 376 | 667 | 366 | 327 | 356 | 337 |
| `expr:date:coalesce` | 1,683 | 552 | 644 | 111 | 376 | 388 | 653 | 393 | 328 | 347 | 330 |
| `expr:date:date_add` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 358 | 348 | 366 | 374 |
| `expr:date:date_trunc` | 0 | 0 | 0 | 0 | 0 | 0 | 626 | 344 | 392 | 368 | 349 |
| `expr:date:interval` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 357 | 357 | 346 | 354 |
| `expr:date:typed_cast` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 384 | 337 | 366 | 344 |
| `expr:dbl:abs` | 793 | 194 | 237 | 39 | 323 | 156 | 219 | 140 | 154 | 128 | 140 |
| `expr:dbl:arith` | 770 | 159 | 273 | 50 | 288 | 162 | 215 | 185 | 140 | 130 | 134 |
| `expr:dbl:case` | 757 | 190 | 241 | 59 | 267 | 175 | 200 | 177 | 141 | 139 | 150 |
| `expr:dbl:cast` | 792 | 187 | 262 | 36 | 307 | 151 | 212 | 141 | 150 | 158 | 147 |
| `expr:dbl:coalesce` | 770 | 198 | 230 | 49 | 293 | 157 | 225 | 154 | 136 | 139 | 143 |
| `expr:dbl:div` | 766 | 184 | 238 | 48 | 296 | 166 | 229 | 169 | 141 | 138 | 165 |
| `expr:dbl:float_lit` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 307 | 265 | 297 |
| `expr:dbl:ln` | 0 | 0 | 0 | 0 | 0 | 0 | 197 | 148 | 133 | 154 | 163 |
| `expr:dbl:log2arg` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 166 | 147 | 131 | 143 |
| `expr:dbl:mixed` | 0 | 0 | 0 | 0 | 0 | 0 | 417 | 356 | 301 | 240 | 234 |
| `expr:dbl:pow` | 0 | 0 | 0 | 0 | 0 | 0 | 223 | 172 | 140 | 153 | 136 |
| `expr:dbl:pow_op` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 340 | 287 | 287 | 273 |
| `expr:dbl:recip` | 746 | 150 | 263 | 52 | 281 | 179 | 221 | 196 | 137 | 156 | 130 |
| `expr:dbl:round` | 774 | 199 | 239 | 40 | 296 | 168 | 222 | 179 | 128 | 142 | 140 |
| `expr:dbl:sci` | 0 | 0 | 0 | 0 | 0 | 0 | 401 | 311 | 284 | 274 | 273 |
| `expr:dbl:sqrt` | 0 | 0 | 0 | 0 | 0 | 0 | 224 | 161 | 140 | 136 | 155 |
| `expr:dec:abs` | 1,060 | 386 | 372 | 60 | 242 | 226 | 428 | 335 | 321 | 257 | 280 |
| `expr:dec:arith` | 1,078 | 357 | 394 | 59 | 268 | 226 | 398 | 314 | 274 | 269 | 262 |
| `expr:dec:case` | 1,103 | 374 | 399 | 67 | 263 | 209 | 386 | 294 | 277 | 287 | 278 |
| `expr:dec:cast` | 1,070 | 360 | 406 | 61 | 243 | 221 | 405 | 302 | 274 | 297 | 280 |
| `expr:dec:coalesce` | 1,086 | 389 | 384 | 36 | 277 | 213 | 416 | 289 | 307 | 302 | 254 |
| `expr:dec:floor` | 0 | 0 | 0 | 0 | 0 | 0 | 404 | 300 | 271 | 269 | 293 |
| `expr:dec:greatest` | 0 | 0 | 0 | 0 | 0 | 0 | 397 | 284 | 316 | 276 | 286 |
| `expr:dec:mod_dec` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 304 | 292 | 278 | 291 |
| `expr:dec:mul` | 1,071 | 329 | 407 | 75 | 260 | 217 | 394 | 293 | 277 | 296 | 281 |
| `expr:dec:neg_cast` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 301 | 279 | 264 | 294 |
| `expr:dec:nullif` | 0 | 0 | 0 | 0 | 0 | 0 | 418 | 306 | 305 | 296 | 273 |
| `expr:dec:round` | 1,091 | 389 | 388 | 52 | 262 | 207 | 407 | 318 | 302 | 262 | 283 |
| `expr:dec:round0` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 280 | 278 | 299 | 274 |
| `expr:dec:typed_cast_exact` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 283 | 289 | 253 |
| `expr:int:abs` | 609 | 212 | 230 | 36 | 131 | 113 | 239 | 190 | 170 | 156 | 161 |
| `expr:int:arith` | 1,239 | 414 | 444 | 75 | 306 | 227 | 502 | 400 | 337 | 341 | 341 |
| `expr:int:bitop` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 172 | 143 | 173 | 163 |
| `expr:int:case` | 627 | 183 | 242 | 52 | 150 | 125 | 220 | 162 | 164 | 174 | 149 |
| `expr:int:cast` | 1,271 | 436 | 466 | 83 | 286 | 265 | 420 | 352 | 351 | 315 | 321 |
| `expr:int:cast_text` | 634 | 223 | 229 | 46 | 136 | 84 | 218 | 176 | 167 | 174 | 132 |
| `expr:int:coalesce` | 679 | 207 | 253 | 37 | 182 | 138 | 234 | 174 | 152 | 147 | 164 |
| `expr:int:datediff` | 0 | 0 | 0 | 0 | 0 | 0 | 228 | 161 | 188 | 148 | 159 |
| `expr:int:extract` | 0 | 0 | 0 | 0 | 0 | 0 | 216 | 191 | 180 | 160 | 145 |
| `expr:int:extract_from` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 179 | 168 | 148 | 181 |
| `expr:int:floor` | 0 | 0 | 0 | 0 | 0 | 0 | 187 | 177 | 154 | 155 | 171 |
| `expr:int:greatest` | 0 | 0 | 0 | 0 | 0 | 0 | 226 | 185 | 137 | 143 | 174 |
| `expr:int:hex_lit` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 7 | 9 |
| `expr:int:intdiv` | 0 | 0 | 0 | 0 | 0 | 0 | 227 | 186 | 172 | 136 | 192 |
| `expr:int:length` | 640 | 205 | 242 | 42 | 151 | 128 | 236 | 182 | 156 | 168 | 143 |
| `expr:int:mod` | 630 | 221 | 224 | 44 | 141 | 135 | 229 | 148 | 168 | 140 | 168 |
| `expr:int:position` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 167 | 168 | 163 | 182 |
| `expr:int:round1` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 151 | 175 | 153 | 165 |
| `expr:int:sign` | 656 | 208 | 260 | 28 | 160 | 108 | 225 | 145 | 129 | 176 | 152 |
| `expr:int:simple_case` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 182 | 158 | 173 | 155 |
| `expr:int:strpos` | 0 | 0 | 0 | 0 | 0 | 0 | 210 | 174 | 156 | 165 | 159 |
| `expr:int:underscore_lit` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 156 | 147 | 171 |
| `expr:int:year` | 611 | 218 | 217 | 33 | 143 | 124 | 233 | 162 | 156 | 149 | 159 |
| `expr:text:case` | 624 | 193 | 267 | 34 | 130 | 146 | 148 | 119 | 118 | 122 | 116 |
| `expr:text:cast` | 655 | 191 | 267 | 43 | 154 | 151 | 157 | 135 | 116 | 116 | 107 |
| `expr:text:cast_from_bool` | 125 | 38 | 55 | 6 | 26 | 25 | 31 | 30 | 20 | 19 | 19 |
| `expr:text:cast_from_date` | 120 | 32 | 46 | 8 | 34 | 27 | 37 | 21 | 25 | 25 | 28 |
| `expr:text:cast_from_dbl` | 150 | 37 | 71 | 10 | 32 | 44 | 31 | 21 | 23 | 16 | 21 |
| `expr:text:cast_from_dec` | 134 | 42 | 43 | 11 | 38 | 29 | 24 | 34 | 29 | 25 | 18 |
| `expr:text:cast_from_int` | 130 | 45 | 53 | 8 | 24 | 26 | 34 | 30 | 19 | 32 | 21 |
| `expr:text:coalesce` | 683 | 226 | 290 | 30 | 137 | 171 | 151 | 139 | 116 | 93 | 101 |
| `expr:text:concat` | 645 | 172 | 245 | 54 | 174 | 149 | 125 | 145 | 124 | 123 | 97 |
| `expr:text:concat_fn` | 0 | 0 | 0 | 0 | 0 | 0 | 140 | 124 | 108 | 112 | 116 |
| `expr:text:concat_ws` | 0 | 0 | 0 | 0 | 0 | 0 | 171 | 119 | 99 | 97 | 96 |
| `expr:text:dcast` | 0 | 0 | 0 | 0 | 0 | 0 | 133 | 117 | 110 | 97 | 106 |
| `expr:text:if` | 0 | 0 | 0 | 0 | 0 | 0 | 159 | 116 | 117 | 113 | 118 |
| `expr:text:ifnull` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130 | 140 | 99 | 108 |
| `expr:text:left` | 657 | 199 | 276 | 36 | 146 | 162 | 189 | 108 | 109 | 125 | 100 |
| `expr:text:lower` | 640 | 213 | 241 | 40 | 146 | 137 | 133 | 113 | 113 | 114 | 101 |
| `expr:text:replace` | 0 | 0 | 0 | 0 | 0 | 0 | 160 | 109 | 128 | 93 | 125 |
| `expr:text:right` | 0 | 0 | 0 | 0 | 0 | 0 | 158 | 117 | 120 | 114 | 114 |
| `expr:text:simple_case` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 103 | 105 | 117 | 127 |
| `expr:text:split_part` | 0 | 0 | 0 | 0 | 0 | 0 | 186 | 106 | 122 | 109 | 131 |
| `expr:text:strftime` | 0 | 0 | 0 | 0 | 0 | 0 | 171 | 123 | 111 | 109 | 127 |
| `expr:text:substr2` | 0 | 0 | 0 | 0 | 0 | 0 | 150 | 123 | 122 | 102 | 110 |
| `expr:text:substr_from` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 102 | 134 | 120 | 130 |
| `expr:text:substring` | 645 | 194 | 271 | 39 | 141 | 145 | 160 | 121 | 106 | 112 | 103 |
| `expr:text:trim` | 627 | 220 | 237 | 34 | 136 | 136 | 150 | 129 | 114 | 94 | 123 |
| `expr:text:trim_both` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 96 | 123 | 120 | 122 |
| `expr:text:typed_cast` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 248 | 216 | 213 | 225 |
| `group:by_alias` | 848 | 151 | 375 | 22 | 300 | 164 | 427 | 406 | 250 | 228 | 190 |
| `group:by_ordinal` | 2,929 | 490 | 1325 | 63 | 1051 | 512 | 1,389 | 1,333 | 1,351 | 1,296 | 1,311 |
| `group:col` | 11,082 | 2152 | 4135 | 421 | 4374 | 1592 | 5,429 | 5,370 | 5,136 | 5,015 | 4,963 |
| `group:col:bool` | 968 | 186 | 462 | 36 | 284 | 210 | 471 | 507 | 436 | 306 | 246 |
| `group:col:date` | 1,344 | 268 | 631 | 56 | 389 | 179 | 686 | 623 | 596 | 447 | 378 |
| `group:col:dbl` | 1,944 | 0 | 0 | 0 | 1944 | 356 | 981 | 953 | 976 | 975 | 829 |
| `group:col:dec` | 1,071 | 231 | 469 | 46 | 325 | 151 | 502 | 520 | 476 | 911 | 732 |
| `group:col:int` | 4,324 | 953 | 1889 | 157 | 1325 | 519 | 2,132 | 2,084 | 1,975 | 2,082 | 1,700 |
| `group:col:text` | 2,980 | 632 | 1270 | 176 | 902 | 602 | 1,433 | 1,428 | 1,346 | 1,032 | 1,284 |
| `group:col:ts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 544 |
| `group:dbl` | 2,193 | 0 | 0 | 0 | 2193 | 413 | 1,101 | 1,091 | 1,097 | 1,083 | 943 |
| `group:expr` | 5,144 | 790 | 2239 | 395 | 1720 | 965 | 2,618 | 2,487 | 2,410 | 2,324 | 2,385 |
| `group:expr:bool->bool` | 407 | 60 | 189 | 40 | 118 | 90 | 188 | 221 | 194 | 135 | 117 |
| `group:expr:date->int` | 574 | 80 | 295 | 36 | 163 | 54 | 293 | 253 | 247 | 197 | 143 |
| `group:expr:dbl->dbl` | 277 | 0 | 0 | 0 | 277 | 63 | 128 | 147 | 136 | 113 | 125 |
| `group:expr:dbl->int` | 287 | 26 | 138 | 17 | 106 | 37 | 151 | 141 | 131 | 153 | 130 |
| `group:expr:dbl->text` | 275 | 37 | 123 | 27 | 88 | 75 | 151 | 131 | 136 | 127 | 125 |
| `group:expr:dec->dec` | 195 | 32 | 89 | 12 | 62 | 26 | 102 | 113 | 103 | 201 | 158 |
| `group:expr:dec->int` | 233 | 49 | 97 | 17 | 70 | 23 | 112 | 101 | 102 | 170 | 151 |
| `group:expr:int->int` | 1,951 | 311 | 881 | 169 | 590 | 418 | 977 | 886 | 909 | 918 | 761 |
| `group:expr:text->text` | 1,266 | 215 | 571 | 110 | 370 | 272 | 673 | 632 | 608 | 443 | 584 |
| `group:expr:ts->date` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 250 |
| `having:agg_cmp` | 1,353 | 275 | 474 | 60 | 544 | 117 | 620 | 660 | 648 | 599 | 607 |
| `having:count` | 1,318 | 286 | 489 | 59 | 484 | 113 | 682 | 630 | 657 | 642 | 653 |
| `having:global` | 360 | 295 | 0 | 0 | 65 | 0 | 149 | 203 | 164 | 172 | 191 |
| `having:grp_const` | 1,290 | 457 | 335 | 56 | 442 | 37 | 693 | 592 | 640 | 613 | 667 |
| `having:grp_null` | 1,384 | 537 | 276 | 40 | 531 | 18 | 651 | 658 | 633 | 623 | 615 |
| `join:comma` | 7,787 | 2457 | 2749 | 874 | 1707 | 1641 | 3,921 | 4,006 | 3,802 | 3,987 | 3,987 |
| `join:cross` | 3,250 | 1065 | 1141 | 344 | 700 | 887 | 1,634 | 1,702 | 1,587 | 1,626 | 1,626 |
| `join:eq` | 6,298 | 2079 | 2228 | 673 | 1318 | 1080 | 3,141 | 3,081 | 3,128 | 3,162 | 3,240 |
| `join:key` | 10,634 | 3447 | 3779 | 1092 | 2316 | 2029 | 5,531 | 5,506 | 5,302 | 5,315 | 5,419 |
| `join:on_char_varchar` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,362 |
| `join:on_eq_keycol` | 9,566 | 3050 | 3311 | 989 | 2216 | 1605 | 4,783 | 4,809 | 4,786 | 3,614 | 2,250 |
| `join:on_eq_nonkey` | 10,134 | 3145 | 3532 | 1062 | 2395 | 1985 | 5,173 | 5,126 | 5,001 | 6,290 | 4,938 |
| `join:on_fk_key` | 2,484 | 808 | 845 | 208 | 623 | 541 | 1,232 | 1,346 | 1,243 | 1,317 | 909 |
| `join:on_theta` | 5,905 | 1835 | 2094 | 679 | 1297 | 1466 | 2,972 | 2,952 | 2,830 | 2,949 | 3,027 |
| `join:on_ts_tz` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2,118 |
| `join:self` | 9,248 | 2836 | 3109 | 937 | 2366 | 2045 | 4,678 | 4,582 | 4,595 | 4,566 | 4,678 |
| `join:theta` | 3,277 | 1041 | 1166 | 348 | 722 | 834 | 1,662 | 1,607 | 1,603 | 1,662 | 1,700 |
| `known:distinct_order_nonoutput` | 0 | 0 | 0 | 0 | 0 | 0 | 439 | 421 | 308 | 343 | 307 |
| `limit` | 24,224 | 8274 | 8108 | 2103 | 5739 | 4626 | 12,029 | 12,067 | 12,206 | 12,213 | 12,054 |
| `limit:0` | 3,503 | 1190 | 1170 | 291 | 852 | 0 | 1,714 | 1,725 | 1,756 | 1,728 | 1,791 |
| `offset` | 8,457 | 2819 | 2831 | 754 | 2053 | 1537 | 4,237 | 4,316 | 4,283 | 4,327 | 4,185 |
| `oof:collate` | 0 | 0 | 0 | 0 | 0 | 0 | 191 | 189 | 208 | 204 | 207 |
| `oof:cte` | 535 | 0 | 0 | 0 | 535 | 342 | 210 | 217 | 237 | 201 | 214 |
| `oof:derived` | 545 | 0 | 0 | 0 | 545 | 317 | 217 | 182 | 223 | 208 | 202 |
| `oof:distinct_on` | 557 | 0 | 0 | 0 | 557 | 150 | 201 | 195 | 192 | 202 | 202 |
| `oof:groupall` | 531 | 0 | 0 | 0 | 531 | 64 | 173 | 175 | 194 | 154 | 199 |
| `oof:left` | 570 | 0 | 0 | 0 | 570 | 114 | 192 | 205 | 193 | 216 | 180 |
| `oof:natural` | 501 | 0 | 0 | 0 | 501 | 25 | 197 | 181 | 193 | 189 | 216 |
| `oof:nested_limit` | 467 | 0 | 0 | 0 | 467 | 58 | 181 | 178 | 179 | 203 | 180 |
| `oof:nested_window` | 0 | 0 | 0 | 0 | 0 | 0 | 191 | 200 | 219 | 219 | 202 |
| `oof:orderagg` | 536 | 0 | 0 | 0 | 536 | 167 | 192 | 176 | 192 | 173 | 180 |
| `oof:orderagg:any_value` | 111 | 0 | 0 | 0 | 111 | 40 | 26 | 33 | 40 | 37 | 38 |
| `oof:orderagg:arg_max` | 90 | 0 | 0 | 0 | 90 | 25 | 35 | 39 | 30 | 31 | 36 |
| `oof:orderagg:first` | 113 | 0 | 0 | 0 | 113 | 34 | 44 | 31 | 48 | 35 | 39 |
| `oof:orderagg:list` | 100 | 0 | 0 | 0 | 100 | 34 | 36 | 41 | 43 | 33 | 34 |
| `oof:orderagg:string_agg` | 122 | 0 | 0 | 0 | 122 | 34 | 51 | 32 | 31 | 37 | 33 |
| `oof:percent_limit` | 0 | 0 | 0 | 0 | 0 | 0 | 230 | 214 | 185 | 191 | 205 |
| `oof:qualify` | 531 | 0 | 0 | 0 | 531 | 228 | 183 | 200 | 201 | 187 | 210 |
| `oof:rollup` | 0 | 0 | 0 | 0 | 0 | 0 | 186 | 201 | 193 | 188 | 188 |
| `oof:sample` | 0 | 0 | 0 | 0 | 0 | 0 | 232 | 230 | 184 | 247 | 228 |
| `oof:setop` | 571 | 0 | 0 | 0 | 571 | 151 | 207 | 211 | 229 | 194 | 217 |
| `oof:setop:except` | 148 | 0 | 0 | 0 | 148 | 32 | 61 | 53 | 62 | 48 | 54 |
| `oof:setop:intersect` | 149 | 0 | 0 | 0 | 149 | 30 | 54 | 54 | 52 | 37 | 64 |
| `oof:setop:union` | 134 | 0 | 0 | 0 | 134 | 43 | 46 | 52 | 65 | 50 | 53 |
| `oof:setop:union_all` | 140 | 0 | 0 | 0 | 140 | 46 | 46 | 52 | 50 | 59 | 46 |
| `oof:unknown_func` | 542 | 0 | 0 | 0 | 542 | 217 | 194 | 202 | 202 | 199 | 194 |
| `oof:using` | 500 | 0 | 0 | 0 | 500 | 66 | 208 | 179 | 198 | 179 | 205 |
| `oof:volatile` | 557 | 0 | 0 | 0 | 557 | 272 | 176 | 220 | 173 | 190 | 207 |
| `oof:window` | 570 | 0 | 0 | 0 | 570 | 195 | 178 | 213 | 193 | 198 | 197 |
| `order:agg` | 3,347 | 739 | 1222 | 130 | 1256 | 433 | 1,537 | 1,449 | 1,019 | 934 | 965 |
| `order:alias` | 4,709 | 1653 | 1696 | 0 | 1360 | 912 | 1,825 | 1,856 | 1,249 | 1,262 | 1,341 |
| `order:alias_expr` | 0 | 0 | 0 | 0 | 0 | 0 | 1,649 | 1,545 | 945 | 897 | 896 |
| `order:alias_paren` | 662 | 0 | 0 | 0 | 662 | 121 | 250 | 231 | 180 | 192 | 175 |
| `order:all` | 1,562 | 1245 | 0 | 0 | 317 | 21 | 835 | 791 | 883 | 855 | 820 |
| `order:asc` | 9,077 | 3059 | 3241 | 396 | 2381 | 1772 | 4,521 | 4,459 | 4,276 | 4,329 | 4,376 |
| `order:case_alias` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,384 | 1,388 | 1,362 |
| `order:col` | 7,762 | 2623 | 3020 | 978 | 1141 | 2190 | 3,577 | 3,590 | 2,747 | 2,858 | 2,794 |
| `order:desc` | 16,275 | 5364 | 5716 | 800 | 4395 | 3182 | 8,144 | 8,147 | 7,771 | 7,732 | 7,756 |
| `order:expr` | 3,901 | 1073 | 1675 | 593 | 560 | 1209 | 1,862 | 1,980 | 1,424 | 1,521 | 1,491 |
| `order:grp` | 3,061 | 735 | 1235 | 17 | 1074 | 173 | 1,409 | 1,321 | 927 | 915 | 901 |
| `order:nulls_first` | 9,143 | 3122 | 3181 | 393 | 2447 | 1748 | 4,563 | 4,529 | 4,239 | 4,225 | 4,232 |
| `order:nulls_last` | 9,053 | 3011 | 3168 | 418 | 2456 | 1743 | 4,510 | 4,433 | 4,336 | 4,325 | 4,314 |
| `order:ordinal` | 10,449 | 4350 | 3213 | 0 | 2886 | 1706 | 4,338 | 4,368 | 3,056 | 3,020 | 3,031 |
| `order:out_expr` | 9,828 | 3539 | 3228 | 183 | 2878 | 1510 | 4,139 | 4,115 | 2,926 | 2,876 | 2,960 |
| `order:paren` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3,008 | 2,981 | 3,015 |
| `order:sub` | 0 | 0 | 0 | 0 | 0 | 0 | 1,773 | 1,783 | 1,411 | 1,411 | 1,376 |
| `order:unary_alias` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 481 | 455 | 468 |
| `order:unary_col` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 718 | 729 | 634 |
| `order:unary_ordinal` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 564 | 531 | 535 |
| `out:col` | 20,755 | 5623 | 8620 | 2712 | 3800 | 6896 | 10,498 | 10,567 | 10,774 | 10,964 | 10,915 |
| `out:col:bool` | 2,308 | 514 | 1039 | 316 | 439 | 832 | 1,167 | 1,270 | 1,220 | 991 | 783 |
| `out:col:date` | 3,072 | 757 | 1391 | 350 | 574 | 1130 | 1,540 | 1,608 | 1,576 | 1,246 | 1,013 |
| `out:col:dbl` | 4,401 | 995 | 1979 | 620 | 807 | 1557 | 2,353 | 2,333 | 2,508 | 2,562 | 2,219 |
| `out:col:dec` | 2,473 | 542 | 1300 | 170 | 461 | 867 | 1,242 | 1,155 | 1,251 | 2,396 | 2,027 |
| `out:col:int` | 9,699 | 2339 | 4331 | 1259 | 1770 | 3447 | 4,864 | 4,802 | 4,968 | 5,432 | 4,622 |
| `out:col:text` | 6,705 | 1649 | 3314 | 525 | 1217 | 2348 | 3,406 | 3,382 | 3,442 | 2,755 | 3,523 |
| `out:col:ts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,439 |
| `out:exists` | 0 | 0 | 0 | 0 | 0 | 0 | 834 | 831 | 813 | 862 | 914 |
| `out:expr` | 13,019 | 3588 | 5950 | 1108 | 2373 | 4204 | 6,742 | 6,672 | 6,685 | 6,862 | 6,965 |
| `out:fn_of_group` | 1,031 | 210 | 485 | 3 | 333 | 121 | 483 | 482 | 449 | 489 | 427 |
| `out:scalar_sub` | 5,125 | 942 | 2397 | 308 | 1478 | 1581 | 1,846 | 1,879 | 1,831 | 1,938 | 1,957 |
| `out:star` | 1,410 | 341 | 887 | 12 | 170 | 532 | 714 | 732 | 734 | 705 | 565 |
| `out:star_exclude` | 0 | 0 | 0 | 0 | 0 | 0 | 75 | 80 | 80 | 68 | 62 |
| `out:star_replace` | 0 | 0 | 0 | 0 | 0 | 0 | 96 | 77 | 76 | 78 | 51 |
| `ref:unqualified` | 8,801 | 2897 | 3167 | 653 | 2084 | 1814 | 4,533 | 4,514 | 4,313 | 4,669 | 4,881 |
| `ref:unqualified_in_subquery` | 0 | 0 | 0 | 0 | 0 | 0 | 1,180 | 1,182 | 1,167 | 1,063 | 1,032 |
| `shape:global` | 6,755 | 5558 | 0 | 0 | 1197 | 9 | 3,403 | 3,399 | 3,503 | 3,550 | 3,605 |
| `shape:grouped` | 14,213 | 2738 | 5511 | 678 | 5286 | 2049 | 7,095 | 6,921 | 6,632 | 6,468 | 6,466 |
| `shape:plain` | 27,381 | 8247 | 10606 | 3510 | 5018 | 8398 | 13,868 | 14,070 | 14,176 | 14,379 | 14,296 |
| `subq:scalar` | 7,497 | 1758 | 3154 | 498 | 2087 | 1861 | 4,520 | 4,584 | 4,254 | 4,042 | 3,915 |
| `subq:scalar:agg_corr` | 3,655 | 754 | 1534 | 280 | 1087 | 956 | 2,287 | 2,263 | 2,118 | 2,070 | 1,909 |
| `subq:scalar:agg_uncorr` | 1,648 | 467 | 667 | 45 | 469 | 409 | 969 | 1,002 | 966 | 871 | 853 |
| `subq:scalar:key_lookup` | 1,127 | 282 | 481 | 73 | 291 | 285 | 712 | 690 | 600 | 573 | 579 |
| `subq:scalar:multi_row` | 1,607 | 335 | 742 | 115 | 415 | 337 | 1,024 | 1,069 | 934 | 872 | 908 |
| `where:between` | 2,152 | 741 | 719 | 197 | 495 | 233 | 1,077 | 1,091 | 1,071 | 885 | 738 |
| `where:char_varchar_eq` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1,907 |
| `where:cmp_const` | 9,653 | 3322 | 3186 | 796 | 2349 | 1718 | 5,059 | 5,136 | 5,187 | 4,007 | 3,256 |
| `where:col_eq` | 9,031 | 2983 | 2977 | 794 | 2277 | 620 | 4,807 | 4,773 | 4,663 | 3,790 | 3,219 |
| `where:col_eq:bool` | 170 | 50 | 63 | 16 | 41 | 36 | 107 | 113 | 83 | 30 | 28 |
| `where:col_eq:cross_alias` | 2,884 | 855 | 1005 | 302 | 722 | 237 | 1,541 | 1,498 | 1,452 | 1,150 | 964 |
| `where:col_eq:date` | 337 | 120 | 102 | 23 | 92 | 31 | 165 | 180 | 168 | 56 | 40 |
| `where:col_eq:dbl` | 397 | 124 | 117 | 44 | 112 | 78 | 245 | 241 | 233 | 163 | 132 |
| `where:col_eq:dbl-dec` | 406 | 121 | 125 | 43 | 117 | 44 | 258 | 221 | 241 | 340 | 278 |
| `where:col_eq:dbl-int` | 1,758 | 584 | 522 | 160 | 492 | 82 | 951 | 980 | 958 | 749 | 543 |
| `where:col_eq:dec` | 111 | 33 | 42 | 9 | 27 | 18 | 83 | 54 | 68 | 127 | 93 |
| `where:col_eq:dec-int` | 960 | 319 | 334 | 85 | 222 | 53 | 452 | 447 | 455 | 762 | 495 |
| `where:col_eq:int` | 1,880 | 635 | 628 | 167 | 450 | 168 | 941 | 935 | 937 | 805 | 525 |
| `where:col_eq:int-text` | 2,664 | 846 | 929 | 244 | 645 | 26 | 1,429 | 1,394 | 1,357 | 801 | 861 |
| `where:col_eq:same_alias` | 6,433 | 2210 | 2069 | 522 | 1632 | 398 | 3,409 | 3,409 | 3,344 | 2,723 | 2,306 |
| `where:col_eq:text` | 991 | 352 | 323 | 82 | 234 | 99 | 554 | 542 | 507 | 218 | 341 |
| `where:col_eq:ts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 48 |
| `where:const_enotation` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6,033 | 5,059 |
| `where:const_enotation:dec` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2,743 | 2,241 |
| `where:const_enotation:int` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3,554 | 2,982 |
| `where:const_eq` | 13,398 | 4951 | 4129 | 967 | 3351 | 1873 | 7,098 | 7,037 | 7,173 | 5,607 | 4,719 |
| `where:const_eq:bool` | 1,180 | 391 | 408 | 113 | 268 | 228 | 633 | 608 | 602 | 357 | 247 |
| `where:const_eq:date` | 1,507 | 509 | 517 | 111 | 370 | 216 | 831 | 841 | 839 | 454 | 291 |
| `where:const_eq:dbl` | 2,225 | 700 | 723 | 182 | 620 | 415 | 1,322 | 1,210 | 1,249 | 988 | 668 |
| `where:const_eq:dec` | 1,238 | 422 | 417 | 95 | 304 | 208 | 662 | 610 | 630 | 945 | 646 |
| `where:const_eq:int` | 5,193 | 2080 | 1499 | 345 | 1269 | 528 | 2,708 | 2,698 | 2,766 | 2,275 | 1,609 |
| `where:const_eq:text` | 3,573 | 1461 | 1032 | 209 | 871 | 421 | 1,789 | 1,887 | 1,928 | 1,095 | 1,207 |
| `where:const_eq:ts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 451 |
| `where:exists` | 4,240 | 1428 | 1500 | 342 | 970 | 700 | 2,104 | 2,082 | 2,267 | 1,763 | 1,483 |
| `where:expr_eq` | 3,727 | 1275 | 1162 | 319 | 971 | 345 | 2,042 | 2,000 | 2,037 | 1,562 | 1,304 |
| `where:in_list` | 3,175 | 1062 | 1010 | 291 | 812 | 524 | 1,696 | 1,655 | 1,740 | 1,322 | 1,137 |
| `where:in_sub` | 4,201 | 1495 | 1390 | 379 | 937 | 679 | 2,190 | 2,200 | 2,103 | 1,775 | 1,371 |
| `where:isnull` | 5,453 | 2001 | 1700 | 437 | 1315 | 865 | 2,768 | 2,863 | 2,857 | 2,229 | 1,740 |
| `where:or` | 3,768 | 1267 | 1284 | 337 | 880 | 618 | 1,870 | 1,818 | 1,940 | 1,580 | 1,258 |
| `where:scalar_cmp` | 2,660 | 862 | 901 | 204 | 693 | 322 | 1,310 | 1,322 | 1,365 | 1,027 | 890 |
| `where:ts_tz_eq` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2,832 |
