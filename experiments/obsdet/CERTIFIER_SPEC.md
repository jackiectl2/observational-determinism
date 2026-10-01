# Certifier specification (implementation of record)

This document states what `certify.py` accepts, how it types expressions, which functional dependencies it uses, and
every reason code it can return. For each rule it records which adversarial cases and which replayed natural
statements exercise it. The theorems of the paper (Section 3) are about these rules; whether the code applies them
as the engine reads a statement is tested, not proved (paper, Sections 4 and 5.3).

- Implementation: `experiments/obsdet/certify.py`, md5 `80705f632bf861731a2084d2cf5c1306`, 743 lines (7626553a plus the
  rejection of qualified table names in step 6 and a docstring note on premise (vi); same verdicts and tie-breaks as the
  certifier of the runs on every evaluated statement, jobs 61902064 and 61902355).
- Environment: sqlglot 30.19.0, DuckDB 1.5.5, PostgreSQL 16.2 (`experiments/obsdet/results/env_versions.json`).
- Tool (`experiments/obsdet/tool.py`, md5 `md5-withheld`, 58 lines): runs only statements that DuckDB parses as queries,
  each on a fresh cursor of a private instance, so no call changes the tables, keys or settings that later certificates
  rely on; together with step 6 (qualified names are `unknown-table`), every table name the certifier binds denotes the
  catalog's table (JOBS.md, "Name binding and state changes"). If the exact count of a long result fails, the call
  fails (JOBS.md, job 61905605).
- Constants (step on constant attributes): DuckDB 1.5.5 compares a DECIMAL or integer column with a numeric literal of
  up to 38 digits exactly, also when the exact common decimal would need more than 38 digits (job 61905604, 12
  cases); a longer literal is typed DOUBLE by DuckDB and by the certifier, so it creates no constant.
- Adversarial suite: `experiments/obsdet/adversarial.py` (md5 `877ae29bc32c6c92cc954cb49d06b1c7`), result
  `results/v7/adversarial_v7final.json` (75 DuckDB cases, numbered 1–75 below in file order) and the 18 PostgreSQL
  verdict checks in `results/v7/logs/obsdet-adv7f-61889821.out`.
- Natural statements: the certificates in `results/v7/cert_probes_v7.jsonl` (development, 1,015),
  `cert_heldout_kept_v7.jsonl` (held-out, 1,125), `cert_td_new_v7.jsonl` (unseen tasks I, 1,321) and
  `cert_td2_new.jsonl` (unseen tasks II, 1,267); PostgreSQL-dialect verdicts in the `sound_pg_*` files.

## 1. Order of checks

`certify(sql, catalog, dialect)` runs these steps in order and returns the first reason code that applies.

1. Parse with sqlglot in the engine's dialect. Parse failure: `parse:<exception>`. More than one statement:
   `multi-statement`. Not a `SELECT`: `not-select:<kind>`.
2. Token-level checks on the statement as written (before any rewriting by sqlglot):
   - PostgreSQL only: the token `date_part` followed by `(`: `function:date_part` (sqlglot would turn the
     double-precision `date_part` into `EXTRACT`, which returns `numeric`).
   - A top-level `ORDER BY` item that starts with a unary `+`: `order-by-unary-plus` (sqlglot drops it).
   - A type keyword, a string literal and `::` in sequence: `typed-literal-cast` (sqlglot inverts the two casts).
3. Joins in every `SELECT`, checked as written because name qualification turns `USING` and `NATURAL` into `ON`:
   a side (`LEFT`/`RIGHT`/`FULL`), a method (`NATURAL`, `ASOF`, `POSITIONAL`) or a kind other than inner or cross:
   `outer-or-special-join`; `USING`: `using-join`.
4. `ORDER BY` items as written: ordinals and unqualified names are recorded for resolution against the outputs. An
   output alias used inside an `ORDER BY` expression: `order-by-alias-in-expression` (both engines bind such names to
   input columns). PostgreSQL, when `ORDER BY` uses names: a quoted identifier with upper-case letters among the
   `ORDER BY` names or the outputs: `pg-quoted-name`.
5. Name resolution and star expansion (`sqlglot.optimizer.qualify` with column validation). Failure:
   `unresolved:<exception>`.
6. Fragment checks on the root and every nested `SELECT`: a `WITH` clause: `cte`; any clause other than the select
   list, `DISTINCT`, `FROM`, joins, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, `OFFSET`: `clause:<name>`;
   joins again after qualification (step 3); `DISTINCT ON`: `distinct-on`; `ROLLUP`, `CUBE`, `GROUPING SETS`:
   `grouping-sets`; `GROUP BY ALL`: `group-by-all`; a `FROM` item that is not a base table: `derived-table`; a table
   not in the catalog: `unknown-table`. The catalog describes one schema by bare names, so a schema- or
   catalog-qualified name (`evil.t`, `main.t`, `db.s.t`) is never matched to a catalog table and is `unknown-table`.
