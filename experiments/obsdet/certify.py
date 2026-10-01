"""Certified observational determinism for bounded SQL previews shown to agents.

certify(sql, tables, dialect) returns a Certificate whose verdict is one of
  DET          the preview (first k rendered rows, their order, the row count) is the same for every
               admissible execution; the query is executed unchanged;
  NARROW       a tie-break T completes the order and is narrower than smart-lex's (fewer attributes, or as many
               with fewer estimated bytes); the rewritten query appends T (ascending, NULLS LAST) to the ORDER BY;
  ALL          the chosen certified tie-break is no narrower than smart-lex's (not necessarily the output columns);
  UNSUPPORTED  outside the supported fragment, or names/types that cannot be resolved (fail closed).
These are the meanings the paper's rules (Section 3) prove; that this code reads each statement as the engine does
(parse, name bindings, types) is the paper's premise (vi), which is tested, not proved.
T is chosen among a primary-key cover, a group-key cover and an output-position cover by (attributes, estimated
bytes), ties going to keys (an index may serve them).

Supported fragment (checked for the root and every nested SELECT): single SELECT over base tables with inner
joins (deterministic ON/WHERE predicates); subqueries without LIMIT/OFFSET anywhere outside FROM; GROUP BY
exact-typed columns or expressions; DISTINCT (ORDER BY items must then be outputs); top-level ORDER BY and integer
LIMIT/OFFSET; aggregates
COUNT/MIN/MAX and SUM/AVG over exact numeric types (MIN/MAX over inexact types only where their value is
rendered, sorted or compared); scalar functions from an immutable allowlist; binary collation. See
refine-logs/METHOD_FORMAL.md.
`tables` = {table: {"columns": {col: duckdb_type}, "keys": [[col, ...], ...]}} (validated non-null keys).
"""
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.tokens import TokenType

INT_T = {"TINYINT", "SMALLINT", "INTEGER", "INT", "BIGINT", "HUGEINT", "UTINYINT", "USMALLINT", "UINTEGER",
         "UBIGINT", "UHUGEINT", "INT2", "INT4", "INT8"}
FLOAT_T = {"DOUBLE", "FLOAT", "REAL", "FLOAT4", "FLOAT8"}
SAFE_AGGS = (exp.Count, exp.Min, exp.Max, exp.Sum, exp.Avg)
VOLATILE = tuple(getattr(exp, n) for n in ("Rand", "Random", "CurrentDate", "CurrentTimestamp", "CurrentTime",
                                           "Uuid", "RandomBits") if hasattr(exp, n))
UNSUPPORTED_NODES = tuple(getattr(exp, n) for n in ("Window", "Union", "Intersect", "Except", "Lateral",
                                                    "Unnest", "Pivot", "TableSample", "Fetch", "Collate")
                          if hasattr(exp, n))
# Immutable, row-local scalar functions admitted in the fragment; any other function is UNSUPPORTED (fail closed).
IMMUTABLE_FUNCS = tuple(getattr(exp, n) for n in (
    "And", "Or", "Not", "Xor", "If", "Case", "Cast", "TryCast", "Coalesce", "Nullif", "Extract", "Year", "Month",
    "Day", "Quarter", "Week", "DayOfWeek", "DayOfMonth", "DayOfYear", "Date", "Substring", "Left", "Right", "Length",
    "Lower", "Upper", "Trim", "Replace", "StrPosition", "Split", "SplitPart", "Concat", "ConcatWs", "Round", "Abs",
    "Floor", "Ceil", "Sqrt", "Pow", "Sign", "Ln", "Log", "Exp", "DateDiff", "DateAdd", "DateSub", "DateTrunc",
    "TimestampTrunc", "TimeToStr", "StrToTime", "StrToDate", "Greatest", "Least", "Initcap", "RegexpLike", "Exists")
    if hasattr(exp, n))
ANON_IMMUTABLE = {"date_part", "datepart"}
PG_RELATIVE_TIME = {"now", "today", "tomorrow", "yesterday"}
WIDTH = {"INT": 8, "DECIMAL": 16, "FLOAT": 8, "BOOL": 1, "TIME": 8, "TEXT": 32}  # estimated bytes per sort key
# Types whose SQL equality is identity of the value: equal values render alike and every immutable function maps
# them to equal results. Floats are inexact (-0.0 = 0.0, but 1/-0.0 != 1/0.0), as are lists and other types.
EXACT = ("INT", "DECIMAL", "TEXT", "BOOL", "TIME")
TYPE_TOKENS = sqlglot.parser.Parser.TYPE_TOKENS
OPEN = (TokenType.L_PAREN, TokenType.L_BRACKET, TokenType.L_BRACE)
CLOSE = (TokenType.R_PAREN, TokenType.R_BRACKET, TokenType.R_BRACE)
SELECT_CLAUSES = {"expressions", "distinct", "from_", "joins", "where", "group", "having", "order", "limit", "offset"}
COMPARISONS = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between, exp.In, exp.Is)
TEXT_FUNCS = tuple(getattr(exp, n) for n in ("TimeToStr", "Substring", "Left", "Right", "Lower", "Upper", "Trim",
                                             "Replace", "Concat", "ConcatWs", "SplitPart", "Initcap") if hasattr(exp, n))
