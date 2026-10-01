"""E1d: property-based soundness testing of certify.py on randomly generated schemas, instances and queries.

Complements the hand-written adversarial suite (adversarial.py). For each seeded random schema (3-5 tables with a
declared single or composite key, sometimes an extra keyless table; INTEGER, DECIMAL(10,2), VARCHAR over small
alphabets, DATE, DOUBLE with -0.0/0.0, BOOLEAN; nullable non-key columns; FK-like integer columns with duplicates)
the generator draws random queries covering the fragment F of refine-logs/METHOD_FORMAL.md and its boundary
(out-of-fragment constructs, which must be UNSUPPORTED), and random small instances with heavy ties. Queries that
DuckDB rejects semantically (binder/parser errors) on the first instance are discarded and counted.

Every query is certified. A certified query (DET: unchanged; NARROW/ALL: `rewritten`) is executed under several
equivalent executions of each instance; checks (soundness violations if any fails):
  cert_div   the canonical observation (header, row count, first 20 rows rendered with tool.canon) differs among
             the certified query's successful executions;
  cert_fail  in some execution the raw query succeeds and the certified query fails;
  g2_bag     without LIMIT/OFFSET the rewrite returns a different bag than the raw query (G2);
  g2_header  the rewrite's header differs from the raw query's header in the same execution (any LIMIT/OFFSET);
  g2_limit   with LIMIT/OFFSET the rewrite's rows are not a sub-bag of the raw query's unlimited result, or the
             count is not min(L, max(n - O, 0)).
Raw-query divergence is recorded as the test's power.

DuckDB executions per instance: 3 shuffled insertion orders x threads 1/4, plus two more shuffles with
preserve_insertion_order=false (threads 4) and debug_force_external=true (threads 1).
PostgreSQL executions per instance: 3 heap (insertion) orders x serial / parallel-enabled
(max_parallel_workers_per_gather 4, parallel costs zeroed); queries are transpiled with pg_cost.to_pg and certified
in the postgres dialect (as replay_pg.py does); private server from pg_setup.py under runs/obsdet/pg/<server>/.

Usage:
  python proptest.py duck <out_dir> <seed_lo> <seed_hi> [--queries 25] [--instances 10] [--workers 16]
  python proptest.py pg   <out_dir> <seed_lo> <seed_hi> [--queries 25] [--instances 4] [--server proptest]
  python proptest.py summary <out_dir>
  add --certify <path/to/certify.py> to test another certifier revision (default: certify.py next to this file)
  python proptest.py reduce <violations.jsonl> <out.json>      minimal DuckDB instances for cert_div violations
"""
import argparse
import datetime
import glob
import hashlib
import json
import multiprocessing as mp
import os
import random
import signal
import sys
import threading
import time
from collections import Counter
from decimal import Decimal

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from certify import certify  # noqa: E402
from tool import canon  # noqa: E402

K = 20  # preview rows
TIMEOUT = 20  # seconds per statement
CERTIFIED = ("DET", "NARROW", "ALL")
TYPES = {"INT": "INTEGER", "DEC": "DECIMAL(10,2)", "TEXT": "VARCHAR", "DATE": "DATE", "DBL": "DOUBLE",
         "BOOL": "BOOLEAN"}
PGTYPES = {"INT": "integer", "DEC": "numeric(10,2)", "TEXT": "text", "DATE": "date", "DBL": "double precision",
           "BOOL": "boolean"}
CLASSES = list(TYPES)
COL_CLASSES = ["INT", "INT", "DEC", "TEXT", "TEXT", "DATE", "DBL", "DBL", "BOOL"]
D0 = datetime.date(2026, 1, 1)
TEXTS = ["a", "b", "A", "B", "ab", "aB", "", "b ", "ba", "1", "01"]
KEYTEXTS = ["a", "b", "A", "B", "ab", "aB", "ba", "bb", "c", "C", "k1", "k2", "k10", "K1", "x", "y", "z", "zz", "aa",
            "b "]
DECS = [Decimal(s) for s in ("-1.50", "0.00", "0.50", "1.00", "1.25", "2.00", "10.00")]
DATES = [D0 + datetime.timedelta(days=i) for i in (0, 1, 31, 365)]
DBLS = [1.5, -1.5, 2.0, 0.25]
LITS = {"INT": [0, 1, 2, 3, -1], "DEC": DECS, "TEXT": TEXTS, "DATE": DATES, "DBL": [0.0, -0.0, 1.5],
        "BOOL": [True, False], "TS": ["TIMESTAMP '2018-03-11 03:30:00'"]}
NAMES = ["name", "x", "y", "v", "amt", "flag", "s", "n", "d", "w", "id"]
KEY_KINDS = ["int", "int", "int", "text", "date", "int_int", "int_text"]
KEY_COLS = {"int": [("id", "INT")], "text": [("code", "TEXT")], "date": [("d", "DATE")],
            "int_int": [("id", "INT"), ("n", "INT")], "int_text": [("id", "INT"), ("s", "TEXT")], None: []}
SIZES = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20]
CMP = ["=", "<>", "<", "<=", ">", ">="]
OOF = ["window", "derived", "setop", "cte", "left", "using", "natural", "volatile", "orderagg", "groupall",
       "distinct_on", "nested_limit", "unknown_func", "qualify"]
PLAIN_OOF = ("window", "volatile", "unknown_func", "distinct_on", "qualify")
SPEC_UNSUPPORTED = ("agg:sum:dbl", "agg:avg:dbl", "group:dbl")  # in-fragment syntax the spec excludes
PRED = (["const_eq", "isnull", "col_eq", "cmp_const", "between", "in_list", "in_sub", "exists", "scalar_cmp", "or",
         "expr_eq"], [22, 8, 14, 14, 4, 5, 8, 8, 5, 7, 5])
PRED_SIMPLE = (["const_eq", "isnull", "col_eq", "cmp_const", "in_list", "expr_eq"], [30, 10, 20, 25, 5, 10])
EXPR_KINDS = {"INT": ["arith", "arith", "mod", "length", "year", "cast", "cast", "cast_text", "abs", "sign", "case",
                      "coalesce"],
              "DEC": ["arith", "mul", "round", "cast", "abs", "case", "coalesce"],
              "DBL": ["div", "cast", "arith", "round", "abs", "recip", "case", "coalesce"],
              "TEXT": ["lower", "substring", "concat", "cast", "trim", "left", "case", "coalesce"],
              "DATE": ["add", "case", "coalesce"],
              "BOOL": ["cmp", "cmp", "isnull", "not", "andor"]}
# generator v2 (--gen v2): more functions and shapes; v1 draws are unchanged when v2 is off
EXPR_KINDS_V2 = {k: v + extra for (k, v), extra in zip(EXPR_KINDS.items(), [
    ["intdiv", "strpos", "datediff", "extract", "greatest", "floor"],
    ["floor", "greatest", "nullif"],
    ["sci", "sci", "ln", "sqrt", "pow", "mixed", "mixed"],
    ["replace", "split_part", "concat_fn", "concat_ws", "right", "strftime", "substr2", "if", "dcast"],
    ["date_trunc"],
    ["like", "in_list", "between", "regexp"]])}
OOF_V2 = OOF + ["collate", "percent_limit", "sample", "nested_window", "rollup"]
# generator v3 (--gen v3): v2 + DuckDB syntax whose sqlglot regeneration (the NARROW/ALL rewrite) may differ
EXPR_KINDS_V3 = {k: v + extra for (k, v), extra in zip(EXPR_KINDS_V2.items(), [
    ["position", "extract_from", "simple_case", "bitop", "round1"],
    ["mod_dec", "round0", "neg_cast"],
    ["pow_op", "pow_op", "log2arg"],
    ["typed_cast", "typed_cast", "substr_from", "trim_both", "simple_case", "ifnull"],
    ["typed_cast", "interval", "date_add"],
    ["distinct_from", "is_true", "not_prec", "glob", "similar"]])}
# generator v4 (--gen v4): v3 + literals whose DuckDB type differs from their sqlglot parse (typed literal then ::,
# literals beyond DECIMAL(38) / HUGEINT, hex and underscore literals), also injected into SUM/AVG arguments
FLOAT_LITS = ["DECIMAL '0.1'::DOUBLE", "INTEGER '2'::DOUBLE", "BIGINT '3'::REAL", "DECIMAL '1.25'::FLOAT",
              "0.1000000000000000000000000000000000000001", "100000000000000000000000000000000000000001"]
EXPR_KINDS_V4 = {k: v + extra for (k, v), extra in zip(EXPR_KINDS_V3.items(), [
    ["hex_lit", "underscore_lit"], ["typed_cast_exact"], ["float_lit", "float_lit"], [], [], []])}
# generator v5 (--gen v5): v4 + columns near the precision limits and cross-type numeric constants/equalities
# (BIGINT near 2^53 vs e-notation literals, UBIGINT near 2^64, DECIMAL(38,0) vs DECIMAL(38,10), DOUBLE near 2^53);
# drawn from separate random streams, so v1-v4 schemas and instances are unchanged
V5_COLS = [("big", "BIGINT", "bigint", "INT", 0.6, [9007199254740992, 9007199254740993, 9007199254740994, 1, 2]),
           ("ub", "UBIGINT", "numeric(20,0)", "INT", 0.3, [18446744073709551615, 18446744073709551614, 1]),
           ("d38a", "DECIMAL(38,0)", "numeric(38,0)", "DEC", 0.4,
            [Decimal("12345678901234567890123456789012345678"), Decimal("12345678901234567890123456789012345679"),
             Decimal("1234567890123456789012345678"), Decimal("1234567890123456789012345679"), Decimal(5)]),
           ("d38b", "DECIMAL(38,10)", "numeric(38,10)", "DEC", 0.4,
            [Decimal("1234567890123456789012345678.0000000000"), Decimal("1234567890123456789012345678.5000000000"),
             Decimal("5.0000000000")]),
           ("dbl53", "DOUBLE", "double precision", "DBL", 0.4, [9007199254740992.0, 9007199254740994.0, 1.0])]
ENOT = {"INT": ["9007199254740992e0", "9.007199254740993e15", "18446744073709551615e0", "1e0"],
        "DEC": ["1.2345678901234568e27", "1.2345678901234568e37", "5e0"]}
# generator v6 (--gen v6): v5 + TIMESTAMP vs TIMESTAMPTZ around the 2018 America/New_York DST changes (session
# TimeZone America/New_York on both engines) and CHAR(3) vs VARCHAR values with trailing blanks
V6_COLS = [("ts", "TIMESTAMP", "timestamp", "TS", 0.5,
            ["2018-03-11 02:30:00", "2018-03-11 03:30:00", "2018-03-11 01:30:00", "2018-11-04 01:30:00"],
            ["TIMESTAMP '2018-03-11 02:30:00'", "TIMESTAMP '2018-03-11 03:30:00'", "TIMESTAMP '2018-11-04 01:30:00'"]),
           ("tz", "TIMESTAMP WITH TIME ZONE", "timestamptz", "TS", 0.5,
            ["2018-03-11 07:30:00+00", "2018-03-11 06:30:00+00", "2018-11-04 05:30:00+00", "2018-11-04 06:30:00+00"],
            ["TIMESTAMPTZ '2018-03-11 07:30:00+00'", "TIMESTAMPTZ '2018-11-04 06:30:00+00'"]),
           ("ch", "CHAR(3)", "character(3)", "TEXT", 0.4, ["a", "a ", "b", "ab"], None),
           ("vc", "VARCHAR", "varchar", "TEXT", 0.4, ["a", "a ", "a  ", "b"], None)]
