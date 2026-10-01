"""E1b/E1c: adversarial suite with expected verdicts + property-based bounded-instance testing.

For each boundary query: (1) the certificate must match the expected verdict; (2) on many random small
instances, each loaded in several physical insertion orders and thread settings, the certified execution
(DET: unchanged, NARROW/ALL: rewritten) must show the same observation everywhere; (3) the raw query's
divergence is recorded to show the test has power.

Usage: python adversarial.py <out.json> [n_instances] [n_perms]
"""
import datetime
import hashlib
import json
import random
import sys

import duckdb

from certify import certify
from tool import canon

SCHEMA = {
    "emp": {"columns": {"id": "INTEGER", "name": "VARCHAR", "dept_id": "INTEGER", "salary": "INTEGER",
                        "bonus": "DOUBLE", "email": "VARCHAR"}, "keys": [["id"]]},
    "dept": {"columns": {"id": "INTEGER", "dname": "VARCHAR"}, "keys": [["id"]]},
    "log": {"columns": {"ts": "INTEGER", "emp_id": "INTEGER", "msg": "VARCHAR"}, "keys": []},
    "pair": {"columns": {"a": "INTEGER", "b": "INTEGER", "v": "VARCHAR"}, "keys": [["a", "b"]]},
    "code": {"columns": {"c": "VARCHAR", "n": "INTEGER"}, "keys": []},
    "lst": {"columns": {"xs": "DOUBLE[]"}, "keys": []},
    "f": {"columns": {"x": "DOUBLE"}, "keys": []},
    "kk": {"columns": {"wide": "VARCHAR", "narrow": "INTEGER", "x": "VARCHAR", "y": "VARCHAR"},
           "keys": [["wide"], ["narrow"]]},
    "ev": {"columns": {"id": "INTEGER", "d": "DATE", "name": "VARCHAR"}, "keys": [["id"]]},
}