INT_FUNCS = tuple(getattr(exp, n) for n in ("Year", "Month", "Day", "Quarter", "Week", "DayOfWeek", "DayOfMonth",
                                            "DayOfYear", "StrPosition", "DateDiff", "Sign") if hasattr(exp, n))
TIME_FUNCS = tuple(getattr(exp, n) for n in ("Date", "DateTrunc", "TimestampTrunc", "StrToTime", "StrToDate",
                                             "DateAdd", "DateSub") if hasattr(exp, n))
FLOAT_FUNCS = tuple(getattr(exp, n) for n in ("Sqrt", "Ln", "Log", "Exp", "Pow") if hasattr(exp, n))


@dataclass
class Certificate:
    verdict: str
    reason: str = ""
    tie_break: list = field(default_factory=list)
    rewritten: str = None
    evidence: dict = field(default_factory=dict)


def _unsupported(reason):
    return Certificate("UNSUPPORTED", reason)


def type_class(t):
    if t is None:
        return None
    u = str(t).upper()
    base = u.split("(")[0].strip()
    if base in INT_T:
        return "INT"
    if base in FLOAT_T:
        return "FLOAT"
    if base in ("DECIMAL", "NUMERIC"):
        return "DECIMAL"
    if base == "BOOLEAN":
        return "BOOL"
    if base in ("VARCHAR", "TEXT", "STRING", "CHAR"):
        return "TEXT"
    if base in ("DATE", "TIMESTAMP", "TIME", "DATETIME", "TIMESTAMP WITH TIME ZONE"):
        return "TIME"
    return "OTHER"


def _strip(e):
    while isinstance(e, (exp.Paren, exp.Alias)):
        e = e.this
    return e


def _enclosing_select(node):
    p = node.parent
    while p is not None and not isinstance(p, exp.Select):
        p = p.parent
    return p


def _sources(select):
    """alias -> table name for base tables in a SELECT's FROM/JOIN; None if a source is not a base table.
    A schema- or catalog-qualified name keeps its qualifiers, so it matches no catalog table (unknown-table):
    the catalog describes one schema, and the qualifier may name another."""
    out = {}
    frm = select.args.get("from") or select.args.get("from_")
    items = ([frm.this] if frm is not None else []) + [j.this for j in (select.args.get("joins") or [])]
    for s in items:
        if not isinstance(s, exp.Table):
            return None
        out[s.alias_or_name] = ".".join(p for p in (s.catalog, s.db, s.name) if p)
    return out