SESSION_V6 = ["SET TimeZone = 'America/New_York'"]
V4_KINDS = {"hex_lit", "underscore_lit", "typed_cast_exact", "float_lit"}
V3_KINDS = {"position", "extract_from", "bitop", "round1", "mod_dec", "round0", "neg_cast", "pow_op", "log2arg",
            "typed_cast", "substr_from", "trim_both", "simple_case", "ifnull", "interval", "date_add",
            "distinct_from", "is_true", "not_prec", "glob", "similar"}
SCI = ["1e-1", "2.5e0", "1e0", "3e-1"]
DUCK_EXECS = [(p, th, "") for p in range(3) for th in (1, 4)] + [
    (3, 4, "SET preserve_insertion_order=false"), (4, 1, "SET debug_force_external=true")]
N_HEAP = 3
PARALLEL = ["SET parallel_setup_cost = 0", "SET parallel_tuple_cost = 0", "SET min_parallel_table_scan_size = 0",
            "SET min_parallel_index_scan_size = 0"]
DUCK_SEMANTIC = ("BinderException", "ParserException", "CatalogException", "NotImplementedException")
MAX_VIOL_PER_KIND = 5  # detailed violation records kept per schema and kind (all are counted)


CERTIFY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certify.py")
CERTIFY_MD5 = hashlib.md5(open(CERTIFY_PATH, "rb").read()).hexdigest()  # the file imported above


def use_certifier(path, expect_md5=None):
    """Test the certifier at an explicit path instead of the certify.py next to this file. The md5 is taken of the
    exact bytes that are executed; with expect_md5 a different file is refused."""
    global certify, CERTIFY_PATH, CERTIFY_MD5
    import types
    src = open(path, "rb").read()
    md5 = hashlib.md5(src).hexdigest()
    if expect_md5 and not md5.startswith(expect_md5):
        raise SystemExit(f"certifier {path} has md5 {md5}, expected {expect_md5}")
    mod = types.ModuleType("certify_under_test")
    mod.__file__ = os.path.abspath(path)
    sys.modules["certify_under_test"] = mod  # dataclasses look the module up
    exec(compile(src, path, "exec"), mod.__dict__)
    certify, CERTIFY_PATH, CERTIFY_MD5 = mod.certify, os.path.abspath(path), md5
    return mod


def certifier_id():
    return {"certify": CERTIFY_PATH, "certify_md5": CERTIFY_MD5}


# ------------------------------------------------------------------------------------------ schema and instances
def domain(r, cls):
    if cls == "INT":
        return r.sample(range(-2, 9), r.randint(2, 5))
    if cls == "DEC":
        return r.sample(DECS, r.randint(2, 4))
    if cls == "TEXT":
        return r.sample(TEXTS, r.randint(2, 5))
    if cls == "DATE":
        return r.sample(DATES, r.randint(2, 3))
    if cls == "DBL":
        return [0.0, -0.0] + r.sample(DBLS, r.randint(0, 2)) + ([float("nan")] if r.random() < 0.1 else [])
    return [True, False]


def gen_schema(seed, gen="v1"):
    r = random.Random(f"schema-{seed}")
    n_keyed = r.randint(3, 5)
    S = {"seed": seed, "tables": {}, "meta": {}}
    for ti in range(n_keyed + (r.random() < 0.3)):
        t = f"t{ti}"
        kind = r.choice(KEY_KINDS) if ti < n_keyed else None
        cols = {c: {"cls": cls, "null": False, "gen": "key"} for c, cls in KEY_COLS[kind]}
        keys = [[c for c, _ in KEY_COLS[kind]]] if kind else []
        if kind and r.random() < 0.2:  # an alternate unique key
            cols["u"] = {"cls": "TEXT", "null": False, "gen": "alt"}
            keys.append(["u"])
        for tj in range(ti):  # FK-like columns to earlier tables with a single INTEGER key
            if S["meta"][f"t{tj}"]["kind"] == "int" and r.random() < 0.5:
                cols[f"t{tj}_id"] = {"cls": "INT", "null": r.random() < 0.4, "gen": "fk", "ref": f"t{tj}"}
        for c in r.sample([n for n in NAMES if n not in cols], r.randint(3, 5)):
            cls = r.choice(COL_CLASSES)
            cols[c] = {"cls": cls, "null": r.random() < 0.5, "gen": "dom", "dom": domain(r, cls)}
        S["meta"][t] = {"kind": kind, "cols": cols}
        S["tables"][t] = {"columns": {c: TYPES[m["cls"]] for c, m in cols.items()}, "keys": keys}
    if gen == "v6":
        r6 = random.Random(f"schema6-{seed}")
        S["session"] = SESSION_V6
        for t, m in S["meta"].items():
            for name, duck, pg, cls, p, dom, lits in V6_COLS:
                if r6.random() < p:
                    m["cols"][name] = {"cls": cls, "null": r6.random() < 0.3, "gen": "dom5", "dom": dom, "type": duck,
                                       "pgtype": pg, **({"lits": lits} if lits else {})}
                    S["tables"][t]["columns"][name] = duck
    if gen in ("v5", "v6"):
        r5 = random.Random(f"schema5-{seed}")
        for t, m in S["meta"].items():
            for name, duck, pg, cls, p, dom in V5_COLS:
                if r5.random() < p:
                    m["cols"][name] = {"cls": cls, "null": r5.random() < 0.3, "gen": "dom5", "dom": dom, "type": duck,
                                       "pgtype": pg}
                    S["tables"][t]["columns"][name] = duck
    return S


def gen_instance(S, key):
    r = random.Random(f"inst-{key}")
    r5 = random.Random(f"inst5-{key}")
    inst, ids = {}, {}
    for t, m in S["meta"].items():
        n, kind = r.choice(SIZES), m["kind"]
        if kind == "int":
            kv = [(v,) for v in r.sample(range(1, 41), n)]
        elif kind == "text":
            kv = [(v,) for v in r.sample(KEYTEXTS, n)]
        elif kind == "date":
            kv = [(D0 + datetime.timedelta(days=v),) for v in r.sample(range(60), n)]
        elif kind == "int_int":
            kv = r.sample([(i, j) for i in range(1, 8) for j in range(1, 4)], n)
        elif kind == "int_text":
            kv = r.sample([(i, s) for i in range(1, 8) for s in ("a", "b", "A")], n)
        else:
            kv = [()] * n
        keycols = [c for c, cm in m["cols"].items() if cm["gen"] == "key"]
        alt = r.sample(KEYTEXTS, n)
        rows = []
        for j in range(n):
            row = []
            for c, cm in m["cols"].items():
                g = cm["gen"]
                if g == "dom5":  # v5 columns: separate stream, so the v1-v4 values are unchanged
                    v = None if cm["null"] and r5.random() < 0.2 else r5.choice(cm["dom"])
                elif g == "key":
                    v = kv[j][keycols.index(c)]
                elif g == "alt":
                    v = alt[j]
                elif cm["null"] and r.random() < 0.2:
                    v = None
                elif g == "fk":
                    v = r.choice(ids.get(cm["ref"]) or [99]) if r.random() < 0.85 else 99
                else:
                    v = r.choice(cm["dom"])
                row.append(v)
            rows.append(tuple(row))
        inst[t] = rows
        if kind == "int":
            ids[t] = [k[0] for k in kv]
    for t, spec in S["tables"].items():  # declared keys are unique and non-null on every instance
        names = list(spec["columns"])
        for k in spec["keys"]:
            vals = [tuple(row[names.index(c)] for c in k) for row in inst[t]]
            assert all(v is not None for kv in vals for v in kv) and len(set(vals)) == len(vals), (t, k)
    return inst


def lit_sql(cls, v):
    if cls == "TEXT":
        return "'" + v.replace("'", "''") + "'"
    if cls == "DATE":
        return f"DATE '{v.isoformat()}'"
    if cls == "DBL":
        return f"CAST('{v!r}' AS DOUBLE)"
    if cls == "BOOL":
        return "TRUE" if v else "FALSE"
    return str(v)


def jv(v):
    """JSON form of a value for repro files (keeps -0.0, NaN, decimals and dates)."""
    if isinstance(v, float):
        return {"double": repr(v)}
    if isinstance(v, Decimal):
        return {"decimal": str(v)}
    if isinstance(v, datetime.date):
        return {"date": v.isoformat()}
    return v


# ------------------------------------------------------------------------------------------------ query generator
class Col:
    __slots__ = ("alias", "name", "cls", "table")

    def __init__(self, alias, name, cls, table):
        self.alias, self.name, self.cls, self.table = alias, name, cls, table