7. Node-level checks anywhere in the query: window functions, set operations, `LATERAL`, `UNNEST`, `PIVOT`,
   `TABLESAMPLE`, `FETCH`, `COLLATE`: `construct:<node>`; volatile functions (`random`, `rand`, `uuid`,
   `current_date`, `current_timestamp`, `current_time`, random bits): `volatile:<node>`; a subquery in `FROM` or a
   join: `derived-table`; a nested `SELECT` with `LIMIT` or `OFFSET`: `nested-limit`; a nested `SELECT` without a base
   table: `derived-table`; a function that is not on the allowlist (Section 2): `function:<name>`.
8. `LIMIT` and `OFFSET` of the root must be integer literals without percent or `WITH TIES`: otherwise `limit-form`
   or `offset-form`. A root `SELECT` without a base table: `no-base-table`.
9. Equality-class checks (Section 3): a `GROUP BY` expression that is not of an exact type: `inexact-group-key`; a
   `DISTINCT` projection of inexact type inside a subquery whose value is used other than by rendering, sorting or
   comparing: `inexact-distinct-value`; `MIN`/`MAX` over an inexact argument in such a position:
   `inexact-min-max-in-expression`.
10. PostgreSQL only: a string literal `'now'`, `'today'`, `'tomorrow'` or `'yesterday'`, unless it is compared with
    text: `relative-time-literal`; a cast of text (or of an expression of unknown type) to a temporal type:
    `text-to-temporal-cast`.
11. Aggregates: only `COUNT`, `MIN`, `MAX`, `SUM`, `AVG` (otherwise `aggregate:<name>`); `SUM`/`AVG` over an argument
    of unknown, text, temporal or other type: `aggregate-type-unknown`; over a floating-point argument:
    `float-aggregate`.
12. `ORDER BY` resolution: an `ORDER BY ALL` stands for every output position. If qualification changed the number of
    `ORDER BY` items: `order-by-rewritten`. An ordinal outside `1..n`: `order-by-position`. A name that several
    outputs carry: `ambiguous-order-by-name`. Under `DISTINCT`, an `ORDER BY` item that is not an output:
    `distinct-order-by-non-output`.
13. Verdicts and covers as in the paper (Section 3.3, Algorithm 1). The tie-break is spliced into the statement as
    written (Section 5); if the spliced text does not parse to exactly the original statement with the keys
    appended: `rewrite-splice`.

## 2. Function allowlist

Scalar functions are admitted only if sqlglot parses them into one of these node types (identical for both
dialects): `And`, `Or`, `Not`, `Xor`, `If`, `Case`, `Cast`, `TryCast`, `Coalesce`, `Nullif`, `Extract`, `Year`,
`Month`, `Day`, `Quarter`, `Week`, `DayOfWeek`, `DayOfMonth`, `DayOfYear`, `Date`, `Substring`, `Left`, `Right`,
`Length`, `Lower`, `Upper`, `Trim`, `Replace`, `StrPosition`, `Split`, `SplitPart`, `Concat`, `ConcatWs`, `Round`,
`Abs`, `Floor`, `Ceil`, `Sqrt`, `Pow`, `Sign`, `Ln`, `Log`, `Exp`, `DateDiff`, `DateAdd`, `DateSub`, `DateTrunc`,
`TimestampTrunc`, `TimeToStr` (e.g. `strftime`), `StrToTime`, `StrToDate`, `Greatest`, `Least`, `Initcap`,
`RegexpLike`, `Exists`; plus the aggregates of step 11, and the unparsed functions `date_part`/`datepart` (DuckDB only;
PostgreSQL rejects `date_part` in step 2). Arithmetic and comparison operators are expressions, not functions, and are
admitted. Every other function, including every function sqlglot does not recognize, is rejected (`function:<name>`).

## 3. Types

Declared column types map to classes: integer types (`TINYINT` … `HUGEINT`, unsigned variants, `INT2/4/8`) → INT;
`DOUBLE`, `FLOAT`, `REAL`, `FLOAT4/8` → FLOAT; `DECIMAL`/`NUMERIC` → DECIMAL; `BOOLEAN` → BOOL; `VARCHAR`, `TEXT`,
`STRING`, `CHAR` → TEXT; `DATE`, `TIMESTAMP`, `TIME`, `DATETIME`, `TIMESTAMP WITH TIME ZONE` → TIME; anything else →
OTHER. Exact classes: INT, DECIMAL, TEXT (binary collation), BOOL, TIME. FLOAT and OTHER are inexact.