CASES = [
    ("SELECT id, name FROM emp ORDER BY id", "DET"),
    ("SELECT name FROM emp ORDER BY id LIMIT 3", "DET"),
    ("SELECT name FROM emp ORDER BY name LIMIT 3", "DET"),
    ("SELECT name, salary FROM emp ORDER BY salary DESC LIMIT 2", "NARROW"),
    ("SELECT dept_id, COUNT(*) FROM emp GROUP BY dept_id ORDER BY 2 DESC", "NARROW"),
    ("SELECT DISTINCT dept_id FROM emp", "ALL"),
    ("SELECT e.name, d.dname FROM emp e JOIN dept d ON e.dept_id = d.id ORDER BY e.id", "DET"),
    ("SELECT e.name, d.dname FROM emp e JOIN dept d ON e.dept_id = d.id ORDER BY d.id", "NARROW"),
    ("SELECT msg FROM log ORDER BY ts", "ALL"),
    ("SELECT * FROM log LIMIT 5", "ALL"),
    ("SELECT email, name FROM emp ORDER BY email LIMIT 3", "NARROW"),
    ("SELECT SUM(bonus) FROM emp", "UNSUPPORTED"),
    ("SELECT SUM(salary) FROM emp", "DET"),
    ("SELECT name FROM emp e LEFT JOIN dept d ON e.dept_id = d.id", "UNSUPPORTED"),
    ("SELECT * FROM (SELECT * FROM emp ORDER BY salary LIMIT 3) t", "UNSUPPORTED"),
    ("SELECT name FROM emp WHERE id = 3", "DET"),
    ("SELECT name FROM emp WHERE dept_id = 1 ORDER BY LENGTH(name)", "NARROW"),
    ("SELECT a, v FROM pair ORDER BY a", "NARROW"),
    ("SELECT name FROM emp ORDER BY random()", "UNSUPPORTED"),
    ("SELECT dept_id, AVG(salary) FROM emp GROUP BY dept_id HAVING COUNT(*) > 1 ORDER BY dept_id", "DET"),
    ("SELECT name FROM emp UNION SELECT dname FROM dept", "UNSUPPORTED"),
    ("SELECT name, (SELECT COUNT(*) FROM log l WHERE l.emp_id = e.id) AS n FROM emp e ORDER BY e.id", "DET"),
    ("SELECT name FROM emp WHERE salary > (SELECT AVG(bonus) FROM emp) ORDER BY id", "UNSUPPORTED"),
    ("SELECT DISTINCT e.id, e.name FROM emp e", "NARROW"),
    ("SELECT name, salary FROM emp ORDER BY salary, name LIMIT 5", "DET"),
    ("SELECT d.dname, COUNT(*) AS n FROM emp e JOIN dept d ON e.dept_id = d.id GROUP BY d.dname ORDER BY n DESC LIMIT 2", "NARROW"),
    ("SELECT e.name FROM emp e, dept d WHERE e.dept_id = d.id AND d.id = 2 ORDER BY e.salary", "NARROW"),
    ("SELECT ts, msg FROM log WHERE emp_id = 1 ORDER BY ts, msg LIMIT 3", "DET"),
    ("SELECT emp_id, MAX(ts) FROM log GROUP BY emp_id", "NARROW"),
    ("SELECT name FROM emp ORDER BY salary; SELECT 1", "UNSUPPORTED"),
    ("SELECT e.name, d.dname FROM emp e, dept d WHERE e.dept_id = d.id ORDER BY e.id", "DET"),
    ("SELECT d.id, c.c FROM dept d JOIN code c ON c.c = d.id ORDER BY d.id", "NARROW"),
    # code-review round 1 counterexamples and completeness cases
    ("SELECT DISTINCT id % 2 AS parity, name FROM emp LIMIT 1", "ALL"),
    ("SELECT id % 2 AS parity, name, COUNT(*) FROM emp GROUP BY id % 2, name LIMIT 1", "NARROW"),
    ("SELECT DISTINCT COUNT(*) FROM emp GROUP BY dept_id LIMIT 1", "ALL"),
    ("SELECT name, salary FROM emp ORDER BY salary FETCH FIRST 1 ROWS WITH TIES", "UNSUPPORTED"),
    ("SELECT name FROM emp LIMIT 10%", "UNSUPPORTED"),
    ("SELECT now() AS t FROM emp", "UNSUPPORTED"),
    ("SELECT name COLLATE nocase AS x FROM emp ORDER BY x LIMIT 1", "UNSUPPORTED"),
    ("SELECT dept_id, COUNT(*) FROM emp GROUP BY dept_id HAVING dept_id = 1", "DET"),
    ("SELECT COUNT(*) FROM emp GROUP BY dept_id, name", "ALL"),
    ("SELECT name FROM emp", "NARROW"),
    # code-review round 2 counterexamples
    ("SELECT name, salary FROM emp ORDER BY ALL LIMIT 1", "DET"),
    ("SELECT dept_id, COUNT(*) FROM emp GROUP BY ALL LIMIT 1", "UNSUPPORTED"),
    ("SELECT xs FROM lst ORDER BY xs LIMIT 1", "DET"),  # [-0.0] and [0.0] tie and must render alike
    # code-review round 3 counterexamples
    ("SELECT 1.0 / x AS y FROM f ORDER BY x LIMIT 1", "ALL"),  # -0.0 and 0.0 tie, 1/x differs
    ("SELECT x, 1.0 / x AS y FROM f LIMIT 1", "ALL"),
    ("SELECT 1.0 / MAX(x) FROM f WHERE x = 0", "UNSUPPORTED"),  # MAX returns either zero
    ("SELECT MAX(x) FROM f WHERE x = 0", "DET"),  # either zero renders as 0.0
    ("SELECT x, COUNT(*) FROM f GROUP BY x", "UNSUPPORTED"),
    ("SELECT (SELECT DISTINCT ON (i.dept_id) i.name FROM emp i WHERE i.dept_id = e.dept_id) AS n FROM emp e "
     "WHERE e.id = 1", "UNSUPPORTED"),
    ("WITH c AS (SELECT id FROM emp) SELECT id FROM c", "UNSUPPORTED"),
    ("SELECT x, y FROM kk", "NARROW"),
]
EXPECT_TIE = {"SELECT x, y FROM kk": ['"kk"."narrow"']}  # the 8-byte key, not the text key
# verdict-only checks for the PostgreSQL dialect (relative time inputs are evaluated against the clock)
PG_CASES = [
    ("SELECT TIMESTAMP 'now' FROM emp", "UNSUPPORTED"),
    ("SELECT CAST('today' AS DATE) FROM emp", "UNSUPPORTED"),
    ("SELECT CAST(name AS TIMESTAMP) FROM emp", "UNSUPPORTED"),
    ("SELECT name FROM emp WHERE id = 3", "DET"),
    ("SELECT name, salary FROM emp ORDER BY salary DESC LIMIT 2", "NARROW"),
    ("SELECT name FROM emp WHERE name = 'now'", "DET"),  # a text comparison, not a time input
    ("SELECT name FROM ev WHERE 'today' IN (d)", "UNSUPPORTED"),  # 'today' is read as a date here
    ("SELECT name FROM ev WHERE 'now' IN (name)", "NARROW"),  # plain text
]
# the harness must detect divergence where the raw query is order-dependent (power check)
MUST_DIVERGE_RAW = {"SELECT name, salary FROM emp ORDER BY salary DESC LIMIT 2", "SELECT DISTINCT dept_id FROM emp",
                    "SELECT * FROM log LIMIT 5", "SELECT name FROM emp ORDER BY random()"}