class QGen:
    """One random query over schema S in DuckDB syntax; `tags` records the constructs used (coverage)."""

    def __init__(self, S, r, gen="v1"):
        self.S, self.r, self.tags, self.nsub, self.outer, self.scope, self.oof = S, r, set(), 0, True, [], None
        self.v2, self.v3 = gen in ("v2", "v3", "v4", "v5", "v6"), gen in ("v3", "v4", "v5", "v6")
        self.v4 = gen in ("v4", "v5", "v6")
        self.v5, self.v6, self.inner = gen in ("v5", "v6"), gen == "v6", []

    def tag(self, *ts):
        self.tags.update(ts)

    def cols(self, t, alias):
        return [Col(alias, c, m["cls"], t) for c, m in self.S["meta"][t]["cols"].items()]

    def ref(self, c):
        if self.outer and self.r.random() < 0.1 and sum(x.name == c.name for x in self.scope) == 1:
            self.tag("ref:unqualified")
            return c.name
        if (self.v2 and not self.outer and c in self.inner and sum(x.name == c.name for x in self.inner) == 1
                and self.r.random() < 0.3):
            self.tag("ref:unqualified_in_subquery")
            return c.name
        return f"{c.alias}.{c.name}"

    def meta(self, c):
        return self.S["meta"][c.table]["cols"][c.name]

    def lit(self, cls, col=None):
        r = self.r
        m = self.meta(col) if col is not None else None
        if m is not None and "lits" in m:  # temporal columns of generator v6: typed literals
            return r.choice(m["lits"])
        if m is not None and m["gen"] in ("dom", "dom5") and r.random() < 0.85:
            v = r.choice(m["dom"])
        elif m is not None and m["gen"] in ("key", "fk", "alt") and r.random() < 0.85:
            v = {"INT": r.randint(1, 12), "TEXT": r.choice(KEYTEXTS[:8]),
                 "DATE": D0 + datetime.timedelta(days=r.randrange(8))}[cls]
        else:
            v = r.choice(LITS[cls])
        return lit_sql(cls, v)

    def fk_pair(self, a, b):
        """a is an FK-like column referencing b's table and b is that table's single INTEGER key."""
        m = self.meta(a)
        return (m["gen"] == "fk" and m["ref"] == b.table and b.name == "id"
                and self.S["meta"][b.table]["kind"] == "int")

    # ---- scalar expressions
    def expr(self, scope, cls, depth=0):
        r = self.r
        if depth >= 2 or cls not in EXPR_KINDS or r.random() < 0.5:  # classes without expression kinds (TS): leaf
            cands = [c for c in scope if c.cls == cls]
            if cands and r.random() < 0.9:
                return self.ref(r.choice(cands))
            return self.lit(cls)

        def e(k):
            return self.expr(scope, k, depth + 1)

        kind = r.choice((EXPR_KINDS_V4 if self.v4 else EXPR_KINDS_V3 if self.v3 else EXPR_KINDS_V2 if self.v2
                         else EXPR_KINDS)[cls])
        self.tag(f"expr:{cls.lower()}:{kind}")
        if kind in V4_KINDS:
            return {"hex_lit": lambda: f"({e('INT')} + 0x{r.choice(['1', 'A', '10'])})",
                    "underscore_lit": lambda: f"({e('INT')} + 1_000)",
                    "typed_cast_exact": lambda: f"({e('DEC')} + DOUBLE '0.5'::DECIMAL(10,2))",
                    "float_lit": lambda: f"({e(r.choice(['INT', 'DEC']))} * {r.choice(FLOAT_LITS)})"}[kind]()
        if kind in V3_KINDS:
            return self.expr_v3(kind, cls, e)
        if kind in ("greatest", "floor", "nullif", "sci", "ln", "sqrt", "pow", "mixed", "replace", "split_part",
                    "concat_fn", "concat_ws", "right", "strftime", "substr2", "if", "dcast", "date_trunc", "like",
                    "in_list", "between", "regexp", "intdiv", "strpos", "datediff", "extract"):
            return self.expr_v2(kind, cls, e)
        if kind == "case":
            return f"CASE WHEN {e('BOOL')} THEN {e(cls)} ELSE {e(cls)} END"
        if kind == "coalesce":
            return f"COALESCE({e(cls)}, {self.lit(cls)})"
        if kind == "abs":
            return f"ABS({e(cls)})"
        if cls == "INT":
            if kind == "arith":
                return f"({e('INT')} {r.choice('+-*')} {e('INT')})"
            if kind == "mod":
                return f"({e('INT')} % {r.choice([2, 3])})"
            if kind == "length":
                return f"LENGTH({e('TEXT')})"
            if kind == "year":
                return f"{r.choice(['YEAR', 'MONTH'])}({e('DATE')})"
            if kind == "cast":
                return f"CAST({e(r.choice(['DEC', 'DBL', 'BOOL']))} AS INTEGER)"
            if kind == "cast_text":
                return f"{r.choice(['CAST', 'TRY_CAST'])}({e('TEXT')} AS INTEGER)"
            return f"SIGN({e('DBL')})"
        if cls == "DEC":
            if kind == "arith":
                return f"({e('DEC')} {r.choice('+-')} {e(r.choice(['DEC', 'INT']))})"
            if kind == "mul":
                return f"({e('DEC')} * {e('INT')})"
            if kind == "round":
                return f"ROUND({e('DEC')}, {r.choice([0, 1])})"
            return f"CAST({e(r.choice(['INT', 'DBL']))} AS DECIMAL(10,2))"
        if cls == "DBL":
            if kind == "div":
                return f"({e(r.choice(['INT', 'DEC']))} / {e(r.choice(['INT', 'DEC']))})"
            if kind == "cast":
                return f"CAST({e(r.choice(['INT', 'DEC']))} AS DOUBLE)"
            if kind == "arith":
                return f"({e('DBL')} {r.choice('+-*')} {e(r.choice(['DBL', 'INT']))})"
            if kind == "round":
                return f"ROUND({e('DBL')}, 1)"
            return f"(1 / {e('DBL')})"
        if cls == "TEXT":
            if kind == "lower":
                return f"{r.choice(['LOWER', 'UPPER'])}({e('TEXT')})"
            if kind == "substring":
                return f"SUBSTRING({e('TEXT')}, 1, {r.choice([1, 2])})"
            if kind == "concat":
                return f"({e('TEXT')} || {e('TEXT')})"
            if kind == "cast":
                k = r.choice(["INT", "DEC", "DBL", "DATE", "BOOL"])
                self.tag(f"expr:text:cast_from_{k.lower()}")
                return f"CAST({e(k)} AS VARCHAR)"
            if kind == "trim":
                return f"TRIM({e('TEXT')})"
            return f"LEFT({e('TEXT')}, 1)"
        if cls == "DATE":
            return f"({e('DATE')} + {r.choice([1, 30])})"
        if kind == "cmp":
            k = r.choice(["INT", "DEC", "TEXT", "DATE", "DBL"])
            return f"({e(k)} {r.choice(CMP)} {e(k)})"
        if kind == "isnull":
            return f"({e(r.choice(CLASSES))} IS {r.choice(['', 'NOT '])}NULL)"
        if kind == "not":
            return f"(NOT {e('BOOL')})"
        return f"({e('BOOL')} {r.choice(['AND', 'OR'])} {e('BOOL')})"

    def expr_v2(self, kind, cls, e):
        r = self.r
        if kind == "greatest":
            return f"{r.choice(['GREATEST', 'LEAST'])}({e(cls)}, {e(cls)})"
        if kind == "floor":
            return (f"CAST({r.choice(['FLOOR', 'CEIL'])}({e('DEC')}) AS INTEGER)" if cls == "INT"
                    else f"{r.choice(['FLOOR', 'CEIL'])}({e('DEC')})")
        if kind == "nullif":
            return f"NULLIF({e(cls)}, {self.lit(cls)})"
        if kind == "sci":
            return f"({e(r.choice(['INT', 'DEC']))} * {r.choice(SCI)})"
        if kind == "ln":
            return f"{r.choice(['LN', 'LOG', 'LOG10', 'EXP'])}(ABS({e('DEC')}) + 1)"
        if kind == "sqrt":
            return f"SQRT(ABS({e(r.choice(['INT', 'DEC', 'DBL']))}))"
        if kind == "pow":
            return f"POW({e(r.choice(['INT', 'DEC']))}, 2)"
        if kind == "mixed":  # branches of different numeric classes: the result is DOUBLE
            a, b = r.sample(["DBL", r.choice(["DEC", "INT"])], 2)
            return r.choice([f"CASE WHEN {e('BOOL')} THEN {e(a)} ELSE {e(b)} END", f"COALESCE({e(a)}, {e(b)})",
                             f"GREATEST({e(a)}, {e(b)})"])
        if kind == "replace":
            return f"REPLACE({e('TEXT')}, 'a', 'b')"
        if kind == "split_part":
            return f"SPLIT_PART({e('TEXT')}, 'a', 1)"
        if kind == "concat_fn":
            return f"CONCAT({e('TEXT')}, {e(r.choice(CLASSES))})"
        if kind == "concat_ws":
            return f"CONCAT_WS('-', {e('TEXT')}, {e('TEXT')})"
        if kind == "right":
            return f"RIGHT({e('TEXT')}, 1)"
        if kind == "strftime":
            return f"STRFTIME({e('DATE')}, '%Y-%m')"
        if kind == "substr2":
            return f"SUBSTR({e('TEXT')}, 2)"
        if kind == "if":
            return f"IF({e('BOOL')}, {e('TEXT')}, {e('TEXT')})"
        if kind == "dcast":
            return f"{e(r.choice(['INT', 'DEC', 'DATE']))}::VARCHAR"
        if kind == "date_trunc":
            return f"CAST(DATE_TRUNC('month', {e('DATE')}) AS DATE)"
        if kind == "like":
            return f"({e('TEXT')} {r.choice(['LIKE', 'ILIKE', 'NOT LIKE'])} 'a%')"
        if kind == "in_list":
            return f"({e('INT')} IN (1, 2))"
        if kind == "between":
            return f"({e('INT')} BETWEEN 0 AND 3)"
        if kind == "regexp":
            return f"REGEXP_MATCHES({e('TEXT')}, '^a')"
        if kind == "intdiv":
            return f"({e('INT')} // {r.choice([2, 3])})"
        if kind == "strpos":
            return f"STRPOS({e('TEXT')}, 'a')"
        if kind == "datediff":
            return f"DATE_DIFF('day', {e('DATE')}, {e('DATE')})"
        return f"{r.choice(['QUARTER', 'DAYOFWEEK', 'DAYOFYEAR'])}({e('DATE')})"  # extract

    def expr_v3(self, kind, cls, e):
        r = self.r
        d = r.choice(DATES).isoformat()
        if kind == "typed_cast":
            if cls == "DATE":
                return f"TIMESTAMP '{d} 10:00:00'::DATE"
            return r.choice([f"DATE '{d}'::VARCHAR", f"TIMESTAMP '{d} 10:00:00'::VARCHAR", "TIME '10:30:00'::VARCHAR"])
        if kind == "position":
            return f"POSITION('a' IN {e('TEXT')})"
        if kind == "extract_from":
            return f"EXTRACT({r.choice(['YEAR', 'MONTH', 'DAY'])} FROM {e('DATE')})"
        if kind == "simple_case":
            if cls == "INT":
                return f"CASE {e('TEXT')} WHEN 'a' THEN 1 WHEN 'b' THEN 2 ELSE {e('INT')} END"
            return f"CASE {e('INT')} WHEN 1 THEN {e('TEXT')} ELSE {e('TEXT')} END"
        if kind == "bitop":
            return f"({e('INT')} {r.choice(['&', '|', '<<'])} {r.choice([1, 3])})"
        if kind == "round1":
            return f"CAST(ROUND({e('DEC')}) AS INTEGER)"
        if kind == "mod_dec":
            return f"({e('DEC')} % 0.75)"
        if kind == "round0":
            return f"ROUND({e('DEC')})"
        if kind == "neg_cast":
            return f"-{e('INT')}::DECIMAL(10,2)"
        if kind == "pow_op":
            return f"({e(r.choice(['INT', 'DEC']))} {r.choice(['^', '**'])} 2)"
        if kind == "log2arg":
            return f"LOG(2, ABS({e('DEC')}) + 1)"
        if kind == "substr_from":
            return f"SUBSTRING({e('TEXT')} FROM 2 FOR 1)"
        if kind == "trim_both":
            return f"TRIM(BOTH 'a' FROM {e('TEXT')})"
        if kind == "ifnull":
            return f"IFNULL({e('TEXT')}, 'z')"
        if kind == "interval":
            iv = r.choice(["1 DAY", "'1' MONTH"])
            return f"CAST({e('DATE')} {r.choice(['+', '-'])} INTERVAL {iv} AS DATE)"
        if kind == "date_add":
            return f"CAST(DATE_ADD({e('DATE')}, INTERVAL 1 DAY) AS DATE)"
        if kind == "distinct_from":
            k = r.choice(["INT", "TEXT", "DATE", "DEC"])
            return f"({e(k)} IS {r.choice(['', 'NOT '])}DISTINCT FROM {e(k)})"
        if kind == "is_true":
            return f"({e('BOOL')} IS {r.choice(['TRUE', 'FALSE', 'NOT TRUE'])})"
        if kind == "not_prec":
            return f"(NOT {e('INT')} = {e('INT')})"
        if kind == "glob":
            return f"({e('TEXT')} GLOB 'a*')"
        return f"({e('TEXT')} SIMILAR TO 'a%')"  # similar

    # ---- aggregates
    def agg(self, scope):
        r = self.r
        kind = r.choice(["count_star", "count", "count_distinct", "min", "max", "min", "max", "sum", "sum", "avg"])
        if kind == "count_star":
            self.tag("agg:count_star")
            return "COUNT(*)", "INT"
        k = r.choice(["INT", "INT", "DEC", "DEC", "DBL"]) if kind in ("sum", "avg") else r.choice(CLASSES)
        a = self.expr(scope, k, 1)
        if self.v4 and kind in ("sum", "avg") and self.r.random() < 0.15:
            a = f"({self.expr(scope, r.choice(['INT', 'DEC']), 1)} * {r.choice(FLOAT_LITS)})"
            k = "DBL"
            self.tag("agg:arg_float_literal")
        self.tag(f"agg:{kind}", f"agg:{kind}:{k.lower()}")
        if kind in ("sum", "avg") and "/" in a:
            self.tag("agg:arg_has_division")
        if self.v2 and kind in ("sum", "avg", "min", "max", "count") and self.r.random() < 0.1:
            self.tag("agg:filter")
            f = f" FILTER (WHERE {self.pred(scope, 1)})"
            if kind == "avg":
                return f"AVG({a}){f}", "DBL"
            return f"{kind.upper()}({a}){f}", ("INT" if kind == "count" else k)
        if kind == "count":
            return f"COUNT({a})", "INT"
        if kind == "count_distinct":
            return f"COUNT(DISTINCT {a})", "INT"
        if kind == "avg":
            return f"AVG({a})", "DBL"
        return f"{kind.upper()}({a})", k

    def agg_out(self, scope):
        a, k = self.agg(scope)
        if self.r.random() < 0.25:
            opts = ["cast_text", "coalesce"] + (["plus", "recip", "round", "case"] if k in ("INT", "DEC", "DBL") else [])
            w = self.r.choice(opts)
            self.tag(f"agg:wrap:{w}", f"agg:wrap:{k.lower()}")
            if w == "cast_text":
                return f"CAST({a} AS VARCHAR)", "TEXT"
            if w == "coalesce":
                return f"COALESCE({a}, {self.lit(k)})", k
            if w == "plus":
                return f"({a} + 1)", k
            if w == "recip":
                return f"(1 / {a})", "DBL"
            if w == "round":
                return f"ROUND({a}, 1)", ("DBL" if k == "DBL" else "DEC")
            return f"CASE WHEN {a} > 1 THEN 'hi' ELSE 'lo' END", "TEXT"
        return a, k

    # ---- subqueries
    def sub_scope(self):
        t = self.r.choice(list(self.S["meta"]))
        b = f"s{self.nsub}"
        self.nsub += 1
        self.inner = self.cols(t, b)
        return t, b, self.inner

    def corr(self, inner, outer):
        """An equality correlating an inner alias with the outer scope, preferring FK -> key pairs."""
        fk = [(i, o) for i in inner for o in outer if self.fk_pair(i, o) or self.fk_pair(o, i)]
        same = [(i, o) for i in inner for o in outer if i.cls == o.cls and i.cls != "BOOL"]
        pairs = fk if fk and self.r.random() < 0.7 else same
        if not pairs:
            return None
        i, o = self.r.choice(pairs)
        return f"{i.alias}.{i.name} = {o.alias}.{o.name}"

    def scalar_sub(self, scope):
        r = self.r
        t, b, inner = self.sub_scope()
        saved, self.outer = self.outer, False
        kind = r.choice(["agg_corr", "agg_corr", "agg_uncorr", "key_lookup", "multi_row"])
        keys = self.S["tables"][t]["keys"]
        if kind == "key_lookup" and not (keys and len(keys[0]) == 1):
            kind = "agg_corr"
        cond = self.corr(inner, scope)
        if kind in ("agg_corr", "agg_uncorr"):
            a, k = self.agg(inner)
            sql = f"(SELECT {a} FROM {t} {b}" + (f" WHERE {cond})" if kind == "agg_corr" and cond else ")")
        elif kind == "key_lookup":
            key = keys[0][0]
            kc = next(c for c in inner if c.name == key)
            outer = [c for c in scope if c.cls == kc.cls]
            o = r.choice(outer) if outer else None
            rhs = f"{o.alias}.{o.name}" if o else self.lit(kc.cls, kc)
            c = r.choice(inner)
            k = c.cls
            sql = f"(SELECT {b}.{c.name} FROM {t} {b} WHERE {b}.{key} = {rhs})"
        else:
            c = r.choice(inner)
            k = c.cls
            sql = f"(SELECT {b}.{c.name} FROM {t} {b}" + (f" WHERE {cond})" if cond else ")")
        self.outer = saved
        self.tag("subq:scalar", f"subq:scalar:{kind}")
        return sql, k

    # ---- predicates
    def pred(self, scope, depth=0):
        r = self.r
        kinds, weights = PRED if depth == 0 else PRED_SIMPLE
        kind = r.choices(kinds, weights)[0]
        c = r.choice(scope)
        if self.v6 and r.random() < 0.3:
            eq = self.v6_pairs(scope, scope)
            if eq:
                a, b, k = r.choice(eq)
                self.tag(f"where:{k}_eq")
                return f"{self.ref(a)} = {self.ref(b)}"
        if self.v5 and r.random() < 0.2:
            num = [x for x in scope if x.cls in ("INT", "DEC")]
            if num:
                c = r.choice([x for x in num if self.meta(x)["gen"] == "dom5"] or num)
                self.tag("where:const_enotation", f"where:const_enotation:{c.cls.lower()}")
                return f"{self.ref(c)} = {r.choice(ENOT[c.cls])}"
        if kind == "col_eq":
            pairs = [(x, y) for x in scope for y in scope if x is not y and
                     (x.cls == y.cls or {x.cls, y.cls} <= {"INT", "DEC", "DBL"} or {x.cls, y.cls} == {"INT", "TEXT"})]
            if not pairs:
                kind = "cmp_const"
            else:
                x, y = r.choice(pairs)
                self.tag("where:col_eq", f"where:col_eq:{'-'.join(sorted({x.cls, y.cls})).lower()}",
                         "where:col_eq:" + ("same_alias" if x.alias == y.alias else "cross_alias"))
                return f"{self.ref(x)} = {self.ref(y)}"
        self.tag(f"where:{kind}")
        if kind == "const_eq":
            self.tag(f"where:const_eq:{c.cls.lower()}")
            return f"{self.ref(c)} = {self.lit(c.cls, c)}"
        if kind == "isnull":
            return f"{self.ref(c)} IS {r.choice(['', 'NOT '])}NULL"
        if kind in ("cmp_const", "between", "in_list"):
            c = r.choice([x for x in scope if x.cls != "BOOL"] or scope)
            if kind == "cmp_const":
                return f"{self.ref(c)} {r.choice(CMP)} {self.lit(c.cls, c)}"
            if kind == "between":
                return f"{self.ref(c)} BETWEEN {self.lit(c.cls, c)} AND {self.lit(c.cls, c)}"
            return f"{self.ref(c)} {r.choice(['IN', 'NOT IN'])} ({self.lit(c.cls, c)}, {self.lit(c.cls, c)})"
        if kind == "expr_eq":
            k = r.choice(CLASSES)
            return f"{self.expr(scope, k, 1)} = {self.lit(k)}"
        if kind == "or":
            return f"({self.pred(scope, depth + 1)} OR {self.pred(scope, depth + 1)})"
        if kind == "scalar_cmp":
            sub, k = self.scalar_sub(scope)
            outer = [x for x in scope if x.cls == k]
            return f"{self.ref(r.choice(outer))} {r.choice(CMP)} {sub}" if outer else f"{sub} IS NOT NULL"
        t, b, inner = self.sub_scope()
        saved, self.outer = self.outer, False
        try:
            if kind == "in_sub":
                ic = [x for x in inner if x.cls == c.cls]
                if not ic:
                    return f"{c.alias}.{c.name} IS NOT NULL"
                w = f" WHERE {self.pred(inner, depth + 1)}" if r.random() < 0.4 else ""
                dist = "DISTINCT " if r.random() < 0.2 else ""
                return (f"{c.alias}.{c.name} {r.choice(['IN', 'NOT IN'])} "
                        f"(SELECT {dist}{b}.{r.choice(ic).name} FROM {t} {b}{w})")
            conds = [self.corr(inner, scope)] + ([self.pred(inner, depth + 1)] if r.random() < 0.4 else [])
            conds = [x for x in conds if x]
            return f"{r.choice(['', 'NOT '])}EXISTS (SELECT 1 FROM {t} {b} WHERE {' AND '.join(conds) or 'TRUE'})"
        finally:
            self.outer = saved

    def v6_pairs(self, left, right):
        """TIMESTAMP = TIMESTAMPTZ and CHAR(3) = VARCHAR pairs (generator v6)."""
        pick = lambda cols, n: [x for x in cols if x.name == n]  # noqa: E731
        return ([(a, b, "ts_tz") for a in pick(left, "ts") for b in pick(right, "tz")]
                + [(a, b, "ts_tz") for a in pick(left, "tz") for b in pick(right, "ts")]
                + [(a, b, "char_varchar") for a in pick(left, "ch") for b in pick(right, "vc")]
                + [(a, b, "char_varchar") for a in pick(left, "vc") for b in pick(right, "ch")])

    # ---- FROM
    def join_cond(self, left, right, kind):
        r = self.r
        if self.v6 and kind in ("key", "eq") and r.random() < 0.5:
            eq = self.v6_pairs(left, right)
            if eq:
                x, y, k = r.choice(eq)
                self.tag(f"join:on_{k}")
                return f"{x.alias}.{x.name} = {y.alias}.{y.name}"
        if kind == "key":
            pairs = [(x, y) for x in left for y in right if self.fk_pair(x, y) or self.fk_pair(y, x)]
            if pairs:
                x, y = r.choice(pairs)
                self.tag("join:on_fk_key")
                return f"{x.alias}.{x.name} = {y.alias}.{y.name}"
            kind = "eq"
        pairs = [(x, y) for x in left for y in right if x.cls == y.cls and x.cls != "BOOL"]
        if not pairs:
            return None
        x, y = r.choice(pairs)
        if kind == "eq":
            keyish = self.meta(x)["gen"] in ("key", "alt") or self.meta(y)["gen"] in ("key", "alt")
            self.tag("join:on_eq_keycol" if keyish else "join:on_eq_nonkey")
            return f"{x.alias}.{x.name} = {y.alias}.{y.name}"
        self.tag("join:on_theta")
        return f"{x.alias}.{x.name} {r.choice(['<', '<=', '>', '>=', '<>'])} {y.alias}.{y.name}"

    def from_clause(self):
        r = self.r
        tabs = list(self.S["meta"])
        n = r.choices([1, 2, 3], [45, 40, 15])[0]
        if self.oof in ("left", "using", "natural"):
            n = max(n, 2)
        t = r.choice(tabs)
        scope, sql, conds, used = self.cols(t, "a0"), f"{t} a0", [], [t]
        for i in range(1, n):
            t, a = r.choice(tabs), f"a{i}"
            new = self.cols(t, a)
            if t in used:
                self.tag("join:self")
            used.append(t)
            if i == 1 and self.oof in ("left", "using", "natural"):
                kind = self.oof
            else:
                kind = r.choices(["key", "eq", "theta", "cross", "comma"], [35, 20, 10, 10, 25])[0]
            shared = sorted({x.name for x in scope} & {y.name for y in new})
            if kind == "using" and not shared:
                kind = self.oof = "left"
            self.tag(f"oof:{kind}" if kind in ("left", "using", "natural") else f"join:{kind}")
            if kind == "cross":
                sql += f" CROSS JOIN {t} {a}"
            elif kind == "natural":
                sql += f" NATURAL JOIN {t} {a}"
            elif kind == "using":
                sql += f" JOIN {t} {a} USING ({r.choice(shared)})"
            elif kind == "comma":
                sql += f", {t} {a}"
                cond = self.join_cond(scope, new, r.choice(["key", "eq", "theta"]))
                if cond and r.random() < 0.8:
                    conds.append(cond)
            else:
                cond = self.join_cond(scope, new, "key" if kind == "left" else kind)
                sql += f" {'LEFT ' if kind == 'left' else ''}JOIN {t} {a} ON {cond or 'TRUE'}"
            scope = scope + new
        return sql, scope, conds

    # ---- SELECT list items
    def plain_out(self, scope):
        r = self.r
        x = r.random()
        if x < 0.6:
            c = r.choice(scope)
            self.tag("out:col", f"out:col:{c.cls.lower()}")
            return {"sql": self.ref(c), "cls": c.cls}
        if x < 0.9:
            k = r.choice(CLASSES)
            self.tag("out:expr")
            return {"sql": self.expr(scope, k, 0), "cls": k}
        if self.v2 and r.random() < 0.3:
            t, b, inner = self.sub_scope()
            saved, self.outer = self.outer, False
            cond = self.corr(inner, scope) or "TRUE"
            self.outer = saved
            self.tag("out:exists")
            return {"sql": f"{r.choice(['', 'NOT '])}EXISTS (SELECT 1 FROM {t} {b} WHERE {cond})", "cls": "BOOL"}
        s, k = self.scalar_sub(scope)
        self.tag("out:scalar_sub")
        return {"sql": s, "cls": k}

    def group_item(self, scope):
        r = self.r
        c = r.choice(scope)
        if r.random() < 0.7:
            self.tag("group:col", f"group:col:{c.cls.lower()}")
            g = {"sql": self.ref(c), "cls": c.cls, "col": c}
        else:
            f, k = r.choice({"TEXT": [("LOWER({})", "TEXT"), ("SUBSTRING({}, 1, 1)", "TEXT")],
                             "DATE": [("YEAR({})", "INT")], "INT": [("({} % 2)", "INT")],
                             "DEC": [("({} * 2)", "DEC"), ("CAST({} AS INTEGER)", "INT")],
                             "DBL": [("CAST({} AS INTEGER)", "INT"), ("CAST({} AS VARCHAR)", "TEXT"),
                                     ("ROUND({}, 0)", "DBL")],
                             "BOOL": [("(NOT {})", "BOOL")], "TS": [("CAST({} AS DATE)", "DATE")]}[c.cls])
            self.tag("group:expr", f"group:expr:{c.cls.lower()}->{k.lower()}")
            g = {"sql": f.format(f"{c.alias}.{c.name}"), "cls": k, "col": None}
        if g["cls"] == "DBL":
            self.tag("group:dbl")
        return g

    def window(self, scope):
        c = self.r.choice(scope)
        ref = f"{c.alias}.{c.name}"
        return {"sql": self.r.choice([f"ROW_NUMBER() OVER (ORDER BY {ref})", f"COUNT(*) OVER (PARTITION BY {ref})",
                                      f"RANK() OVER (ORDER BY {ref})", "SUM(1) OVER ()"]), "cls": "INT"}

    def orderagg(self, scope):
        r = self.r
        c, c2 = r.choice(scope), r.choice(scope)
        f = r.choice(["STRING_AGG", "FIRST", "ANY_VALUE", "LIST", "ARG_MAX"])
        self.tag(f"oof:orderagg:{f.lower()}")
        if f == "STRING_AGG":
            return {"sql": f"STRING_AGG(CAST({c.alias}.{c.name} AS VARCHAR), ',')", "cls": "TEXT"}
        if f == "ARG_MAX":
            return {"sql": f"ARG_MAX({c.alias}.{c.name}, {c2.alias}.{c2.name})", "cls": c.cls}
        return {"sql": f"{f}({c.alias}.{c.name})", "cls": c.cls}

    # ---- ORDER BY and LIMIT
    def order_by(self, outs, scope, shape, distinct, gitems, rand_order):
        r = self.r
        if r.random() > (0.1 if shape == "global" else 0.75):
            return " ORDER BY random()" if rand_order else ""
        if r.random() < 0.05 and not rand_order:
            self.tag("order:all")
            return " ORDER BY ALL" + r.choice(["", " DESC"])
        star = bool(outs[0].get("star"))
        aliased = [o for o in outs if o.get("alias")]
        kinds = ["ordinal"] + ([] if star else ["out_expr"]) + (["alias"] if aliased else [])
        if not distinct:
            kinds += {"plain": ["col", "col", "expr"], "grouped": ["grp", "agg"], "global": ["agg"]}[shape]
        elif self.v2 and shape == "plain" and r.random() < 0.4:
            kinds += ["col", "expr"]  # DISTINCT with a non-output sort key (known defect 2 shape)
        if self.v2:
            kinds += (["alias_expr"] if aliased else []) + (["sub"] if shape == "plain" and not distinct else [])
        if self.v4:  # ORDER BY binding forms: unary +/-, parentheses, case-flipped or quoted alias spellings
            kinds += ["unary", "paren"] + (["case_alias"] if any(" " not in o["alias"] for o in aliased) else [])
        names = {c.name for c in scope}
        items = []
        for _ in range(r.choice([1, 1, 1, 2, 2, 3])):
            k = r.choice(kinds)
            if k == "ordinal":
                s = str(1 if star else r.randrange(len(outs)) + 1)
            elif k == "alias":
                s = r.choice(aliased)["alias"]
                if s in names and r.random() < 0.3:
                    s, k = f"({s})", "alias_paren"
            elif k == "out_expr":
                s = r.choice(outs)["sql"]
            elif k == "col":
                s = self.ref(r.choice(scope))
            elif k == "expr":
                s = self.expr(scope, r.choice(CLASSES), 1)
            elif k == "grp":
                s = r.choice(gitems)["sql"]
            elif k == "alias_expr":
                o = r.choice(aliased)
                s = (f"({o['alias']} || '')" if o["cls"] == "TEXT" else
                     f"({o['alias']} + 0)" if o["cls"] in ("INT", "DEC", "DBL") else o["alias"])
            elif k == "sub":
                s = self.scalar_sub(scope)[0]
            elif k == "unary":
                sign, sub = r.choice(["+", "-"]), r.choice(["ordinal", "alias", "col"])
                if sub == "ordinal" or (sub == "alias" and not aliased):
                    s = f"{sign}{1 if star else r.randrange(len(outs)) + 1}"
                elif sub == "alias":
                    s = f"{sign}{r.choice(aliased)['alias']}"
                else:
                    s = f"{sign}{self.ref(r.choice([x for x in scope if x.cls in ('INT', 'DEC', 'DBL')] or scope))}"
                k = f"unary_{sub}"
            elif k == "paren":
                s = f"({r.choice([o['alias'] for o in aliased] + [str(1 if star else r.randrange(len(outs)) + 1)])})"
            elif k == "case_alias":
                a = r.choice([o["alias"] for o in aliased if " " not in o["alias"]])
                s = a.strip('"').lower() if a.startswith('"') else f'"{a.upper()}"'  # flip quoting and case
            else:
                s = self.agg(scope)[0]
            self.tag(f"order:{k}")
            if distinct and k in ("col", "expr") and s not in [o["sql"] for o in outs]:
                self.tag("known:distinct_order_nonoutput")
            d = r.choice(["", "", " ASC", " DESC", " DESC"])
            nl = r.choice(["", "", "", " NULLS FIRST", " NULLS LAST"])
            if d:
                self.tag(f"order:{d.strip().lower()}")
            if nl:
                self.tag("order:" + nl.strip().lower().replace(" ", "_"))
            items.append(s + d + nl)
        if rand_order:
            items.append("random()")
        return " ORDER BY " + ", ".join(items)

    def limit(self):
        r = self.r
        lim = off = None
        if r.random() < 0.5:
            lim = r.choice([0, 1, 1, 2, 3, 5, 10])
            if r.random() < 0.3:
                off = r.choice([1, 2, 5])
        elif r.random() < 0.05:
            off = r.choice([1, 2])
        if lim is not None:
            self.tag("limit", "limit:0" if lim == 0 else "limit")
        if off is not None:
            self.tag("offset")
        return lim, off

    # ---- whole queries
    def wrapped(self):
        """Out-of-fragment query shapes: set operations, derived tables, CTEs."""
        r, kind = self.r, self.oof
        if kind == "setop":
            present = sorted({m["cls"] for tm in self.S["meta"].values() for m in tm["cols"].values()} - {"BOOL"})
            k = r.choice(present)
            cands = [(t, c) for t, tm in self.S["meta"].items() for c, m in tm["cols"].items() if m["cls"] == k]
            parts = []
            for _ in range(2):
                t, c = r.choice(cands)
                w = f" WHERE {self.pred(self.cols(t, 'a0'), 1)}" if r.random() < 0.4 else ""
                parts.append(f"SELECT a0.{c} FROM {t} a0{w}")
            op = r.choice(["UNION", "UNION ALL", "EXCEPT", "INTERSECT"])
            self.tag(f"oof:setop:{op.lower().replace(' ', '_')}")
            body = f" {op} ".join(parts)
        else:
            t = r.choice(list(self.S["meta"]))
            cs = self.cols(t, "a0")
            picks = r.sample(cs, min(len(cs), r.randint(1, 3)))
            w = f" WHERE {self.pred(cs, 1)}" if r.random() < 0.4 else ""
            inner = f"SELECT {', '.join(f'a0.{c.name} AS c{i + 1}' for i, c in enumerate(picks))} FROM {t} a0{w}"
            body = f"SELECT * FROM ({inner}) sub" if kind == "derived" else f"WITH w AS ({inner}) SELECT * FROM w"
        order = (" ORDER BY 1" + r.choice(["", " DESC"])) if r.random() < 0.6 else ""
        lim = r.choice([None, None, 1, 3])
        return {"sql": body + order + (f" LIMIT {lim}" if lim else ""), "base": body + order, "limit": lim,
                "offset": None}

    def query(self):
        r = self.r
        self.oof = r.choice(OOF_V2 if self.v2 else OOF) if r.random() < 0.15 else None
        if self.oof and self.oof not in ("left", "using", "natural"):  # join kinds are tagged in from_clause
            self.tag(f"oof:{self.oof}")
        if self.oof in ("setop", "derived", "cte"):
            return self.wrapped()
        frm, scope, conds = self.from_clause()
        self.scope = scope
        if self.oof in ("orderagg", "groupall", "rollup"):
            shape = "grouped"
        elif self.oof in PLAIN_OOF + ("collate", "percent_limit", "sample", "nested_window"):
            shape = "plain"
        else:
            shape = r.choices(["plain", "grouped", "global"], [55, 30, 15])[0]
        self.tag(f"shape:{shape}")
        where = conds + [self.pred(scope) for _ in range(r.choice([0, 0, 1, 1, 1, 2, 3]))]
        if self.oof == "nested_window":
            t, b, inner = self.sub_scope()
            ints = [x for x in scope if x.cls == "INT"]
            w = f"(SELECT ROW_NUMBER() OVER (ORDER BY {b}.{inner[0].name}) FROM {t} {b})"
            where.append(f"{ints[0].alias}.{ints[0].name} IN {w}" if ints else f"EXISTS {w}")
        if self.oof == "nested_limit":
            t, b, inner = self.sub_scope()
            c = r.choice(scope)
            ic = [x for x in inner if x.cls == c.cls] or inner
            ic = r.choice(ic)
            if ic.cls != c.cls:
                c = r.choice([x for x in scope if x.cls == ic.cls] or [c])
            where.append(f"{c.alias}.{c.name} IN (SELECT {b}.{ic.name} FROM {t} {b} ORDER BY {b}.{ic.name} LIMIT 2)")
        outs, gitems, group, having, distinct, qualify, rand_order = [], [], "", "", "", "", False
        if shape == "plain":
            if r.random() < 0.05:
                single = self.v2 and len({c.alias for c in scope}) == 1
                st = r.choice(["*", "a0.*"] + (["* EXCLUDE", "* REPLACE"] if single else []))
                if st == "* EXCLUDE":
                    st = f"* EXCLUDE ({r.choice(scope).name})"
                    self.tag("out:star_exclude")
                elif st == "* REPLACE":
                    c = r.choice(scope)
                    st = f"* REPLACE ({self.expr(scope, c.cls, 1)} AS {c.name})"
                    self.tag("out:star_replace")
                outs = [{"sql": st, "cls": None, "star": True}]
                self.tag("out:star")
            else:
                outs = [self.plain_out(scope) for _ in range(r.choice([1, 1, 2, 2, 3, 4]))]
            c = r.choice(scope)
            if self.oof == "window":
                outs.append(self.window(scope))
            elif self.oof == "volatile":
                if r.random() < 0.5:
                    outs.append({"sql": "random()", "cls": "DBL"})
                else:
                    rand_order = True
            elif self.oof == "unknown_func":
                outs.append({"sql": r.choice([f"HASH({c.alias}.{c.name})", f"MD5(CAST({c.alias}.{c.name} AS VARCHAR))"]),
                             "cls": "TEXT"})
            elif self.oof == "qualify":
                qualify = f" QUALIFY ROW_NUMBER() OVER (PARTITION BY {c.alias}.{c.name}) = 1"
            if self.oof == "distinct_on":
                distinct = f"DISTINCT ON ({c.alias}.{c.name}) "
            elif r.random() < 0.2:
                distinct = "DISTINCT "
        elif shape == "grouped":
            gitems = [self.group_item(scope) for _ in range(r.choice([1, 1, 2]))]
            outs = [dict(g) for g in gitems if r.random() < 0.8]
            g0 = gitems[0]
            if g0["col"] is not None and r.random() < 0.15 and g0["cls"] in ("TEXT", "INT", "DEC"):
                self.tag("out:fn_of_group")
                outs.append({"sql": f"LOWER({g0['sql']})" if g0["cls"] == "TEXT" else f"({g0['sql']} + 1)",
                             "cls": g0["cls"]})
            outs += [dict(zip(("sql", "cls"), self.agg_out(scope))) for _ in range(r.choice([1, 1, 2]))]
            if self.oof == "orderagg":
                outs.append(self.orderagg(scope))
            r.shuffle(outs)
        else:
            outs = [dict(zip(("sql", "cls"), self.agg_out(scope))) for _ in range(r.choice([1, 1, 2, 3]))]
            if r.random() < 0.05:
                having = " HAVING COUNT(*) > 0"
                self.tag("having:global")
        names = sorted({c.name for c in scope})
        used = set()
        for o in outs:
            if o.get("star") or r.random() > 0.35:
                continue
            fresh = [f"c{i}" for i in range(1, 6)] + (['"Mixed Case"', '"c 1"', '"C2"'] if self.v3 else [])
            if self.v4:  # a quoted upper-case spelling of an input column name: DuckDB matches it case-insensitively
                fresh += [f'"{n.upper()}"' for n in names]
            pool = [p for p in (fresh if r.random() < 0.6 else names) if p not in used]
            if pool:
                o["alias"] = r.choice(pool)
                used.add(o["alias"])
                self.tag("alias:shadow" if o["alias"] in names else "alias:fresh")
        if shape == "grouped":
            if self.oof == "groupall":
                group = " GROUP BY ALL"
            elif self.oof == "rollup":
                group = f" GROUP BY ROLLUP ({', '.join(g['sql'] for g in gitems)})"
            else:
                refs = []
                for g in gitems:
                    idx = next((i for i, o in enumerate(outs) if o["sql"] == g["sql"]), None)
                    x = r.random()
                    if idx is not None and x < 0.2:
                        refs.append(str(idx + 1))
                        self.tag("group:by_ordinal")
                    elif idx is not None and outs[idx].get("alias") and x < 0.45:
                        refs.append(outs[idx]["alias"])
                        self.tag("group:by_alias")
                    else:
                        refs.append(g["sql"])
                group = " GROUP BY " + ", ".join(refs)
            if r.random() < 0.3:
                hs = []
                for _ in range(r.choice([1, 1, 2])):
                    k, g = r.choice(["count", "agg_cmp", "grp_const", "grp_null"]), r.choice(gitems)
                    self.tag(f"having:{k}")
                    if k == "count":
                        hs.append(f"COUNT(*) > {r.choice([0, 1, 2])}")
                    elif k == "agg_cmp":
                        a, ak = self.agg(scope)
                        hs.append(f"{a} = TRUE" if ak == "BOOL" else f"{a} {r.choice(CMP)} {self.lit(ak)}")
                    elif k == "grp_const":
                        hs.append(f"{g['sql']} = {self.lit(g['cls'], g['col'])}")
                    else:
                        hs.append(f"{g['sql']} IS NULL")
                having = " HAVING " + " AND ".join(hs)
            if r.random() < 0.08:
                distinct = "DISTINCT "
        if distinct == "DISTINCT ":
            self.tag("distinct")
        order = self.order_by(outs, scope, shape, distinct, gitems, rand_order)
        lim, off = self.limit()
        if self.oof == "collate":
            txt = [x for x in scope if x.cls == "TEXT"]
            key = f"{txt[0].alias}.{txt[0].name}" if txt else f"CAST({scope[0].alias}.{scope[0].name} AS VARCHAR)"
            order = (order + ", " if order else " ORDER BY ") + f"{key} COLLATE NOCASE"
        if self.oof == "sample":
            qualify += " USING SAMPLE 50% (bernoulli, 7)"
        sel = ", ".join(o["sql"] + (f" AS {o['alias']}" if o.get("alias") else "") for o in outs)
        base = (f"SELECT {distinct}{sel} FROM {frm}" + (f" WHERE {' AND '.join(where)}" if where else "")
                + group + having + qualify + order)
        tail = (f" LIMIT {lim}" if lim is not None else "") + (f" OFFSET {off}" if off is not None else "")
        if self.oof == "percent_limit":
            lim, off, tail = None, None, " LIMIT 50%"
        return {"sql": base + tail, "base": base, "limit": lim, "offset": off}