class _Ctx:
    def __init__(self, q, tables, dialect):
        self.q, self.tables, self.dialect = q, tables, dialect
        self.cache = {}

    def raw_type(self, col):
        """The declared type of a column, as the catalog records it."""
        sel = _enclosing_select(col)
        while sel is not None:
            src = _sources(sel) or {}
            if col.table in src:
                t = self.tables.get(src[col.table])
                return t["columns"].get(col.name) if t else None
            sel = _enclosing_select(sel)
        return None

    def col_type(self, col):
        return type_class(self.raw_type(col))

    def infer(self, e):
        """Type class of a scalar expression, or None when unknown."""
        e = _strip(e)
        if isinstance(e, exp.Column):
            return self.col_type(e)
        if isinstance(e, exp.Null):
            return "NULL"
        if isinstance(e, exp.Boolean):
            return "BOOL"
        if isinstance(e, exp.Literal):
            if e.is_string:
                return "TEXT"
            if self.dialect == "duckdb":  # DuckDB types 1e0, decimals over 38 digits and integers beyond HUGEINT as DOUBLE
                if "e" in e.this.lower() or sum(ch.isdigit() for ch in e.this) > 38:
                    return "FLOAT"
                if e.is_int and abs(int(e.this)) > 2 ** 127 - 1:
                    return "FLOAT"
            return "INT" if e.is_int else "DECIMAL"
        if isinstance(e, exp.Cast):
            return type_class(e.to.sql(dialect=self.dialect))
        if isinstance(e, (exp.Add, exp.Sub, exp.Mul, exp.Mod)):
            return _combine(self.infer(e.this), self.infer(e.expression))
        if isinstance(e, exp.Div):
            a, b = self.infer(e.this), self.infer(e.expression)
            if a is None or b is None:
                return None
            if self.dialect == "duckdb":
                return "FLOAT"  # '/' returns DOUBLE in DuckDB, also for two DECIMAL operands
            return _combine(a, b)
        if isinstance(e, exp.IntDiv):
            a, b = self.infer(e.this), self.infer(e.expression)
            if a is None or b is None:
                return None
            if a in ("INT", "BOOL") and b in ("INT", "BOOL"):
                return "INT"
            return "FLOAT" if self.dialect == "duckdb" else _combine(a, b)  # DuckDB '//' on DECIMAL/DOUBLE: DOUBLE
        if isinstance(e, exp.Neg):
            return self.infer(e.this)
        if isinstance(e, (exp.Predicate, exp.Not, exp.And, exp.Or, exp.Connector)):
            return "BOOL"
        if isinstance(e, exp.Case):
            ts = [self.infer(i.args.get("true")) for i in e.args.get("ifs") or []]
            if e.args.get("default") is not None:
                ts.append(self.infer(e.args["default"]))
            return _combine(*ts)
        if isinstance(e, exp.If):
            return _combine(self.infer(e.args.get("true")), self.infer(e.args.get("false")))
        if isinstance(e, exp.Coalesce):
            return _combine(self.infer(e.this), *[self.infer(x) for x in e.expressions])
        if isinstance(e, exp.Sign) and self.dialect == "postgres":  # sign(double precision) is double precision
            t = self.infer(e.this)
            return "FLOAT" if t == "FLOAT" else (None if t is None else "DECIMAL")
        if isinstance(e, (exp.Length, exp.Count)) or isinstance(e, INT_FUNCS):
            return "INT"
        if isinstance(e, exp.Extract):
            return "FLOAT" if e.this.name.upper() in ("EPOCH", "JULIAN") else "INT"
        if isinstance(e, exp.Anonymous) and e.name.lower() in ANON_IMMUTABLE:
            part = e.expressions[0] if e.expressions else None
            return "FLOAT" if isinstance(part, exp.Literal) and part.this.lower() in ("epoch", "julian") else "INT"
        if isinstance(e, TEXT_FUNCS):
            return "TEXT"
        if isinstance(e, TIME_FUNCS):
            return "TIME"
        if isinstance(e, FLOAT_FUNCS):
            return "FLOAT"
        if isinstance(e, (exp.Abs, exp.Round, exp.Min, exp.Max, exp.Floor, exp.Ceil, exp.Nullif)):
            return self.infer(e.this)
        if isinstance(e, (exp.Greatest, exp.Least)):
            return _combine(self.infer(e.this), *[self.infer(x) for x in e.expressions])
        return None


def _combine(*ts):
    ts = [t for t in ts if t != "NULL"]
    if not ts or any(t is None for t in ts):
        return None
    if any(t == "FLOAT" for t in ts):
        return "FLOAT"
    if all(t in ("INT", "BOOL") for t in ts):
        return "INT"
    if all(t in ("INT", "BOOL", "DECIMAL") for t in ts):
        return "DECIMAL"
    return ts[0] if len(set(ts)) == 1 else None


def _conjuncts(e):
    if e is None:
        return []
    e = _strip(e)
    if isinstance(e, exp.And):
        return _conjuncts(e.this) + _conjuncts(e.expression)
    return [e]


def _root_cols(e, q):
    """Root-level column references of e (outer references inside correlated subqueries included)."""
    out = set()
    for c in e.find_all(exp.Column):
        if isinstance(c.this, exp.Star):
            continue
        sel = _enclosing_select(c)
        src = _sources(q) or {}
        if sel is q or (c.table in src and not ((_sources(sel) or {}).get(c.table))):
            out.add((c.table, c.name))
    return out


def _equality_safe(node, q):
    """True if the value of `node` is only rendered as a root output, used as a sort key, or compared: uses that
    respect SQL equality, so any representative of an equality class gives the same observation."""
    while True:
        p = node.parent
        while isinstance(p, (exp.Alias, exp.Paren)):
            node, p = p, p.parent
        if isinstance(p, (exp.Ordered,) + COMPARISONS):
            return True
        if isinstance(p, exp.Select) and any(x is node for x in p.expressions):
            if p is q or isinstance(p.parent, exp.Exists):
                return True
            if isinstance(p.parent, exp.Subquery) and len(p.expressions) == 1:  # scalar subquery value
                node = p.parent
                continue
        return False


def _has_root_agg(e, q):
    return any(_enclosing_select(a) is q for a in e.find_all(exp.AggFunc))


def _closure(attrs, fds):
    cl = set(attrs)
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            if lhs <= cl and not rhs <= cl:
                cl |= rhs
                changed = True
    return cl


