# SQL normalization, SPJ(+aggregate) block extraction, conservative containment checking and
# compensation-query generation, plus sub-expression signatures (join sub-trees, filtered scans).
# All checks are syntactic over sqlglot ASTs after qualification with the database schema, so they are
# conservative: "not answerable" may be a false negative, "answerable" must be sound (validated in replay).
import itertools

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

DIALECT = "duckdb"


class NotMappable(Exception):
    pass


def sql_of(node):
    return node.sql(dialect=DIALECT)


def exact_key(sql):
    return sql.strip().rstrip(";").strip()


def _from(sel):
    return sel.args.get("from") or sel.args.get("from_")


# ----------------------------------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------------------------------

def _flatten(node, cls):
    if isinstance(node, exp.Paren) and isinstance(node.this, cls):
        node = node.this
    if isinstance(node, cls):
        return _flatten(node.this, cls) + _flatten(node.expression, cls)
    return [node]


_FLIP = {exp.GT: exp.LT, exp.LT: exp.GT, exp.GTE: exp.LTE, exp.LTE: exp.GTE}


def _canon_pred(node):
    """Canonicalize a boolean expression: sorted AND/OR operands, sorted '=' operands, literal on the right,
    BETWEEN expanded into two conjuncts."""
    if isinstance(node, exp.Paren) and isinstance(node.this, (exp.And, exp.Or)):
        node = node.this
    if isinstance(node, exp.And):
        parts = [_canon_pred(p) for p in _flatten(node, exp.And)]
        flat = []
        for p in parts:
            flat.extend(_flatten(p, exp.And))
        flat = sorted({sql_of(p): p for p in flat}.items())
        return exp.and_(*[p for _, p in flat], copy=False)
    if isinstance(node, exp.Or):
        parts = sorted({sql_of(p): p for p in (_canon_pred(p) for p in _flatten(node, exp.Or))}.items())
        return exp.or_(*[p for _, p in parts], copy=False)
    if isinstance(node, exp.Between) and not node.args.get("symmetric"):
        lo = exp.GTE(this=node.this.copy(), expression=node.args["low"].copy())
        hi = exp.LTE(this=node.this.copy(), expression=node.args["high"].copy())
        return _canon_pred(exp.and_(lo, hi, copy=False))
    if isinstance(node, (exp.EQ, exp.NEQ)):
        a, b = node.this, node.expression
        if sql_of(a) > sql_of(b) and not isinstance(b, exp.Literal):
            node = node.__class__(this=b, expression=a)
        elif isinstance(a, exp.Literal) and not isinstance(b, exp.Literal):
            node = node.__class__(this=b, expression=a)
        return node
    if type(node) in _FLIP and isinstance(node.this, exp.Literal) and not isinstance(node.expression, exp.Literal):
        return _FLIP[type(node)](this=node.expression, expression=node.this)
    return node


def _lower_identifiers(ast):
    for ident in ast.find_all(exp.Identifier):
        if isinstance(ident.this, str):
            ident.set("this", ident.this.lower())
    return ast


def _canon_aliases(ast):
    """Rename table aliases to canonical names (table name, then table_2, ...). Returns False on conflicts."""
    mapping, counts = {}, {}
    for t in ast.find_all(exp.Table):
        name = t.name
        alias = t.alias_or_name
        counts[name] = counts.get(name, 0) + 1
        canon = name if counts[name] == 1 else f"{name}_{counts[name]}"
        if alias in mapping and mapping[alias] != canon:
            return False
        mapping[alias] = canon
    # derived tables / CTE names keep their alias; only base-table aliases are renamed
    for t in ast.find_all(exp.Table):
        canon = mapping[t.alias_or_name]
        if canon == t.name:
            t.set("alias", None)
        else:
            t.set("alias", exp.TableAlias(this=exp.to_identifier(canon)))
    for c in ast.find_all(exp.Column):
        if c.table and c.table in mapping:
            c.set("table", exp.to_identifier(mapping[c.table]))
    return True