# ------------------------------------------------------------------------------------------------ execution
def finish(rows, head, want_bag):
    rend = [[str(canon(v)) for v in x] for x in rows]  # the study tool's canonical rendering
    o = {"ok": True, "n": len(rows), "head": head, "top": rend[:K],
         "dig": hashlib.sha1(json.dumps([head, len(rows), rend[:K]]).encode()).hexdigest()}
    if want_bag:
        o["bag"] = Counter(map(tuple, rend))
    return o


def load_duck(S, inst, perm_key, threads, extra):
    con = duckdb.connect(":memory:")
    con.execute(f"SET threads={threads}")
    if extra:
        con.execute(extra)
    for stmt in S.get("session", []):
        con.execute(stmt)
    r = random.Random(perm_key)
    for t, spec in S["tables"].items():
        con.execute(f"CREATE TABLE {t} ({', '.join(f'{c} {ty}' for c, ty in spec['columns'].items())})")
        rows = list(inst[t])
        r.shuffle(rows)
        if rows:
            con.executemany(f"INSERT INTO {t} VALUES ({', '.join('?' * len(spec['columns']))})", rows)
    return con


def observe_duck(con, sql, want_bag=False):
    timer = threading.Timer(TIMEOUT, con.interrupt)
    timer.start()
    try:
        cur = con.execute(sql)
        rows = cur.fetchall()
        head = [d[0] for d in cur.description]
    except Exception as ex:  # noqa: BLE001
        name = type(ex).__name__
        return {"ok": False, "err": "TIMEOUT" if "Interrupt" in name else name, "msg": str(ex)[:200]}
    finally:
        timer.cancel()
    return finish(rows, head, want_bag)