def _key(e):
    return _strip(e).sql(dialect="duckdb", normalize=True)


def _blank_padded(raw):
    """PostgreSQL CHAR(n) compares ignoring trailing spaces, so equal values need not be identical."""
    return str(raw).upper().split("(")[0].strip() in ("CHAR", "BPCHAR", "CHARACTER")


def _eq_exact(a, b, raw_a, raw_b):
    """Column equality a = b makes each side a function of the other: no -0.0 = 0.0, and no comparison that the engine
    evaluates after a lossy or non-injective conversion (a DECIMAL combination beyond 38 digits compares as DOUBLE;
    timestamp vs timestamptz goes through the session time zone; CHAR(n) ignores trailing spaces)."""
    ra, rb = str(raw_a).upper(), str(raw_b).upper()
    if a == b == "INT":
        return not ({ra, rb} & {"UBIGINT", "UHUGEINT"}) or ra == rb
    if a == b and a in ("DECIMAL", "TIME"):
        return ra == rb
    if a == b == "TEXT":
        return not (_blank_padded(ra) or _blank_padded(rb))
    return a == b == "BOOL"


def _const_exact(col_class, raw, lit, lit_class):
    """col = literal pins the rendered value of col (a string literal is cast to the column's type)."""
    if col_class in ("INT", "DECIMAL"):
        return lit.is_string or lit_class in ("INT", "DECIMAL")  # a DOUBLE literal would compare after a lossy cast
    return col_class in ("TEXT", "TIME") and lit.is_string and not _blank_padded(raw)


def _statements(sql, dialect):
    return [s for s in sqlglot.parse(sql, read=dialect) if s is not None]


def _order_item_tokens(toks):
    """Tokens of each top-level ORDER BY item of the statement as written."""
    depth, items, cur, inside = 0, [], [], False
    for t in toks:
        tt = t.token_type
        if depth == 0 and tt == TokenType.ORDER_BY:
            inside, items, cur = True, [], []
            continue
        if depth == 0 and inside and tt in (TokenType.LIMIT, TokenType.OFFSET, TokenType.FETCH, TokenType.SEMICOLON):
            break
        if tt in OPEN:
            depth += 1
        elif tt in CLOSE:
            depth -= 1
        if inside:
            if depth == 0 and tt == TokenType.COMMA:
                items.append(cur)
                cur = []
            else:
                cur.append(t)
    if inside and cur:
        items.append(cur)
    return items