def instance(rng):
    names = ["ann", "bob", "cy", "dee", "ed", "fay"]
    emp = []
    for i in range(1, 31):
        email = None if rng.random() < 0.3 else f"u{i}@x"
        emp.append((i, rng.choice(names), rng.randint(1, 4), rng.choice([10, 20, 30]), rng.uniform(0, 1e6) * 1e-3, email))
    dept = [(i, rng.choice(["ops", "eng", "hr"])) for i in range(1, 5)]
    log = [(rng.randint(1, 5), rng.randint(1, 30), rng.choice(["a", "b", "c"])) for _ in range(40)]
    log += log[:8]  # exact duplicates
    pair = [(a, b, rng.choice(["x", "y"])) for a in range(1, 5) for b in range(1, 6)]
    code = [(s, i) for i, s in enumerate(["1", "01", "2", "02", "3", "003", "4"])]  # text equal to ints after a cast
    lst = [([-0.0],), ([0.0],)]  # SQL-equal lists that str() renders differently
    f = [(0.0,), (-0.0,), (1.5,)]
    kk = [(f"w{i:02d}", i, "a" if i % 2 else "b", "c") for i in range(10)]
    ev = [(1, datetime.date(2026, 9, 25), "old"), (2, datetime.date(2026, 9, 26), "new")]
    return {"emp": emp, "dept": dept, "log": log, "pair": pair, "code": code, "lst": lst, "f": f, "kk": kk, "ev": ev}


def load(data, perm_seed, threads):
    con = duckdb.connect(":memory:")
    con.execute(f"SET threads={threads}")
    r = random.Random(perm_seed)
    for t, spec in SCHEMA.items():
        cols = ", ".join(f"{c} {ty}" for c, ty in spec["columns"].items())
        con.execute(f"CREATE TABLE {t} ({cols})")
        rows = list(data[t])
        r.shuffle(rows)
        con.executemany(f"INSERT INTO {t} VALUES ({', '.join('?' * len(spec['columns']))})", rows)
    return con


def observe(con, sql, k=20):
    """(ok, observation digest) or (False, error class)."""
    try:
        cur = con.execute(sql)
        rows = cur.fetchall()
    except Exception as ex:  # noqa: BLE001
        return False, "ERR:" + type(ex).__name__
    head = [d[0] for d in cur.description]
    rendered = [[str(canon(v)) for v in x] for x in rows[:k]]  # the study tool's canonical rendering
    return True, hashlib.sha1(json.dumps([head, len(rows), rendered]).encode()).hexdigest()


def main(out_path, n_inst=30, n_perm=6):
    res = []
    for sql, expected in CASES:
        cert = certify(sql, SCHEMA, "duckdb")
        run_sql = cert.rewritten or sql
        raw_div = cert_div = cert_fail = 0
        for i in range(n_inst):
            data = instance(random.Random(1000 + i))
            raw_obs, cert_obs = set(), set()
            for p in range(n_perm):
                con = load(data, 7 * p + 1, 1 if p % 2 == 0 else 4)
                raw_obs.add(observe(con, sql)[1])
                if cert.verdict != "UNSUPPORTED":
                    ok, o = observe(con, run_sql)
                    if ok:
                        cert_obs.add(o)
                    else:  # a certified execution must succeed; an error is a failure, not an observation
                        cert_fail += 1
                con.close()
            raw_div += len(raw_obs) > 1
            cert_div += len(cert_obs) > 1
        tie_ok = sql not in EXPECT_TIE or cert.tie_break == EXPECT_TIE[sql]
        ok_case = cert.verdict == expected and cert_div == 0 and cert_fail == 0 and tie_ok
        res.append({"sql": sql, "expected": expected, "verdict": cert.verdict, "reason": cert.reason,
                    "tie_break": cert.tie_break, "rewritten": cert.rewritten, "verdict_ok": cert.verdict == expected,
                    "raw_diverged_instances": raw_div, "certified_diverged_instances": cert_div,
                    "certified_failed_executions": cert_fail, "n_instances": n_inst, "pass": ok_case})
        print(f"{'OK ' if ok_case else 'BAD'} {cert.verdict:11s} (exp {expected:11s}) raw_div {raw_div:2d}/{n_inst} "
              f"cert_div {cert_div:2d}/{n_inst} cert_fail {cert_fail} | {sql[:80]} | {cert.tie_break}", flush=True)
    json.dump(res, open(out_path, "w"), indent=1)
    power = [r for r in res if r["sql"] in MUST_DIVERGE_RAW]
    print("cases passed:", sum(r["pass"] for r in res), "/", len(res),
          "| verdicts correct:", sum(r["verdict_ok"] for r in res),
          "| certified divergences:", sum(r["certified_diverged_instances"] for r in res),
          "| certified failed executions:", sum(r["certified_failed_executions"] for r in res),
          "| power: raw diverged in", sum(r["raw_diverged_instances"] > 0 for r in power), "of", len(power), "designated cases")
    pg = [(sql, expected, certify(sql, SCHEMA, "postgres").verdict) for sql, expected in PG_CASES]
    for sql, expected, got in pg:
        print(f"{'OK ' if got == expected else 'BAD'} postgres {got:11s} (exp {expected:11s}) | {sql}")
    cases_ok = all(r["pass"] for r in res) and all(got == expected for _, expected, got in pg)
    power_ok = all(r["raw_diverged_instances"] > 0 for r in power)
    if not cases_ok or not power_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1], *(int(x) for x in sys.argv[2:4]))