def _strip_select_aliases(sel):
    aliases = {}
    new_exprs = []
    for e in sel.expressions:
        if isinstance(e, exp.Alias):
            aliases[e.alias] = e.this
            new_exprs.append(e.this)
        else:
            new_exprs.append(e)
    sel.set("expressions", new_exprs)
    order = sel.args.get("order")
    if order is not None:
        for o in order.expressions:
            t = o.this
            if isinstance(t, exp.Column) and not t.table and t.name in aliases:
                o.set("this", aliases[t.name].copy())
    for key in ("group", "having"):
        node = sel.args.get(key)
        if node is None:
            continue
        for c in list(node.find_all(exp.Column)):
            if not c.table and c.name in aliases:
                c.replace(aliases[c.name].copy())


def normalize_ast(sql, schema_lc):
    """Returns (ast, qualified_ok, alias_ok) or (None, False, False) on parse failure."""
    try:
        ast = sqlglot.parse_one(sql, read=DIALECT)
    except Exception:
        return None, False, False
    if ast is None:
        return None, False, False
    ast = _lower_identifiers(ast)
    qualified_ok = True
    try:
        ast = qualify(ast, dialect=DIALECT, schema=schema_lc, validate_qualify_columns=False,
                      quote_identifiers=False, identify=False)
    except Exception:
        qualified_ok = False
    alias_ok = _canon_aliases(ast)
    if isinstance(ast, exp.Select):
        _strip_select_aliases(ast)  # output names only; inner aliases may be referenced by outer scopes
    for sel in list(ast.find_all(exp.Select)):
        w = sel.args.get("where")
        if w is not None:
            w.set("this", _canon_pred(w.this))
        h = sel.args.get("having")
        if h is not None:
            h.set("this", _canon_pred(h.this))
        for j in sel.args.get("joins") or []:
            on = j.args.get("on")
            if on is not None:
                j.set("on", _canon_pred(on))
    return ast, qualified_ok, alias_ok


def normalized_key(ast):
    return sql_of(ast)


# ----------------------------------------------------------------------------------------------
# SPJ(+aggregate) blocks
# ----------------------------------------------------------------------------------------------

AGG_TYPES = (exp.AggFunc,)


def _has_agg(node):
    return any(isinstance(n, AGG_TYPES) for n in node.walk())


def _literal_value(node):
    if isinstance(node, exp.Neg) and isinstance(node.this, exp.Literal) and not node.this.is_string:
        v = _literal_value(node.this)
        return -v if v is not None else None
    if isinstance(node, exp.Literal):
        if node.is_string:
            return ("s", node.this)
        try:
            return ("n", float(node.this))
        except ValueError:
            return None
    if isinstance(node, exp.Cast) and isinstance(node.this, exp.Literal) and node.this.is_string:
        return ("s", node.this.this)
    return None


def _num_or_str(v):
    return v


class Pred:
    """Parsed simple comparison 'lhs op literal' for implication checks."""

    def __init__(self, node):
        self.node = node
        self.sql = sql_of(node)
        self.lhs = None
        self.op = None
        self.val = None
        ops = {exp.EQ: "=", exp.NEQ: "<>", exp.GT: ">", exp.GTE: ">=", exp.LT: "<", exp.LTE: "<="}
        if type(node) in ops:
            v = _literal_value(node.expression)
            if v is not None and _literal_value(node.this) is None:
                self.lhs, self.op, self.val = sql_of(node.this), ops[type(node)], v
        elif isinstance(node, exp.In) and not node.args.get("query"):
            vals = [_literal_value(e) for e in node.expressions]
            if vals and all(v is not None for v in vals):
                self.lhs, self.op, self.val = sql_of(node.this), "in", frozenset(vals)


def _cmp_ok(a, op, b):
    if a[0] != b[0]:
        return None
    x, y = a[1], b[1]
    return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y, "=": x == y}[op]