def certify(sql, tables, dialect="duckdb"):
    try:
        stmts = _statements(sql, dialect)
        toks = sqlglot.tokenize(sql, read=dialect)
    except Exception as ex:  # noqa: BLE001
        return _unsupported(f"parse:{type(ex).__name__}")
    if len(stmts) != 1:
        return _unsupported("multi-statement")
    ast = stmts[0]
    if not isinstance(ast, exp.Select):
        return _unsupported(f"not-select:{ast.key}")
    if dialect == "postgres":  # sqlglot parses date_part() (double precision) as EXTRACT (numeric) and rewrites it
        if any(t.text.lower() == "date_part" and i + 1 < len(toks) and toks[i + 1].token_type == TokenType.L_PAREN
               for i, t in enumerate(toks)):
            return _unsupported("function:date_part")
    if any(item and item[0].token_type == TokenType.PLUS for item in _order_item_tokens(toks)):
        return _unsupported("order-by-unary-plus")  # sqlglot drops a unary '+', which turns an expression into a name
    for i in range(len(toks) - 2):  # sqlglot inverts TYPE 'literal'::TYPE2 into CAST(CAST('literal' AS TYPE2) AS TYPE)
        if (toks[i].token_type in TYPE_TOKENS and toks[i + 1].token_type == TokenType.STRING
                and toks[i + 2].token_type == TokenType.DCOLON):
            return _unsupported("typed-literal-cast")
    for sel in ast.find_all(exp.Select):  # qualify() turns USING/NATURAL into ON and would hide them
        for j in sel.args.get("joins") or []:
            bad = _bad_join(j)
            if bad:
                return _unsupported(bad)
    order0 = ast.args.get("order")  # ORDER BY items as written: qualify() may rebind ordinals to ambiguous names
    order_spec = []
    if order0 is not None and not _order_by_all(order0):
        for o in order0.expressions:
            t = o.this
            if isinstance(t, exp.Literal) and t.is_int:
                order_spec.append(("pos", int(t.this)))
            elif isinstance(t, exp.Column) and not t.table:
                order_spec.append(("name", t.name.lower()))
            else:
                order_spec.append(("expr", None))
                # inside an expression the engines bind names to input columns, and qualify() may bind them to outputs
                aliases = {a.alias.lower() for a in ast.expressions if isinstance(a, exp.Alias)}
                if any(not c.table and c.name.lower() in aliases for c in t.find_all(exp.Column)):
                    return _unsupported("order-by-alias-in-expression")
        if dialect == "postgres" and any(k == "name" for k, _ in order_spec):  # "FOO" and foo differ in PostgreSQL
            idents = [o.this.this for o in order0.expressions if isinstance(o.this, exp.Column) and not o.this.table]
            idents += [e.args.get("alias") for e in ast.expressions if isinstance(e, exp.Alias)]
            idents += [e.this for e in ast.expressions if isinstance(e, exp.Column)]
            if any(isinstance(i, exp.Identifier) and i.quoted and i.this != i.this.lower() for i in idents):
                return _unsupported("pg-quoted-name")
    if dialect == "duckdb":  # DuckDB identifiers are case-insensitive; sqlglot normalizes them to lower case
        tables = {t.lower(): {"columns": {c.lower(): ty for c, ty in v["columns"].items()},
                              "keys": [[c.lower() for c in k] for k in v["keys"]]} for t, v in tables.items()}
    schema = {t: dict(v["columns"]) for t, v in tables.items()}
    try:
        q = qualify(ast.copy(), dialect=dialect, schema=schema, validate_qualify_columns=True, expand_stars=True,
                    quote_identifiers=True, identify=False)
    except Exception as ex:  # noqa: BLE001
        return _unsupported(f"unresolved:{type(ex).__name__}")

    # ---- fragment checks (fail closed), applied to the root and to every nested SELECT ----
    for sel in q.find_all(exp.Select):
        if sel.args.get("with_") is not None or sel.args.get("with") is not None:
            return _unsupported("cte")
        extra = sorted(k for k, v in sel.args.items() if v not in (None, [], False) and k not in SELECT_CLAUSES)
        if extra:
            return _unsupported(f"clause:{extra[0]}")
        for j in sel.args.get("joins") or []:
            bad = _bad_join(j)
            if bad:
                return _unsupported(bad)
        dd = sel.args.get("distinct")
        if dd is not None and dd.args.get("on") is not None:
            return _unsupported("distinct-on")
        g = sel.args.get("group")
        if g is not None and any(g.args.get(k) for k in ("rollup", "cube", "grouping_sets")):
            return _unsupported("grouping-sets")
        if g is not None and g.args.get("all"):
            return _unsupported("group-by-all")
        src = _sources(sel)
        if src is None:
            return _unsupported("derived-table")
        if any(t not in tables for t in src.values()):
            return _unsupported("unknown-table")
    for node in q.walk():
        if isinstance(node, UNSUPPORTED_NODES):
            return _unsupported(f"construct:{node.key}")
        if VOLATILE and isinstance(node, VOLATILE):
            return _unsupported(f"volatile:{node.key}")
        if isinstance(node, exp.Subquery) and isinstance(node.parent, (exp.From, exp.Join)):
            return _unsupported("derived-table")
        if isinstance(node, exp.Select) and node is not q:
            if node.args.get("limit") is not None or node.args.get("offset") is not None:
                return _unsupported("nested-limit")
            if _sources(node) is None:
                return _unsupported("derived-table")
        if isinstance(node, exp.Anonymous):
            if node.name.lower() not in ANON_IMMUTABLE:
                return _unsupported(f"function:{node.name.lower()}")
        elif isinstance(node, exp.Func) and not isinstance(node, IMMUTABLE_FUNCS + (exp.AggFunc,)):
            return _unsupported(f"function:{node.key}")
    for k in ("limit", "offset"):  # plain integer LIMIT/OFFSET only (no percent, no expressions)
        node = q.args.get(k)
        if node is not None:
            v = node.args.get("expression")
            if not (isinstance(v, exp.Literal) and v.is_int) or node.args.get("limit_options") or node.args.get("offset"):
                return _unsupported(f"{k}-form")
    root_src = _sources(q)
    if not root_src:
        return _unsupported("no-base-table")
    d, grp = q.args.get("distinct"), q.args.get("group")
    ctx = _Ctx(q, tables, dialect)
    # representatives of inexact equality classes must only be rendered, sorted or compared
    for sel in q.find_all(exp.Select):
        g = sel.args.get("group")
        if g is not None and any(ctx.infer(x) not in EXACT for x in g.expressions):
            return _unsupported("inexact-group-key")
        if sel is not q and sel.args.get("distinct") is not None:
            if any(ctx.infer(x) not in EXACT and not _equality_safe(x, q) for x in sel.expressions):
                return _unsupported("inexact-distinct-value")
    for agg in q.find_all(exp.Min, exp.Max):
        if ctx.infer(agg.this) not in EXACT and not _equality_safe(agg, q):
            return _unsupported("inexact-min-max-in-expression")
    if dialect == "postgres":  # 'now', 'today', ... are evaluated against the transaction clock
        for lit in q.find_all(exp.Literal):
            if lit.is_string and lit.this.strip().lower() in PG_RELATIVE_TIME:
                p = lit.parent
                if isinstance(p, exp.In):  # the literal may be the probe or one of the listed values
                    other = [p.this] if p.this is not lit else (list(p.expressions) if p.args.get("query") is None
                                                                else [None])
                else:
                    other = [x for x in (p.args.get("this"), p.args.get("expression")) if x is not None and x is not lit]
                if not (isinstance(p, COMPARISONS) and other
                        and all(x is not None and ctx.infer(x) == "TEXT" for x in other)):
                    return _unsupported("relative-time-literal")
        for c in q.find_all(exp.Cast):
            if type_class(c.to.sql(dialect=dialect)) == "TIME" and ctx.infer(c.this) in ("TEXT", None):
                return _unsupported("text-to-temporal-cast")
    for agg in q.find_all(exp.AggFunc):
        if not isinstance(agg, SAFE_AGGS):
            return _unsupported(f"aggregate:{agg.key}")
        if isinstance(agg, (exp.Sum, exp.Avg)):
            arg = agg.this.this if isinstance(agg.this, exp.Distinct) else agg.this
            if isinstance(arg, exp.Distinct):
                arg = arg.expressions[0] if arg.expressions else None
            tc = ctx.infer(arg) if arg is not None else None
            if tc in (None, "TEXT", "TIME", "OTHER"):
                return _unsupported("aggregate-type-unknown")
            if tc == "FLOAT":
                return _unsupported("float-aggregate")

    # ---- keys, equalities, constants at the root ----
    fds = []
    for alias, t in root_src.items():
        allc = frozenset((alias, c) for c in tables[t]["columns"])
        for key in tables[t]["keys"]:
            fds.append((frozenset((alias, c) for c in key), allc))
    consts = set()
    where, having = q.args.get("where"), q.args.get("having")
    conds = _conjuncts(where.this if where is not None else None)
    conds += _conjuncts(having.this if having is not None else None)  # holds for every output group
    for j in q.args.get("joins") or []:
        conds += _conjuncts(j.args.get("on"))
    for c in conds:
        if isinstance(c, exp.EQ):
            l, r = _strip(c.this), _strip(c.expression)
            lc = isinstance(l, exp.Column) and _enclosing_select(l) is q and l.table in root_src
            rc = isinstance(r, exp.Column) and _enclosing_select(r) is q and r.table in root_src
            if lc and rc:
                if _eq_exact(ctx.infer(l), ctx.infer(r), ctx.raw_type(l), ctx.raw_type(r)):
                    fds.append((frozenset([(l.table, l.name)]), frozenset([(r.table, r.name)])))
                    fds.append((frozenset([(r.table, r.name)]), frozenset([(l.table, l.name)])))
            elif lc and isinstance(r, exp.Literal) and _const_exact(ctx.infer(l), ctx.raw_type(l), r, ctx.infer(r)):
                consts.add((l.table, l.name))
            elif rc and isinstance(l, exp.Literal) and _const_exact(ctx.infer(r), ctx.raw_type(r), l, ctx.infer(l)):
                consts.add((r.table, r.name))
        elif isinstance(c, exp.Is) and isinstance(_strip(c.expression), exp.Null):
            t = _strip(c.this)
            if isinstance(t, exp.Column) and t.table in root_src:
                consts.add((t.table, t.name))

    outs = [_strip(e) for e in q.expressions]
    out_keys = [_key(e) for e in outs]
    out_names = [e.alias_or_name.lower() for e in q.expressions]
    order = q.args.get("order")
    order_items = [o.this for o in order.expressions] if order is not None else []
    if _order_by_all(order):  # DuckDB ORDER BY ALL: every output column, in order
        order_items = [exp.Literal.number(i + 1) for i in range(len(outs))]
        order_spec = [("pos", i + 1) for i in range(len(outs))]
    if len(order_spec) != len(order_items):
        return _unsupported("order-by-rewritten")
    # map ORDER BY items to plain columns / output positions, resolving ordinals and output names as written
    order_cols, order_out = set(), set()
    for it, (kind, val) in zip(order_items, order_spec):
        s = _strip(it)
        if kind == "pos":
            if not 1 <= val <= len(outs):
                return _unsupported("order-by-position")
            s = outs[val - 1]
        elif kind == "name":
            hits = [i for i, n in enumerate(out_names) if n == val]
            if len(hits) > 1:  # several outputs carry this name
                return _unsupported("ambiguous-order-by-name")
            if hits:
                s = outs[hits[0]]
        if isinstance(s, exp.Column) and s.table in root_src and _enclosing_select(s) is q and ctx.col_type(s) in EXACT:
            order_cols.add((s.table, s.name))  # inexact (float) ties do not make the rows' values equal
        k = _key(s)
        matched = {i for i, ok in enumerate(out_keys) if ok == k}
        if d is not None and not matched:  # DuckDB sorts DISTINCT rows by an arbitrary value of a non-output key
            return _unsupported("distinct-order-by-non-output")
        order_out |= matched
    base_cl = _closure(order_cols | consts, fds)

    grouped, distinct = grp is not None, d is not None
    single_row = (not grouped) and any(_has_root_agg(e, q) for e in outs)
    ev = {"order_cols": sorted(map(list, order_cols)), "consts": sorted(map(list, consts)),
          "grouped": grouped, "single_row": single_row}
    if single_row:
        return Certificate("DET", "single-row aggregate", evidence=ev)

    def det_out(i):
        e = outs[i]
        if i in order_out:
            return True
        if _has_root_agg(e, q):
            return False
        return _root_cols(e, q) <= base_cl

    def plain(e):
        """The column of an exact-typed plain column reference (a sort key that fixes the value), else None."""
        if isinstance(e, exp.Column) and e.table in root_src and _enclosing_select(e) is q and ctx.col_type(e) in EXACT:
            return (e.table, e.name)
        return None

    def width(e):
        return WIDTH.get(ctx.infer(e), 32)

    def cover(items, exprs):
        """Greedy subset of `items` whose values, used as sort keys, force every item's value to be equal on tied
        rows. Only plain columns feed the FD closure: an expression's value does not determine its inputs."""
        return _greedy_cover(items, lambda sel: _closure(base_cl | ({plain(exprs[i]) for i in sel} - {None}), fds),
                             lambda i, cl: not _has_root_agg(exprs[i], q) and _root_cols(exprs[i], q) <= cl,
                             lambda i: width(exprs[i]))

    cands = []  # (attributes, estimated bytes, preference, tie-break, reason); the smallest tuple wins
    if grouped and not distinct:
        gexprs = [_strip(g) for g in grp.expressions]
        gkeys = [_key(g) for g in gexprs]

        def det_g(i):
            g = gexprs[i]
            if any(gkeys[i] == out_keys[j] for j in order_out) or gkeys[i] in {_key(x) for x in order_items}:
                return True
            return _root_cols(g, q) <= base_cl
        undet_g = [i for i in range(len(gexprs)) if not det_g(i)]
        ev["undetermined_group"] = [gkeys[i] for i in undet_g]
        if not undet_g:
            return Certificate("DET", "order determines group key", evidence=ev)
        chosen = cover(undet_g, gexprs)
        keys = []  # each chosen group expression as a plain column or as the output position that equals it
        for i in chosen:
            col, pos = plain(gexprs[i]), [j for j, ok in enumerate(out_keys) if ok == gkeys[i]]
            keys.append(("col", col) if col else (("pos", pos[0] + 1) if pos else None))
        if None not in keys:  # otherwise the output cover below applies
            cands.append((len(chosen), sum(width(gexprs[i]) for i in chosen), 0, keys, "group key tie-break"))

    undet = [i for i in range(len(outs)) if not det_out(i)]
    ev["undetermined_out"] = [out_keys[i] for i in undet]
    if not undet:
        return Certificate("DET", "order determines every output column", evidence=ev)
    if not grouped and not distinct:  # key-based tie-break; keys may be non-output columns
        keys = [(alias, key) for alias, t in root_src.items() for key in tables[t]["keys"]]
        need = set().union(*[_root_cols(outs[i], q) for i in undet])
        sel, cl = [], set(base_cl)
        while not need <= cl:
            gain = []
            for idx, (alias, key) in enumerate(keys):
                if (alias, tuple(key)) in sel:
                    continue
                kc = _closure(cl | {(alias, c) for c in key}, fds)
                g = len((need - cl) & kc)
                if g:
                    kb = sum(WIDTH.get(type_class(tables[root_src[alias]]["columns"][c]), 32) for c in key)
                    gain.append((g, -len(key), -kb, -idx, alias, key, kc))
            if not gain:
                sel = None
                break
            gain.sort(key=lambda x: x[:4], reverse=True)
            *_, alias, key, kc = gain[0]
            sel.append((alias, tuple(key)))
            cl = kc
        if sel:
            cols = [(alias, c) for alias, key in sel for c in key]
            cands.append((len(cols), sum(WIDTH.get(type_class(tables[root_src[a]]["columns"][c]), 32) for a, c in cols),
                          0, [("col", x) for x in cols], "key tie-break"))
    chosen = cover(undet, outs)  # output positions (the only admissible sort keys under DISTINCT)
    oc = (len(chosen), sum(width(outs[i]) for i in chosen), 1, [("pos", i + 1) for i in chosen], "output tie-break")
    eligible = [c for c in cands if c[0] <= oc[0] and c[1] <= oc[1]] + [oc]
    n, w, _, tie, reason = min(eligible, key=lambda c: c[:3])
    cands.append(oc)
    ev["candidates"] = [list(c[:3]) + [c[4]] for c in cands]
    full = (len(outs), sum(width(e) for e in outs))  # smart-lex appends every output column
    return _rewrite(ast, sql, dialect, tie, "NARROW" if (n, w) < full else "ALL", reason, ev)