def observe_pg(con, sql, want_bag=False):
    try:
        cur = con.execute(sql)
        rows = cur.fetchall()
        head = [d.name for d in cur.description]
    except Exception as ex:  # noqa: BLE001
        s = getattr(ex, "sqlstate", None) or ""
        err = "TIMEOUT" if s == "57014" else ("SEM:" if s[:2] in ("42", "0A") else "RT:") + s
        return {"ok": False, "err": err, "msg": str(ex)[:200]}
    return finish(rows, head, want_bag)


def make_queries(S, n_q, inst0, gen="v1"):
    """Draw queries until n_q pass DuckDB's binder on the first instance (runtime errors are kept)."""
    con = load_duck(S, inst0, f"{S['seed']}-gen", 1, "")
    r = random.Random(f"queries-{S['seed']}")
    qs, attempts, rejected = [], 0, Counter()
    while len(qs) < n_q and attempts < 10 * n_q:
        attempts += 1
        g = QGen(S, r, gen)
        q = g.query()
        o = observe_duck(con, q["sql"])
        if not o["ok"] and (o["err"] in DUCK_SEMANTIC or o["err"] == "TIMEOUT"):
            rejected[o["err"]] += 1
            continue
        if not o["ok"] and "pytz" in o["msg"]:  # the DuckDB client needs pytz to fetch TIMESTAMPTZ (not installable)
            rejected["harness:pytz"] += 1
            continue
        q["tags"] = sorted(g.tags)
        qs.append(q)
    con.close()
    return qs, {"attempts": attempts, "rejected": dict(rejected)}