def implies(n, c):
    """True if predicate n implies predicate c (both Pred)."""
    if n.sql == c.sql:
        return True
    if n.lhs is None or c.lhs is None or n.lhs != c.lhs:
        return False
    if c.op == "in":
        if n.op == "=":
            return n.val in c.val
        if n.op == "in":
            return n.val <= c.val
        return False
    if n.op == "in":
        return all(implies_val(v, c) for v in n.val)
    if n.op == "=":
        return implies_val(n.val, c)
    if c.op in (">", ">=") and n.op in (">", ">="):
        r = _cmp_ok(n.val, ">" if (c.op == ">" and n.op == ">=") else ">=", c.val)
        return bool(r)
    if c.op in ("<", "<=") and n.op in ("<", "<="):
        r = _cmp_ok(n.val, "<" if (c.op == "<" and n.op == "<=") else "<=", c.val)
        return bool(r)
    return False


def implies_val(v, c):
    if c.op == "=":
        return v == c.val
    if c.op == "<>":
        return v[0] == c.val[0] and v != c.val
    if c.op == "in":
        return v in c.val
    r = _cmp_ok(v, c.op, c.val)
    return bool(r)


class Block:
    """A single SELECT over base tables with inner/cross (and optionally left) joins, no subqueries,
    no CTEs, no window functions."""

    def __init__(self):
        self.tables = ()
        self.left = ()
        self.join_preds = frozenset()
        self.filters = {}
        self.select = []
        self.distinct = False
        self.group = []
        self.having = None
        self.order = []
        self.limit = None
        self.offset = None
        self.has_agg = False
        self.base_cols = set()
        self.table_cols = {}

    @property
    def core(self):
        return (self.tables, self.left, self.join_preds)


def _int_literal(node):
    if node is None:
        return None
    e = node.expression if isinstance(node, (exp.Limit, exp.Offset)) else node
    if isinstance(e, exp.Literal) and not e.is_string:
        try:
            return int(e.this)
        except ValueError:
            return "bad"
    return "bad"


def extract_block(ast):
    if not isinstance(ast, exp.Select):
        return None
    if ast.args.get("with"):
        return None
    for n in ast.walk():
        if n is ast:
            continue
        if isinstance(n, (exp.Select, exp.Subquery, exp.Union, exp.Window, exp.Unnest, exp.Lateral)):
            return None
    fr = _from(ast)
    if fr is None or not isinstance(fr.this, exp.Table) or fr.this.args.get("db"):
        return None
    b = Block()
    tables = [fr.this]
    conjuncts = []
    left = []
    for j in ast.args.get("joins") or []:
        if not isinstance(j.this, exp.Table):
            return None
        side = (j.args.get("side") or "").upper()
        kind = (j.args.get("kind") or "").upper()
        if kind in ("SEMI", "ANTI", "ASOF", "POSITIONAL") or side in ("RIGHT", "FULL") or j.args.get("using"):
            return None
        on = j.args.get("on")
        if side == "LEFT":
            left.append((j.this.alias_or_name, sql_of(on) if on is not None else ""))
            continue
        tables.append(j.this)
        if on is not None:
            conjuncts.extend(_flatten(on, exp.And))
    w = ast.args.get("where")
    if w is not None:
        conjuncts.extend(_flatten(w.this, exp.And))
    names = [t.alias_or_name for t in tables]
    if len(set(names)) != len(names):
        return None
    b.tables = tuple(sorted(names))
    b.left = tuple(left)
    jp, filt = set(), {}
    for c in conjuncts:
        if (isinstance(c, exp.EQ) and isinstance(c.this, exp.Column) and isinstance(c.expression, exp.Column)
                and c.this.table != c.expression.table):
            jp.add(sql_of(c))
        else:
            filt[sql_of(c)] = c
    b.join_preds = frozenset(jp)
    b.filters = filt
    b.select = [(sql_of(e), e) for e in ast.expressions]
    if any(isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
           for _, e in b.select):
        return None  # unexpanded star (qualification failed)
    d = ast.args.get("distinct")
    if d is not None and d.args.get("on"):
        return None
    b.distinct = d is not None
    g = ast.args.get("group")
    b.group = [(sql_of(e), e) for e in g.expressions] if g is not None else []
    if g is not None and any(isinstance(e, exp.Literal) for _, e in b.group):
        return None
    h = ast.args.get("having")
    b.having = h.this if h is not None else None
    o = ast.args.get("order")
    b.order = [(sql_of(x.this), bool(x.args.get("desc")), x) for x in o.expressions] if o is not None else []
    b.limit = _int_literal(ast.args.get("limit"))
    b.offset = _int_literal(ast.args.get("offset"))
    if b.limit == "bad" or b.offset == "bad":
        return None
    b.has_agg = any(_has_agg(e) for _, e in b.select) or b.having is not None or bool(b.group)
    for c in ast.find_all(exp.Column):
        b.base_cols.add(sql_of(c))
        b.table_cols.setdefault(c.table, set()).add(c.name)
    return b