def _bad_join(j):
    """Reason code if a join is not a plain inner join (comma, CROSS, or JOIN ... ON), else None."""
    if j.args.get("side") or j.args.get("method") or (j.args.get("kind") or "").upper() not in ("", "INNER", "CROSS"):
        return "outer-or-special-join"
    if j.args.get("using"):
        return "using-join"
    return None


def _order_by_all(order):
    return (order is not None and len(order.expressions) == 1 and isinstance(order.expressions[0].this, exp.Var)
            and order.expressions[0].this.name.upper() == "ALL")


def _greedy_cover(items, closure_of, covered, weight=lambda i: 0):
    """Pick items until every item is determined by the closure of the picked ones (most covered first, then the
    narrowest, then the first)."""
    chosen = []
    while True:
        cl = closure_of(chosen)
        rest = [i for i in items if not covered(i, cl) and i not in chosen]
        if not rest:
            return chosen
        scores = []
        for i in rest:
            cl2 = closure_of(chosen + [i])
            scores.append((sum(1 for j in rest if covered(j, cl2)), -weight(i), -i, i))
        scores.sort(reverse=True)
        chosen.append(scores[0][3])


def _splice_order(sql, dialect, keys):
    """The statement as written, with `keys` (SQL text) appended to its top-level ORDER BY, ascending with NULLS LAST
    (a new ORDER BY clause if it has none), inserted before a top-level LIMIT/OFFSET/FETCH or the end of the statement.
    Nothing else in the text changes, so literals, casts and engine-generated column names stay as written."""
    toks = sqlglot.tokenize(sql, read=dialect)
    depth, has_order, stop = 0, False, len(toks)
    for i, t in enumerate(toks):
        if t.token_type in OPEN:
            depth += 1
        elif t.token_type in CLOSE:
            depth -= 1
        elif depth == 0:
            if t.token_type == TokenType.ORDER_BY:
                has_order = True
            elif t.token_type in (TokenType.LIMIT, TokenType.OFFSET, TokenType.FETCH, TokenType.SEMICOLON):
                stop = i
                break
    if stop == 0:
        return None
    pos = toks[stop - 1].end + 1
    add = ", ".join(f"{k} ASC NULLS LAST" for k in keys)
    return sql[:pos] + (", " if has_order else " ORDER BY ") + add + sql[pos:]