def cert_of(sql, S, dialect):
    try:
        c = certify(sql, S["tables"], dialect)
    except Exception as ex:  # noqa: BLE001  (a crash is reported, not a verdict)
        return {"verdict": "CRASH", "reason": f"{type(ex).__name__}: {str(ex)[:120]}", "tie": [], "run": None}
    return {"verdict": c.verdict, "reason": c.reason, "tie": c.tie_break,
            "run": sql if c.verdict == "DET" else c.rewritten}


def subbag_ok(cert, full, q):
    L, O = q["limit"], q["offset"] or 0
    want = max(full["n"] - O, 0) if L is None else min(L, max(full["n"] - O, 0))
    return cert["n"] == want and not (cert["bag"] - full["bag"])


def run_instance(qs, sessions, st, viol, S, inst, i):
    """sessions yields (execution index, observe(sql, want_bag)); fills per-query counters and violations."""
    obs = [[] for _ in qs]

    def add(kind, qi, detail):
        st[qi][kind + "_n"] += 1
        if sum(v["kind"] == kind for v in viol) < MAX_VIOL_PER_KIND:
            q = qs[qi]
            viol.append({"kind": kind, "seed": S["seed"], "inst": i, "qi": qi, "sql": q["sql"], "x": q["x"],
                         "verdict": q["verdict"], "reason": q["reason"], "tie": q["tie"], "run": q["run"],
                         "schema": S["tables"], "instance": {t: [[jv(v) for v in row] for row in rows]
                                                             for t, rows in inst.items()}, **detail})

    for e, ob in sessions:
        for qi, q in enumerate(qs):
            if q["x"] is None:
                continue
            rep = q["verdict"] in ("NARROW", "ALL")
            g2 = rep and q["limit"] is None and q["offset"] is None
            raw = ob(q["x"], g2)
            cert = ob(q["run"], g2 or e == 0) if rep else raw
            if rep and raw["ok"] and cert["ok"]:
                if raw["head"] != cert["head"]:  # the rewrite renamed an output column (checked with and without LIMIT)
                    add("g2_header", qi, {"exec": e, "raw_head": raw["head"], "cert_head": cert["head"]})
                if g2:
                    st[qi]["g2_checked"] += 1
                    if raw["bag"] != cert["bag"]:
                        add("g2_bag", qi, {"exec": e, "raw_n": raw["n"], "cert_n": cert["n"],
                                           "raw_only": [list(x) for x in (raw["bag"] - cert["bag"])][:5],
                                           "cert_only": [list(x) for x in (cert["bag"] - raw["bag"])][:5]})
                elif e == 0:
                    full = ob(q["xbase"], True)
                    if full["ok"]:
                        st[qi]["g2_checked"] += 1
                        if not subbag_ok(cert, full, q):
                            add("g2_limit", qi, {"exec": e, "full_n": full["n"], "cert_n": cert["n"],
                                                 "cert_top": cert["top"]})
            raw.pop("bag", None)
            if rep:
                cert.pop("bag", None)
            obs[qi].append((raw, cert))
    for qi, q in enumerate(qs):
        pairs = obs[qi]
        if not pairs:
            continue
        s = st[qi]
        s["inst"] += 1
        raws = [p[0] for p in pairs]
        ok = [o for o in raws if o["ok"]]
        if not ok:
            s["raw_all_err"] += 1
            s["raw_err:" + raws[0]["err"]] += 1
        elif len(ok) < len(raws):
            s["raw_err_mixed"] += 1
        if len(ok) >= 2:
            s["raw_obs"] += 1
            s["raw_div"] += len({o["dig"] for o in ok}) > 1
        if q["verdict"] not in CERTIFIED:
            continue
        certs = [p[1] for p in pairs]
        okc = [o for o in certs if o["ok"]]
        if len(okc) >= 2:
            s["cert_obs"] += 1
        if 0 < len(okc) < len(certs):
            s["cert_err_mixed"] += 1
        digs = {}
        for e, o in enumerate(certs):
            if o["ok"]:
                digs.setdefault(o["dig"], (e, o))
        if len(digs) > 1:
            s["cert_div"] += 1
            ex = list(digs.values())[:2]
            add("cert_div", qi, {"observations": [{"exec": e, "n": o["n"], "head": o["head"], "top": o["top"]}
                                                  for e, o in ex]})
        fails = [e for e, (a, b) in enumerate(pairs) if a["ok"] and not b["ok"] and "pytz" not in b["msg"]]
        s["harness_pytz"] += sum(1 for a, b in pairs if a["ok"] and not b["ok"] and "pytz" in b["msg"])
        if fails:
            s["cert_fail"] += 1
            add("cert_fail", qi, {"execs": fails, "err": certs[fails[0]]["err"], "msg": certs[fails[0]]["msg"]})