Expression types (`_Ctx.infer`):

- Literals: string → TEXT; integer → INT; other numeric → DECIMAL. DuckDB only: a literal in exponent notation, with
  more than 38 digits, or an integer beyond the `HUGEINT` range → FLOAT.
- `+`, `-`, `*`, `%`, `CASE`, `IF`, `COALESCE`, `GREATEST`, `LEAST`: combination of the operand types (any FLOAT →
  FLOAT; INT/BOOL only → INT; INT/BOOL/DECIMAL → DECIMAL; otherwise the common type, else unknown).
- `/`: DuckDB → FLOAT for all operands (DuckDB returns `DOUBLE`, also for two `DECIMAL`s); PostgreSQL → combination.
  `//` (integer division): INT for integer operands; DuckDB → FLOAT otherwise.
- `EXTRACT` and `date_part`: INT, except the parts `epoch` and `julian` → FLOAT.
- PostgreSQL `sign`: FLOAT for a FLOAT argument, else DECIMAL.
- String functions → TEXT; `LENGTH`, `COUNT`, date-part functions, `StrPosition`, `DateDiff`, DuckDB `sign` → INT;
  date functions → TIME; `SQRT`, `LN`, `LOG`, `EXP`, `POW` → FLOAT; `ABS`, `ROUND`, `MIN`, `MAX`, `FLOOR`, `CEIL`,
  `NULLIF` keep the type of their argument; casts take the target type.

## 4. Functional dependencies and constants (root `SELECT`)

- Key FDs: for every `FROM` alias `a` of a table with a catalog key `K` (validated on the data, `catalog.json`):
  `a.K → all columns of a`.
- Equality FDs: for a top-level conjunct `x = y` of `WHERE`, `ON` or `HAVING` between root columns, both directions,
  if the pair is exact without conversion: INT = INT (but `UBIGINT`/`UHUGEINT` only with the identical declared
  type); DECIMAL = DECIMAL and TIME = TIME only with identical declared types; TEXT = TEXT unless either side is a
  blank-padded `CHAR`/`BPCHAR`/`CHARACTER`; BOOL = BOOL. All other pairs give no FD.
- Constants: `x = literal` where `x` is INT or DECIMAL and the literal is a string or an exact numeric literal; or `x`
  is TEXT or TIME, the literal is a string, and `x` is not blank-padded; and `x IS NULL`.
- The closure is seeded with the exact-typed plain `ORDER BY` columns (ordinals and names resolved to outputs as
  written) and the constants.

## 5. Coverage of each rule

Counts are statements per set (development / held-out / unseen I / unseen II). "Adversarial" lists DuckDB case
numbers; PostgreSQL checks are listed in Section 6.

| Verdict or reason code | Adversarial (DuckDB) | Natural, DuckDB dialect | Natural, PostgreSQL dialect |
|---|---|---|---|
| DET, single-row aggregate (D1) | 13, 49, 55, 56, 73 | 116/143/215/184 | 116/139/210/184 |
| DET, order determines group key (D2) | 20, 40 | 1/2/12/2 | 1/2/12/2 |
| DET, order determines every output (D3) | 1, 2, 3, 7, 16, 22, 25, 28, 31, 43, 45, 58, 75 | 49/44/86/83 | 49/44/86/83 |
| NARROW, key tie-break | 4, 8, 11, 17, 27, 42, 53, 59, 60, 74 | 410/307/352/374 | 411/306/352/370 |
| NARROW, group-key tie-break | 5, 26, 29, 34 | 56/54/69/36 | 56/54/69/36 |
| NARROW, output tie-break | 18, 24, 32 | 45/22/50/47 | 45/21/50/47 |
| ALL, key tie-break | — | 54/93/78/91 | 52/92/78/89 |
| ALL, group-key tie-break | — | 0/3/10/5 | 0/3/10/5 |
| ALL, output tie-break | 6, 9, 10, 33, 35, 41, 46, 47 | 123/108/127/123 | 123/108/127/123 |
| `derived-table` | 15 | 64/133/123/118 | 64/133/123/118 |
| `cte` | 52 | 4/34/43/30 | 4/34/43/30 |
| `construct` | 36, 39 | 0/5/0/15 | 0/5/0/15 |
| `outer-or-special-join` | 14, 62, 63 | 6/16/8/13 | 6/16/8/13 |
| `using-join` | 61 | 0 | 0 |
| `nested-limit` | — | 6/2/9/3 | 6/2/9/3 |
| `limit-form` | 37 | 0 | 0 |
| `distinct-on` | 51 | 0 | 0 |
| `group-by-all` | 44 | 0 | 0 |
| `distinct-order-by-non-output` | 57 | 1/1/2/2 | 1/1/2/2 |
| `float-aggregate` | 12, 23, 54, 64, 65, 66, 72 | 48/41/37/24 | 48/41/28/24 |
| `inexact-group-key` | 50 | 2/0/0/2 | 2/0/0/2 |
| `inexact-min-max-in-expression` | 48, 67 | 0 | 0 |
| `aggregate` | — | 0/1/0/0 | 0/1/0/0 |
| `aggregate-type-unknown` | — | 0 | 0/0/7/0 |
| `function` (incl. `function:date_part`) | 38 | 0/2/2/9 | 0/4/9/9 |
| `volatile` | 19 | 0/6/0/0 | 0/6/0/0 |
| `order-by-unary-plus` | 68, 69 | 0 | 0 |
| `order-by-alias-in-expression` | 70 | 0 | 0 |
| `typed-literal-cast` | 71 | 0 | 0 |
| `text-to-temporal-cast` (PostgreSQL) | — | — | 1/5/0/6 |
| `multi-statement` | 30 | 7/5/2/3 | 7/5/3/3 |
| `not-select` | 21 | 3/14/5/9 | 3/14/4/9 |
| `no-base-table` | — | 2/85/85/80 | 2/85/85/80 |
| `unresolved` | — | 18/4/6/12 | 18/4/6/12 |
| `unknown-table` | — (qualified names: unit check `qualified_check.py`, job 61902063) | 0/0/0/2 | 0/0/0/2 |