# ----------------------------------------------------------------------------------------------
# Containment: answer block q from a stored relation with defining block v
# ----------------------------------------------------------------------------------------------

def _map_expr(node, vmap, strict_agg=False):
    """Rewrite node over relation columns. strict_agg: the relation is already aggregated, so every
    aggregate call (and '*') must match a relation column exactly."""
    s = sql_of(node)
    if s in vmap:
        return exp.column(vmap[s])
    if isinstance(node, exp.Column):
        raise NotMappable(s)
    if strict_agg and isinstance(node, (exp.AggFunc, exp.Star)):
        raise NotMappable(s)
    node = node.copy()
    for key, val in list(node.args.items()):
        if isinstance(val, exp.Expression):
            node.set(key, _map_expr(val, vmap, strict_agg))
        elif isinstance(val, list):
            node.set(key, [_map_expr(v, vmap, strict_agg) if isinstance(v, exp.Expression) else v for v in val])
    return node


def _reagg(node, vmap, vgroup_sqls, q_has_group):
    """Map a q expression over a finer-grained aggregated relation (roll-up)."""
    s = sql_of(node)
    if isinstance(node, exp.AggFunc):
        if isinstance(node, exp.Count):
            inner = node.this
            if isinstance(inner, exp.Distinct):
                args = inner.expressions
                if len(args) == 1 and sql_of(args[0]) in vgroup_sqls and sql_of(args[0]) in vmap:
                    return exp.Count(this=exp.Distinct(expressions=[exp.column(vmap[sql_of(args[0])])]))
                raise NotMappable(s)
            if s in vmap:
                summed = exp.Sum(this=exp.column(vmap[s]))
                return summed if q_has_group else exp.func("coalesce", summed, exp.Literal.number(0))
            raise NotMappable(s)
        if isinstance(node, exp.Sum) and s in vmap:
            return exp.Sum(this=exp.column(vmap[s]))
        if isinstance(node, (exp.Min, exp.Max)):
            if s in vmap:
                return node.__class__(this=exp.column(vmap[s]))
            arg = node.this
            if sql_of(arg) in vgroup_sqls and sql_of(arg) in vmap:
                return node.__class__(this=exp.column(vmap[sql_of(arg)]))
            raise NotMappable(s)
        if isinstance(node, exp.Avg):
            arg = sql_of(node.this)
            ssum, scnt = f"SUM({arg})", f"COUNT({arg})"
            if ssum in vmap and scnt in vmap:
                return exp.Div(this=exp.Cast(this=exp.Sum(this=exp.column(vmap[ssum])), to=exp.DataType.build("DOUBLE")),
                               expression=exp.Sum(this=exp.column(vmap[scnt])))
            raise NotMappable(s)
        raise NotMappable(s)
    if s in vmap and s in vgroup_sqls:
        return exp.column(vmap[s])
    if isinstance(node, exp.Column):
        raise NotMappable(s)
    node = node.copy()
    for key, val in list(node.args.items()):
        if isinstance(val, exp.Expression):
            node.set(key, _reagg(val, vmap, vgroup_sqls, q_has_group))
        elif isinstance(val, list):
            node.set(key, [_reagg(v, vmap, vgroup_sqls, q_has_group) if isinstance(v, exp.Expression) else v
                           for v in val])
    return node