def record(q, s, extra=()):
    rec = {k: q[k] for k in ("sql", "tags", "verdict", "reason", "tie", "limit", "offset", *extra)}
    rec.update({k: v for k, v in s.items() if v})
    return rec


def duck_sessions(S, inst, i):
    for e, (p, th, extra) in enumerate(DUCK_EXECS):
        con = load_duck(S, inst, f"{S['seed']}-{i}-{p}", th, extra)
        yield e, (lambda sql, bag, con=con: observe_duck(con, sql, bag))
        con.close()


def duck_schema(job):
    seed, n_q, n_inst, gen = job
    t0 = time.time()
    S = gen_schema(seed, gen)
    insts = [gen_instance(S, f"{seed}-{i}") for i in range(n_inst)]
    qs, meta = make_queries(S, n_q, insts[0], gen)
    for q in qs:
        q.update(cert_of(q["sql"], S, "duckdb"), x=q["sql"], xbase=q["base"])
    st, viol = [Counter() for _ in qs], []
    for i, inst in enumerate(insts):
        run_instance(qs, duck_sessions(S, inst, i), st, viol, S, inst, i)
    recs = [dict(record(q, s), seed=seed, qi=qi) for qi, (q, s) in enumerate(zip(qs, st))]
    meta.update(seed=seed, queries=len(qs), instances=n_inst, executions=len(DUCK_EXECS),
                secs=round(time.time() - t0, 1), **certifier_id())
    return recs, viol, meta


def run_duck(a):
    tag = f"{a.out}/duck_{a.lo}_{a.hi}"
    jobs = [(s, a.queries, a.instances, a.gen) for s in range(a.lo, a.hi)]
    t0 = time.time()
    with open(f"{tag}_queries.jsonl", "w") as fq, open(f"{tag}_violations.jsonl", "w") as fv, \
            open(f"{tag}_meta.jsonl", "w") as fm, mp.Pool(a.workers) as pool:
        for n, (recs, viol, meta) in enumerate(pool.imap_unordered(duck_schema, jobs), 1):
            for x, f in ((recs, fq), (viol, fv), ([meta], fm)):
                for rec in x:
                    f.write(json.dumps(rec) + "\n")
            if n % 10 == 0 or n == len(jobs):
                for f in (fq, fv, fm):
                    f.flush()
                print(f"[duck] {n}/{len(jobs)} schemas, {time.time() - t0:.0f}s", flush=True)


def load_pg(con, S, inst, h, key):
    r = random.Random(key)
    con.execute(f"DROP SCHEMA IF EXISTS h{h} CASCADE")
    con.execute(f"CREATE SCHEMA h{h}")
    for t, spec in S["tables"].items():
        cm = S["meta"][t]["cols"]
        defs = ", ".join(f"{c} {m.get('pgtype') or PGTYPES[m['cls']]}" for c, m in cm.items())
        con.execute(f"CREATE TABLE h{h}.{t} ({defs})")
        rows = list(inst[t])
        r.shuffle(rows)
        if rows:
            with con.cursor() as cur:
                cur.executemany(f"INSERT INTO h{h}.{t} VALUES ({', '.join(['%s'] * len(cm))})", rows)
        for j, k in enumerate(spec["keys"]):
            con.execute(f"ALTER TABLE h{h}.{t} ADD {'PRIMARY KEY' if j == 0 else 'UNIQUE'} ({', '.join(k)})")
        con.execute(f"ANALYZE h{h}.{t}")


def pg_parallel(con, sql):
    try:
        plan = json.dumps(con.execute(f"EXPLAIN (FORMAT JSON) {sql}").fetchone()[0])
    except Exception:  # noqa: BLE001
        return None
    return '"Workers Planned"' in plan and '"Workers Planned": 0' not in plan


def run_pg(a):
    import pg_setup  # also appends the psycopg path
    import psycopg
    from pg_cost import to_pg
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))  # run the finally block (server stop) on scancel
    tag = f"{a.out}/pg_{a.lo}_{a.hi}"
    pg_setup.start(a.server, "1GB")
    cons, loader = [], None
    try:
        with psycopg.connect(pg_setup.conninfo(a.server), autocommit=True) as adm:
            adm.execute("DROP DATABASE IF EXISTS proptest")
            adm.execute("CREATE DATABASE proptest TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'")
            print("[pg]", adm.execute("SELECT version()").fetchone()[0][:60], flush=True)
        ci = pg_setup.conninfo(a.server, "proptest")
        loader = psycopg.connect(ci, autocommit=True)
        for h in range(N_HEAP):
            for w in (0, 4):
                c = psycopg.connect(ci, autocommit=True, prepare_threshold=None)
                c.execute("SET statement_timeout = '20s'")
                c.execute(f"SET search_path = h{h}")
                c.execute(f"SET max_parallel_workers_per_gather = {w}")
                for s in (PARALLEL if w else []) + (SESSION_V6 if a.gen == "v6" else []):
                    c.execute(s)
                cons.append(((h, w), c))
        par_con = cons[1][1]  # heap order 0, parallel-enabled

        def sessions(S, inst, i):
            for h in range(N_HEAP):
                load_pg(loader, S, inst, h, f"{S['seed']}-{i}-h{h}")
            for e, (_, c) in enumerate(cons):
                yield e, (lambda sql, bag, c=c: observe_pg(c, sql, bag))

        t0 = time.time()
        with open(f"{tag}_queries.jsonl", "w") as fq, open(f"{tag}_violations.jsonl", "w") as fv, \
                open(f"{tag}_meta.jsonl", "w") as fm:
            for n, seed in enumerate(range(a.lo, a.hi), 1):
                ts = time.time()
                S = gen_schema(seed, a.gen)
                insts = [gen_instance(S, f"{seed}-{i}") for i in range(a.instances)]
                qs, meta = make_queries(S, a.queries, insts[0], a.gen)  # as in the DuckDB run
                for q in qs:
                    try:
                        q["x"], q["xbase"] = to_pg(q["sql"]), to_pg(q["base"])
                    except Exception as ex:  # noqa: BLE001
                        q.update(x=None, xbase=None, verdict="TRANSPILE_ERROR", reason=str(ex)[:120], tie=[],
                                 run=None)
                        continue
                    q.update(cert_of(q["x"], S, "postgres"))
                st, viol = [Counter() for _ in qs], []
                for i, inst in enumerate(insts):
                    run_instance(qs, sessions(S, inst, i), st, viol, S, inst, i)
                    if i == 0:  # tables of instance 0 are loaded: does PostgreSQL plan workers?
                        for q in qs:
                            if q["x"] is not None:
                                q["par_raw"] = pg_parallel(par_con, q["x"])
                                q["par_run"] = pg_parallel(par_con, q["run"]) if q["run"] else None
                for qi, (q, s) in enumerate(zip(qs, st)):
                    rec = dict(record(q, s), seed=seed, qi=qi, x=q["x"], par_raw=q.get("par_raw"),
                               par_run=q.get("par_run"))
                    fq.write(json.dumps(rec) + "\n")
                for v in viol:
                    fv.write(json.dumps(v) + "\n")
                meta.update(seed=seed, queries=len(qs), instances=a.instances, executions=len(cons),
                            secs=round(time.time() - ts, 1), **certifier_id())
                fm.write(json.dumps(meta) + "\n")
                for f in (fq, fv, fm):
                    f.flush()
                print(f"[pg] {n}/{a.hi - a.lo} schemas, {time.time() - t0:.0f}s", flush=True)
    finally:
        for _, c in cons:
            c.close()
        if loader is not None:
            loader.close()
        pg_setup.stop(a.server)


# ------------------------------------------------------------------------------------------------ summary
def agg_args(sql, names=("SUM(", "AVG(")):
    """Argument texts of the SUM/AVG calls in sql (balanced parentheses)."""
    out = []
    for n in names:
        i = sql.find(n)
        while i >= 0:
            j, depth = i + len(n), 1
            while j < len(sql) and depth:
                depth += {"(": 1, ")": -1}.get(sql[j], 0)
                j += 1
            out.append(sql[i + len(n):j - 1])
            i = sql.find(n, j)
    return out


def root_cause(v):
    """Heuristic root cause of a cert_div record (checked by hand on samples). K = known defect, N = new finding."""
    import re
    import sqlglot
    head = v["observations"][0]["head"]
    if re.search(r"\bts = \w+\.tz\b|\btz = \w+\.ts\b|\bvc = \w+\.ch\b|\bch = \w+\.vc\b", v["x"]):
        return "N12-timestamp-timestamptz-or-char-varchar-equality"  # columns that exist only in generator v6
    if len({h.lower() for h in head}) != len(head):  # duplicates up to case (DuckDB identifiers are case-insensitive)
        return "N1-duplicate-output-name-positional-order"
    args = agg_args(v["x"])
    if any(re.search(r"[A-Za-z]+ '[^']*'::", a) for a in args):
        return "N8-typed-literal-cast-in-sum-avg"
    if any(len(re.sub(r"\D", "", m)) > 38 for a in args for m in re.findall(r"\d[\d.]*", a)):
        return "N9-literal-beyond-38-digits-in-sum-avg"
    if any(re.search(r"\d[eE][-+]?\d", a) for a in args):
        return "N6-sci-notation-literal-in-sum-avg"
    if any("/" in a for a in args):
        return "K1-sum-avg-of-decimal-division"
    order_txt = v["x"].split(" ORDER BY ")[-1] if " ORDER BY " in v["x"] else ""
    if re.search(r"(^|, )\+", order_txt):
        return "N10-unary-plus-in-order-by"
    if re.search(r"= -?[0-9.]+[eE][-+]?[0-9]+", v["x"]):
        return "N11-lossy-numeric-constant"
    try:
        ast = sqlglot.parse_one(v["sql"], read="duckdb")
        outs = {o.sql() for o in ast.expressions} | {o.unalias().sql() for o in ast.expressions}
        order = ast.args.get("order")
        if ast.args.get("distinct") and order is not None and any(
                not (isinstance(o.this, exp_Literal()) and o.this.is_int) and o.this.sql() not in outs
                and o.this.sql() not in {a.alias for a in ast.expressions} for o in order.expressions):
            return "K2-distinct-non-output-order"
    except Exception:  # noqa: BLE001
        pass
    return "other"