Codes that neither an adversarial DuckDB case nor a natural statement exercised: `relative-time-literal` and
`pg-quoted-name` (both exercised by PostgreSQL checks, Section 6), `ambiguous-order-by-name`, `order-by-position`,
`order-by-rewritten`, `rewrite-splice`, `grouping-sets`, `inexact-distinct-value`, `offset-form`, `clause:*` and
`parse:*`. They are fail-closed guards; the property-based tests in `JOBS_PROPTEST.md` exercise generated queries
beyond these cases.

## 6. PostgreSQL verdict checks (all 18 returned the expected verdict)

| Statement | Expected and returned verdict |
|---|---|
| `SELECT TIMESTAMP 'now' FROM emp` | UNSUPPORTED |
| `SELECT CAST('today' AS DATE) FROM emp` | UNSUPPORTED |
| `SELECT CAST(name AS TIMESTAMP) FROM emp` | UNSUPPORTED |
| `SELECT name FROM emp WHERE id = 3` | DET |
| `SELECT name, salary FROM emp ORDER BY salary DESC LIMIT 2` | NARROW |
| `SELECT name FROM emp WHERE name = 'now'` | DET |
| `SELECT name FROM ev WHERE 'today' IN (d)` | UNSUPPORTED |
| `SELECT name FROM ev WHERE 'now' IN (name)` | NARROW |
| `SELECT AVG(a / b) FROM dec` | DET (in PostgreSQL, `numeric / numeric` is `numeric`, not `double precision`) |
| `SELECT DISTINCT d.dname FROM dept d JOIN emp e ON e.dept_id = d.id ORDER BY e.salary LIMIT 1` | UNSUPPORTED |
| `SELECT AVG(DATE_PART('year', d)) FROM ev` | UNSUPPORTED |
| `SELECT AVG(EXTRACT(YEAR FROM d)) FROM ev` | DET |
| `SELECT SUM(SIGN(bonus)) FROM emp` | UNSUPPORTED (`sign` of a double is a double) |
| `SELECT e.name, e.id AS name FROM emp e ORDER BY 1 LIMIT 3` | NARROW (the ordinal is resolved as written) |
| `SELECT name AS "ID", salary FROM emp ORDER BY id LIMIT 3` | UNSUPPORTED (`pg-quoted-name`) |
| `SELECT name, salary FROM emp ORDER BY +2 LIMIT 3` | UNSUPPORTED (`order-by-unary-plus`) |
| `SELECT b.l FROM tza a JOIN tzb b ON a.z = b.l ORDER BY a.z LIMIT 1` | ALL (`timestamptz` = `timestamp` gives no FD) |
| `SELECT b.v FROM pad a JOIN vt b ON a.c = b.v ORDER BY a.c LIMIT 1` | NARROW (`CHAR` = `VARCHAR` gives no FD) |

The adversarial DuckDB cases additionally check, on 30 random instances in six physical orders each, that no
certified execution diverged or failed (0 of 75 cases) and that all eight designated order-dependent raw queries
diverged.
