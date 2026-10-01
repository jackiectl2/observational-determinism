"""Certifier v7 (md5 1369ffca, used by the running reruns) vs the final candidate: verdict and tie-break differences on
every statement set, both dialects. (v7_diff2_ext.py: v7_diff2.py extended to accept cert_*.jsonl
statement files among the extra arguments.) Usage: python v7_diff2_ext.py <old.py> <new.py> <out.json> [extra trace dirs...]"""
import glob
import importlib.util
import json
import os
import sys

V = os.environ["PROJECT_ROOT"]
R = f"{V}/runs/obsdet"
sys.path.insert(0, f"{V}/code/obsdet_v7")  # pg_cost.to_pg


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jsonl(p):
    return [json.loads(line) for line in open(p)]


def main(old_path, new_path, out_path, *extra):
    old, new = load_mod("c_old", old_path), load_mod("c_new", new_path)
    from pg_cost import to_pg
    cat = json.load(open(f"{R}/catalog.json"))
    sets = {"dev": f"{R}/cert_probes_v6.jsonl", "heldout_all": f"{R}/cert_heldout_all.jsonl", "td_all": f"{R}/cert_td_all.jsonl"}
    items = {k: {(r["db_id"], r["sql"]) for r in jsonl(p)} for k, p in sets.items()}
    for d in sorted(glob.glob(f"{R}/e4/v5_*")) + sorted(glob.glob(f"{R}/e4/v6td_*")) + list(extra):
        src = d if d.endswith(".jsonl") else f"{d}/trace.jsonl"  # extension: statement files (cert_*.jsonl) too
        items[d.rstrip("/").split("/")[-1]] = {(r["db_id"], r["sql"]) for r in jsonl(src) if r.get("sql")}
    report = {}
    for name, its in items.items():
        diffs = []
        for db, sql in sorted(its):
            if db not in cat:
                continue
            for dialect, text in (("duckdb", sql), ("postgres", None)):
                if dialect == "postgres":
                    try:
                        text = to_pg(sql)
                    except Exception:  # noqa: BLE001
                        continue
                a, b = old.certify(text, cat[db], dialect), new.certify(text, cat[db], dialect)
                if (a.verdict, a.tie_break) != (b.verdict, b.tie_break):
                    diffs.append({"db_id": db, "dialect": dialect, "sql": sql, "old": [a.verdict, a.reason, a.tie_break],
                                  "new": [b.verdict, b.reason, b.tie_break]})
        report[name] = {"n": len(its), "diffs": diffs}
        print(name, "n", len(its), "diffs", len(diffs))
        for x in diffs:
            print("   ", x["dialect"], x["db_id"], x["old"][:2], "->", x["new"][:2], "|", x["sql"][:120].replace("\n", " "))
    json.dump(report, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