def other_cause(v):
    """Label of a g2_* or cert_fail record: N7 = typed literal then :: re-generated by the rewrite, N3 = other
    header renames by the re-generated rewrite, N4 = value-quoting runtime error of the rewrite."""
    import re
    typed = bool(re.search(r"[A-Za-z]+ '[^']*'::", v["x"] or ""))
    if v["kind"] == "cert_fail":
        return ("N7-typed-literal-cast-rewrite" if typed else "binder-other") if "Binder" in v["err"] else "N4-runtime-error"
    if typed:
        return "N7-typed-literal-cast-rewrite"
    return "N3-regenerated-header" if v["kind"] == "g2_header" else "other"


def exp_Literal():
    from sqlglot import exp
    return exp.Literal


def summarize(out_dir, engine):
    recs = [json.loads(line) for f in sorted(glob.glob(f"{out_dir}/{engine}_*_queries.jsonl")) for line in open(f)]
    viol = [json.loads(line) for f in sorted(glob.glob(f"{out_dir}/{engine}_*_violations.jsonl")) for line in open(f)]
    metas = [json.loads(line) for f in sorted(glob.glob(f"{out_dir}/{engine}_*_meta.jsonl")) for line in open(f)]
    if not recs:
        return None
    rejected = Counter()
    for m in metas:
        rejected.update(m["rejected"])
    kinds = ("cert_div_n", "cert_fail_n", "g2_bag_n", "g2_limit_n", "g2_header_n")
    execs = metas[0]["executions"]
    out = {"engine": engine,
           "scale": {"schemas": len(metas), "queries_drawn": sum(m["attempts"] for m in metas),
                     "rejected_semantic": dict(rejected), "queries": len(recs),
                     "instances_per_query": metas[0]["instances"], "executions_per_instance": execs,
                     "query_instance_pairs": sum(r.get("inst", 0) for r in recs),
                     "raw_statement_executions": sum(r.get("inst", 0) for r in recs) * execs,
                     "wall_seconds_sum": round(sum(m["secs"] for m in metas))},
           "verdicts": dict(Counter(r["verdict"] for r in recs)),
           "violations": {k[:-2]: sum(r.get(k, 0) for r in recs) for k in kinds},
           "violation_queries": {k[:-2]: sum(1 for r in recs if r.get(k, 0)) for k in kinds},
           "violation_records_kept": dict(Counter(v["kind"] for v in viol)),
           "cert_fail_errors": dict(Counter(v["err"] + ": " + v["msg"].split(" when ")[0].split(" can't")[0][:70]
                                            for v in viol if v["kind"] == "cert_fail").most_common(10))}
    cd = [v for v in viol if v["kind"] == "cert_div"]
    out["other_violation_causes"] = {k: dict(Counter(other_cause(v) for v in viol if v["kind"] == k))
                                      for k in ("cert_fail", "g2_bag", "g2_limit", "g2_header")}
    out["cert_div_root_causes"] = {"records": dict(Counter(root_cause(v) for v in cd)),
                                   "distinct_queries": dict(Counter(root_cause(v) for v in
                                                                    {v["sql"]: v for v in cd}.values())),
                                   "examples": {c: [v["sql"] for v in cd if root_cause(v) == c][:3]
                                                for c in sorted({root_cause(v) for v in cd})}}
    per = {}
    for v in sorted(out["verdicts"]):
        rs = [r for r in recs if r["verdict"] == v]
        per[v] = {"queries": len(rs),
                  "queries_raw_diverged": sum(1 for r in rs if r.get("raw_div", 0)),
                  "pairs_raw_observed": sum(r.get("raw_obs", 0) for r in rs),
                  "pairs_raw_diverged": sum(r.get("raw_div", 0) for r in rs),
                  "pairs_cert_observed": sum(r.get("cert_obs", 0) for r in rs),
                  "pairs_cert_diverged": sum(r.get("cert_div", 0) for r in rs),
                  "pairs_cert_fail": sum(r.get("cert_fail", 0) for r in rs),
                  "pairs_g2_checked_execs": sum(r.get("g2_checked", 0) for r in rs),
                  "pairs_raw_all_error": sum(r.get("raw_all_err", 0) for r in rs),
                  "pairs_raw_error_mixed": sum(r.get("raw_err_mixed", 0) for r in rs),
                  "pairs_cert_error_mixed": sum(r.get("cert_err_mixed", 0) for r in rs),
                  "queries_raw_error_every_instance": sum(1 for r in rs if r.get("raw_all_err", 0) == r.get("inst", 0))}
        if engine == "pg":
            per[v]["queries_parallel_plan_raw"] = sum(1 for r in rs if r.get("par_raw"))
            per[v]["queries_parallel_plan_certified"] = sum(1 for r in rs if r.get("par_run"))
        per[v]["raw_error_classes"] = dict(Counter(k[8:] for r in rs for k in r if k.startswith("raw_err:")).most_common(8))
    out["per_verdict"] = per
    cov = {}
    for r in recs:
        for t in r["tags"]:
            c = cov.setdefault(t, Counter())
            c["n"] += 1
            c[r["verdict"]] += 1
            c["raw_div_q"] += bool(r.get("raw_div", 0))
    out["coverage"] = {t: dict(c) for t, c in sorted(cov.items())}
    spec_uns = lambda r: any(t.startswith("oof:") or t in SPEC_UNSUPPORTED for t in r["tags"])  # noqa: E731
    out["fail_closed_leak_count"] = sum(1 for r in recs if r["verdict"] in CERTIFIED and spec_uns(r))
    out["fail_closed_leak_tags"] = dict(Counter(t for r in recs if r["verdict"] in CERTIFIED and spec_uns(r)
                                                for t in r["tags"] if t.startswith("oof:") or t in SPEC_UNSUPPORTED))
    out["fail_closed_leaks"] = [{"sql": r["sql"], "verdict": r["verdict"], "tags": [t for t in r["tags"] if
                                t.startswith("oof:") or t in SPEC_UNSUPPORTED], "raw_div": r.get("raw_div", 0),
                                 "cert_div": r.get("cert_div", 0)}
                                for r in recs if r["verdict"] in CERTIFIED and spec_uns(r)][:50]
    infrag = [r for r in recs if not spec_uns(r)]
    out["in_fragment_syntax"] = {"queries": len(infrag), "verdicts": dict(Counter(r["verdict"] for r in infrag)),
                                 "unsupported_reasons": dict(Counter(r["reason"].split("(")[0][:60] for r in infrag
                                                                     if r["verdict"] == "UNSUPPORTED").most_common(15))}
    out["crashes"] = [{"sql": r["sql"], "reason": r["reason"]} for r in recs if r["verdict"] == "CRASH"][:20]
    json.dump(out, open(f"{out_dir}/{engine}_summary.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("scale", "verdicts", "violations", "violation_queries")}, indent=1))
    for v, p in per.items():
        print(f"  {v:15s} q={p['queries']:6d} raw_div_q={p['queries_raw_diverged']:5d} "
              f"pairs raw_div {p['pairs_raw_diverged']}/{p['pairs_raw_observed']} "
              f"cert_div {p['pairs_cert_diverged']}/{p['pairs_cert_observed']} cert_fail {p['pairs_cert_fail']}")
    print("fail-closed leaks:", out["fail_closed_leak_count"], "| in-fragment syntax:", out["in_fragment_syntax"])
    return out


def unjv(v):
    if isinstance(v, dict):
        (k, x), = v.items()
        return float(x) if k == "double" else Decimal(x) if k == "decimal" else datetime.date.fromisoformat(x)
    return v


def diverges(tables, inst, sql, n=24):
    """Distinct canonical observations of sql over n shuffled loads (threads alternate 1/4) of a DuckDB instance."""
    S = {"tables": tables}
    digs = set()
    for p in range(n):
        con = load_duck(S, inst, f"reduce-{p}", 1 if p % 2 == 0 else 4, "")
        o = observe_duck(con, sql)
        con.close()
        digs.add(o["dig"] if o["ok"] else "ERR:" + o["err"])
    return len(digs) > 1


def reduce_violations(path, out):
    """Minimal DuckDB instances for cert_div violations (greedy row deletion while the divergence persists)."""
    seen, res = set(), []
    for line in open(path):
        v = json.loads(line)
        if v["kind"] != "cert_div" or v["sql"] in seen:
            continue
        seen.add(v["sql"])
        inst = {t: [tuple(unjv(x) for x in row) for row in rows] for t, rows in v["instance"].items()}
        if not diverges(v["schema"], inst, v["run"]):
            res.append({"sql": v["sql"], "reproduced": False})
            continue
        for t in inst:
            j = 0
            while j < len(inst[t]):
                trial = dict(inst, **{t: inst[t][:j] + inst[t][j + 1:]})
                if diverges(v["schema"], trial, v["run"]):
                    inst = trial
                else:
                    j += 1
        used = {t for t in v["schema"] if f" {t} " in f" {v['run']} "}
        res.append({"sql": v["sql"], "verdict": v["verdict"], "tie": v["tie"], "run": v["run"], "reproduced": True,
                    "seed": v["seed"], "schema": {t: v["schema"][t] for t in sorted(used)},
                    "instance": {t: [[jv(x) for x in row] for row in inst[t]] for t in sorted(used)}})
        print(json.dumps(res[-1])[:600], flush=True)
    json.dump(res, open(out, "w"), indent=1)


def main():
    if sys.argv[1:2] == ["reduce"]:
        return reduce_violations(sys.argv[2], sys.argv[3])
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["duck", "pg", "summary"])
    ap.add_argument("out")
    ap.add_argument("lo", type=int, nargs="?", default=0)
    ap.add_argument("hi", type=int, nargs="?", default=10)
    ap.add_argument("--queries", type=int, default=25)
    ap.add_argument("--instances", type=int, default=10)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--server", default="proptest")
    ap.add_argument("--gen", default="v1", choices=["v1", "v2", "v3", "v4", "v5", "v6"])
    ap.add_argument("--certify", default=None, help="explicit path of the certify.py under test")
    ap.add_argument("--certify-md5", default=None, help="refuse a certifier whose md5 does not start with this")
    a = ap.parse_args()
    if a.certify:
        use_certifier(a.certify, a.certify_md5)
    print("[proptest] certifier", certifier_id(), flush=True)
    os.makedirs(a.out, exist_ok=True)
    if a.mode == "duck":
        run_duck(a)
    elif a.mode == "pg":
        run_pg(a)
    for engine in (("duck", "pg") if a.mode == "summary" else (a.mode,)):
        summarize(a.out, engine)


if __name__ == "__main__":
    main()