def _filters_implied(q, v):
    qp = [Pred(n) for n in q.filters.values()]
    for s, node in v.filters.items():
        if s in q.filters:
            continue
        c = Pred(node)
        if not any(implies(n, c) for n in qp):
            return False
    return True


def containment_sql(q, v, rel, v_nrows):
    """Return (kind, compensation_sql) if block q is answerable from relation `rel` holding the result of
    block v (columns c0..cn in v.select order, plus __rn preserving v's output order), else None."""
    if q is None or v is None or q.core != v.core or v.offset is not None or v.having is not None:
        return None
    if not _filters_implied(q, v):
        return None
    vmap = {}
    for i, (s, _) in enumerate(v.select):
        vmap.setdefault(s, f"c{i}")
    residual = [n for s, n in q.filters.items() if s not in v.filters]
    v_complete = v.limit is None or v_nrows < v.limit
    try:
        if not v_complete:
            # LIMIT-subset: same query up to LIMIT/OFFSET, same ORDER BY, projection of a prefix.
            if (residual or set(q.filters) != set(v.filters) or [g for g, _ in q.group] != [g for g, _ in v.group]
                    or q.having is not None or q.distinct != v.distinct or q.limit is None
                    or [(s, d) for s, d, _ in q.order] != [(s, d) for s, d, _ in v.order]):
                return None
            if (q.offset or 0) + q.limit > v.limit:
                return None
            if q.distinct and {s for s, _ in q.select} != {s for s, _ in v.select}:
                return None
            sel = exp.select(*[_map_expr(e, vmap, v.has_agg) for _, e in q.select]).from_(rel)
            sel = sel.order_by(exp.column("__rn")).limit(q.limit)
            if q.offset:
                sel = sel.offset(q.offset)
            return "limit_subset", sel.sql(dialect=DIALECT)
        if not v.has_agg:
            if v.distinct and not (q.distinct and not q.has_agg):
                return None
            sel = exp.select(*[_map_expr(e, vmap) for _, e in q.select]).from_(rel)
            if residual:
                sel = sel.where(exp.and_(*[_map_expr(n, vmap) for n in residual]))
            if q.group:
                sel = sel.group_by(*[_map_expr(e, vmap) for _, e in q.group])
            if q.having is not None:
                sel = sel.having(_map_expr(q.having, vmap))
            kind = "reaggregate" if q.has_agg else ("project_filter" if residual else "project")
        else:
            if not q.has_agg or v.distinct:
                return None
            vgroup = {s for s, _ in v.group}
            qgroup = {s for s, _ in q.group}
            if not qgroup <= vgroup:
                return None
            # residual predicates may only touch grouping columns (they commute with the aggregation)
            gmap = {s: vmap[s] for s in vgroup if s in vmap}
            mapped_res = [_map_expr(n, gmap) for n in residual]
            if qgroup == vgroup:
                sel = exp.select(*[_map_expr(e, vmap, True) for _, e in q.select]).from_(rel)
                conds = mapped_res + ([_map_expr(q.having, vmap, True)] if q.having is not None else [])
                if conds:
                    sel = sel.where(exp.and_(*conds))
                kind = "same_grouping"
            else:
                has_g = bool(q.group)
                sel = exp.select(*[_reagg(e, vmap, vgroup, has_g) for _, e in q.select]).from_(rel)
                if mapped_res:
                    sel = sel.where(exp.and_(*mapped_res))
                if q.group:
                    sel = sel.group_by(*[_map_expr(e, gmap) for _, e in q.group])
                if q.having is not None:
                    sel = sel.having(_reagg(q.having, vmap, vgroup, has_g))
                kind = "rollup"
        if q.distinct:
            sel = sel.distinct()
        if q.order:
            if v.has_agg and set(s for s, _ in q.group) != set(s for s, _ in v.group):
                ords = [_reagg(o.this, vmap, {s for s, _ in v.group}, bool(q.group)) for _, _, o in q.order]
            else:
                ords = [_map_expr(o.this, vmap, v.has_agg) for _, _, o in q.order]
            new_ords = []
            for x, (_, _, o) in zip(ords, q.order):
                o2 = o.copy()
                o2.set("this", x)
                new_ords.append(o2)
            sel = sel.order_by(*new_ords)
        if q.limit is not None:
            sel = sel.limit(q.limit)
        if q.offset:
            sel = sel.offset(q.offset)
        return kind, sel.sql(dialect=DIALECT)
    except NotMappable:
        return None