def _with_keys(stmt, sql, dialect, nodes):
    """Splice sort keys into the statement as written; None unless the result parses to exactly `stmt` with the keys
    appended to its ORDER BY."""
    a2 = stmt.copy()
    order = a2.args.get("order")
    items = [o.copy() for o in (order.expressions if order is not None else [])]
    items += [exp.Ordered(this=node, desc=False, nulls_first=False) for node in nodes]
    a2.set("order", exp.Order(expressions=items))
    try:
        text = _splice_order(sql, dialect, [node.sql(dialect=dialect) for node in nodes])
        if text is not None:
            parsed = _statements(text, dialect)
            if len(parsed) == 1 and parsed[0] == a2:
                return text
    except Exception:  # noqa: BLE001
        pass
    return None


def _rewrite(ast, sql, dialect, tie, verdict, reason, ev):
    nodes = [exp.Literal.number(v) if kind == "pos" else exp.column(v[1], table=v[0], quoted=True) for kind, v in tie]
    text = _with_keys(ast, sql, dialect, nodes)
    if text is None:
        return _unsupported("rewrite-splice")
    return Certificate(verdict, reason, tie_break=[n.sql(dialect=dialect) for n in nodes], rewritten=text, evidence=ev)


def smartlex(sql, n_out, dialect="duckdb"):
    """Baseline: existing ORDER BY keys, then every output column by position (NULLS LAST), spliced into the statement
    as written."""
    try:
        stmts = _statements(sql, dialect)
    except Exception:  # noqa: BLE001
        return None
    if len(stmts) != 1 or not isinstance(stmts[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return None
    if _order_by_all(stmts[0].args.get("order")):  # already ordered by every output column
        return sql
    return _with_keys(stmts[0], sql, dialect, [exp.Literal.number(i) for i in range(1, n_out + 1)])