# ----------------------------------------------------------------------------------------------
# Sub-expression signatures
# ----------------------------------------------------------------------------------------------

def _single_table_conjuncts(sel):
    """For one SELECT scope with only inner/cross joins: {alias: [conjunct nodes referencing only alias]}."""
    for j in sel.args.get("joins") or []:
        side = (j.args.get("side") or "").upper()
        kind = (j.args.get("kind") or "").upper()
        if side or kind in ("SEMI", "ANTI", "ASOF", "POSITIONAL") or j.args.get("using"):
            return None
    conj = []
    w = sel.args.get("where")
    if w is not None:
        conj.extend(_flatten(w.this, exp.And))
    for j in sel.args.get("joins") or []:
        on = j.args.get("on")
        if on is not None:
            conj.extend(_flatten(on, exp.And))
    out = {}
    for c in conj:
        if any(isinstance(n, (exp.Select, exp.Subquery)) for n in c.walk()):
            continue
        tabs = {col.table for col in c.find_all(exp.Column)}
        if len(tabs) == 1:
            out.setdefault(next(iter(tabs)), []).append(c)
    return out


def scan_units(ast):
    """Filtered-scan units in every SELECT scope: list of (alias, table, filter_key, conjunct_sqls)."""
    units = []
    for sel in ast.find_all(exp.Select):
        fr = _from(sel)
        if fr is None:
            continue
        stc = _single_table_conjuncts(sel)
        if not stc:
            continue
        srcs = [fr.this] + [j.this for j in (sel.args.get("joins") or [])]
        for t in srcs:
            if not isinstance(t, exp.Table):
                continue
            alias = t.alias_or_name
            conj = stc.get(alias)
            if not conj:
                continue
            # express conjuncts with the base table name (alias-independent key)
            sqls = []
            for c in conj:
                c2 = c.copy()
                for col in c2.find_all(exp.Column):
                    col.set("table", exp.to_identifier(t.name))
                sqls.append(sql_of(c2))
            units.append((alias, t.name, tuple(sorted(set(sqls)))))
    return units


def join_subtrees(block, max_tables=5):
    """Connected join sub-trees (>= 2 tables) of an inner-join block, as (tables, join_preds) keys,
    with and without the block's single-table filters on those tables."""
    if block is None or block.left or len(block.tables) < 2 or len(block.tables) > max_tables:
        return set(), set()
    edges = []
    for p in block.join_preds:
        node = sqlglot.parse_one(p, read=DIALECT)
        tabs = tuple(sorted({c.table for c in node.find_all(exp.Column)}))
        if len(tabs) == 2:
            edges.append((tabs, p))
    filt_by_table = {}
    for s, n in block.filters.items():
        tabs = {c.table for c in n.find_all(exp.Column)}
        if len(tabs) == 1:
            filt_by_table.setdefault(next(iter(tabs)), []).append(s)
    bare, filtered = set(), set()
    tabs = list(block.tables)
    for k in range(2, len(tabs) + 1):
        for subset in itertools.combinations(tabs, k):
            ss = set(subset)
            es = [p for (a, b), p in edges if a in ss and b in ss]
            # connectivity check
            seen, frontier = {subset[0]}, [subset[0]]
            while frontier:
                x = frontier.pop()
                for (a, b), _ in edges:
                    if a in ss and b in ss and (a == x or b == x):
                        y = b if a == x else a
                        if y not in seen:
                            seen.add(y)
                            frontier.append(y)
            if seen != ss:
                continue
            key = (tuple(sorted(subset)), tuple(sorted(es)))
            bare.add(key)
            fk = tuple(sorted(f for t in subset for f in filt_by_table.get(t, [])))
            filtered.add(key + (fk,))
    return bare, filtered
