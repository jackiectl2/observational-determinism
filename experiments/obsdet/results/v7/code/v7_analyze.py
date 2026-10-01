"""Certifier v7 evaluation: tables for RESULTS_V7.md from the copied run outputs (results/v7/).

Agent level, per E4 run (analyze3.py summary_e4.json): per-group traj / final SQL / result / correctness changes (with
censoring), unattributed divergence and same-SQL observation-change sources, accuracy (set, bag), paired differences,
statement verdicts under hybrid/strict, strict burden (frozen strict_burden.py, output captured), and every same-SQL
observation change that originated in a certified (DET/NARROW/ALL) statement.
Statement sets (dev, first held-out, task-disjoint, second task-disjoint): verdict distribution and widths
(distribution.py output), soundness counts per engine via row() of figures/gen_table_soundness.py (imported
unchanged, plotting module stubbed), per-verdict tables via heldout_dedup.table, and the certified divergences.
Missing inputs (runs not finished yet) are reported as missing.

Usage: python v7_analyze.py <results_v7_dir> <out.json>
"""
import contextlib
import io
import itertools
import json
import os
import sys
import types
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OBS = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # experiments/obsdet
FINAL = os.path.join(OBS, "results", "final")
sys.modules["paper_plot_style"] = types.SimpleNamespace(DATA=FINAL, OUT=None)
sys.path.insert(0, os.path.join(OBS, "..", "..", "figures"))
from gen_table_soundness import row, SUP  # noqa: E402  (puts results/final/code on sys.path)
from heldout_dedup import norm, table  # noqa: E402
import strict_burden  # noqa: E402  (frozen copy in results/final/code)

GROUPS = [("raw_phys", "raw, 3 physical orders"), ("slx_phys", "smart-lex, 3 physical orders"),
          ("cer_phys", "hybrid (certified), 3 physical orders"), ("str_phys", "strict (fail-closed), 3 physical orders"),
          ("raw_threads", "raw, 1 vs 8 threads"), ("cer_threads", "hybrid, 1 vs 8 threads"),
          ("str_threads", "strict, 1 vs 8 threads")]
GC = {"raw_phys": ["raw_orig_t1", "raw_p42_t1", "raw_p7_t1"], "slx_phys": ["slx_orig_t1", "slx_p42_t1", "slx_p7_t1"],
      "cer_phys": ["cer_orig_t1", "cer_p42_t1", "cer_p7_t1"], "str_phys": ["str_orig_t1", "str_p42_t1", "str_p7_t1"],
      "raw_threads": ["raw_orig_t1", "raw_orig_t8"], "cer_threads": ["cer_orig_t1", "cer_orig_t8"],
      "str_threads": ["str_orig_t1", "str_orig_t8"]}
FLAGS = ["traj_changed", "final_sql_changed", "final_result_changed", "correctness_changed"]
RUNS = [("v7", "tasks_v2 (E4 original tasks)"), ("v7td", "tasks_v3 (first task-disjoint set)"),
        ("v7td2", "tasks_v4 (second task-disjoint set)")]
MODELS = [("qwen3_8b", "Qwen3-8B"), ("phi4", "phi-4")]
SETS = [("dev", "Development probes", "cert_probes_v7.jsonl", "distribution_v7.json", "sound_v7.jsonl", "sound_pg_v7.jsonl"),
        ("heldout", "First held-out", "cert_heldout_kept_v7.jsonl", "distribution_heldout_v7.json",
         "sound_heldout_v7.jsonl", "sound_pg_heldout_v7.jsonl"),
        ("td", "First task-disjoint", "cert_td_new_v7.jsonl", "distribution_td_v7.json", "sound_td_v7.jsonl",
         "sound_pg_td_v7.jsonl"),
        ("td2", "Second task-disjoint (clean test)", "cert_td2_new.jsonl", "distribution_td2.json", "sound_td2.jsonl",
         "sound_pg_td2.jsonl")]


def certified_changes(d):
    """Same-SQL observation changes whose statement was certified (DET/NARROW/ALL) and succeeded in both runs."""
    steps = defaultdict(list)
    for line in open(os.path.join(d, "trace.jsonl")):
        r = json.loads(line)
        src = ("refused" if r["meta"].get("refused") else "runtime-error" if not r["success"]
               else "count-failure" if r["truncated"] else r["meta"].get("verdict") or r["meta"].get("path"))
        steps[(r["cond"], r["task_id"])].append((r["turn"], r["is_final"], r["sql"], r["obs_sha1"], src, r))
    for k in steps:
        steps[k].sort(key=lambda s: s[:5])
    out = []
    for g, cs in GC.items():
        for t in sorted({t for (_, t) in steps}):
            for i, j in itertools.combinations(range(len(cs)), 2):
                a, b = steps[(cs[i], t)], steps[(cs[j], t)]
                for x in range(min(len(a), len(b))):
                    if a[x][2] == b[x][2] and a[x][3] != b[x][3] and a[x][4] in SUP and b[x][4] in SUP:
                        out.append({"group": g, "task_id": t, "conds": [cs[i], cs[j]], "turn": a[x][0],
                                    "is_final": a[x][1], "verdict": a[x][4], "sql": a[x][2],
                                    "exec_sql": a[x][5]["exec_sql"], "obs": [a[x][5]["obs"], b[x][5]["obs"]]})
    return out


def e4_block(d, name):
    s = json.load(open(os.path.join(d, "summary_e4.json")))["all"]
    rows = {}
    for g, _ in GROUPS:
        st = s["stability"][g]
        rows[g] = {"counts": [st[f]["count"] for f in FLAGS], "censored": [st[f]["censored"] for f in FLAGS],
                   "n": st["traj_changed"]["n"], "unattributed": st["unattributed_divergence"]["count"],
                   "obs_same_sql": st["obs_diverged_same_sql"]["count"],
                   "sources": s.get("divergent_statement_sources", {}).get(g, {})}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        strict_burden.main(d)
    full = json.load(open(os.path.join(d, "summary_e4.json")))
    return {"name": name, "groups": rows, "accuracy": s["accuracy"], "bag_accuracy": s["bag_accuracy"],
            "paired": s["paired_accuracy"], "verdicts": full["certified_statement_verdicts"],
            "strict_burden": buf.getvalue().strip().split(": ", 1)[-1], "certified_changes": certified_changes(d)}


def fmt(r):
    c = [str(x) for x in r["counts"]]
    if r["censored"][2]:
        c[2] += f" (cens. {r['censored'][2]})"
    return " / ".join(c)


def acc_range(acc, bag, prefix):
    cs = sorted(c for c in acc if c.startswith(prefix))
    a = [acc[c]["mean"] for c in cs]
    b = [bag[c] for c in cs]
    return f"{min(a):.3f}–{max(a):.3f} ({min(b):.3f}–{max(b):.3f})" if min(a) != max(a) or min(b) != max(b) else \
        f"{a[0]:.3f} ({b[0]:.3f})"


def main(vdir, out_path):
    res, L = {"e4": {}, "sets": {}}, []
    for tag, label in RUNS:
        blocks = {}
        for m, mn in MODELS:
            d = os.path.join(vdir, f"e4_{tag}_{m}")
            if os.path.exists(os.path.join(d, "summary_e4.json")):
                blocks[m] = e4_block(d, mn)
        res["e4"][tag] = blocks
        L += [f"### E4 v7 on {label} (runs {', '.join(f'e4_{tag}_{m}' for m, _ in MODELS)})", ""]
        if not blocks:
            L += ["(not available yet)", ""]
            continue
        ms = [m for m, _ in MODELS if m in blocks]
        L += ["| Group | " + " | ".join(f"{blocks[m]['name']} traj / final SQL / result / correctness" for m in ms) + " |",
              "|---|" + "---|" * len(ms)]
        for g, gl in GROUPS:
            L.append(f"| {gl} | " + " | ".join(fmt(blocks[m]["groups"][g]) for m in ms) + " |")
        L += ["", "| Group | " + " | ".join(f"{blocks[m]['name']} unattributed; same-SQL observation-change sources" for m in ms) + " |",
              "|---|" + "---|" * len(ms)]
        for g, gl in GROUPS:
            L.append(f"| {gl} | " + " | ".join(
                f"{blocks[m]['groups'][g]['unattributed']}/{blocks[m]['groups'][g]['n']}; "
                f"{json.dumps(blocks[m]['groups'][g]['sources'])}" for m in ms) + " |")
        L += ["", "| Accuracy, set (bag) | " + " | ".join(blocks[m]["name"] for m in ms) + " |", "|---|" + "---|" * len(ms)]
        for p, pl in (("raw_", "raw (4 conditions)"), ("slx_", "smart-lex (3)"), ("cer_", "hybrid (4)"), ("str_", "strict (4)")):
            L.append(f"| {pl} | " + " | ".join(acc_range(blocks[m]["accuracy"], blocks[m]["bag_accuracy"], p) for m in ms) + " |")
        L += ["", "| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | " +
              " | ".join(blocks[m]["name"] for m in ms) + " |", "|---|" + "---|" * len(ms)]
        for p in ("cer-raw", "slx-raw", "cer-slx", "str-raw", "str-cer"):
            L.append(f"| {p} | " + " | ".join(
                f"{100 * blocks[m]['paired'][p]['mean_diff']:+.1f} pp [{100 * blocks[m]['paired'][p]['ci95'][0]:+.1f}, "
                f"{100 * blocks[m]['paired'][p]['ci95'][1]:+.1f}]" for m in ms) + " |")
        L.append("")
        for m in ms:
            b = blocks[m]
            L += [f"- {b['name']}: statements under hybrid/strict by verdict {json.dumps(b['verdicts'])}",
                  f"- {b['name']}: strict burden (strict_burden.py): {b['strict_burden']}",
                  f"- {b['name']}: same-SQL observation changes from CERTIFIED statements: {len(b['certified_changes'])}"]
            for c in b["certified_changes"]:
                L.append(f"  - {c['group']} {c['task_id']} {c['conds']} turn {c['turn']} {c['verdict']}: "
                         f"{' '.join(c['sql'].split())[:200]}")
        L.append("")
    for key, label, cert, dist, sd, sp in SETS:
        paths = {k: os.path.join(vdir, f) for k, f in (("cert", cert), ("dist", dist), ("duckdb", sd), ("postgres", sp))}
        L += [f"### {label} (`{cert}`)", ""]
        if not os.path.exists(paths["cert"]):
            L += ["(not available yet)", ""]
            continue
        recs = [json.loads(l) for l in open(paths["cert"])]
        keep = {(r["db_id"], r["sql"]) for r in recs if "exec_error" not in r}
        ent = {"n": len(keep)}
        if os.path.exists(paths["dist"]):
            dd = json.load(open(paths["dist"]))
            ent.update(verdicts=dd["overall"], width=dd["tie_break_width"], unsupported=dd["unsupported_reasons"],
                       ablation=dd["ablation_no_keys"]["overall"], ablation_width=dd["ablation_no_keys"]["tie_break_mean"])
            w = dd["tie_break_width"]
            L += [f"Verdicts ({dd['n_probes']}): " + ", ".join(f"{v} {dd['overall'][v]['n']} ({dd['overall'][v]['pct']}%)"
                                                              for v in ("DET", "NARROW", "ALL", "UNSUPPORTED")),
                  f"Repaired {w['n']}: mean appended sort columns {w['certified_mean']} vs smart-lex {w['smartlex_mean']}; "
                  f"key tie-breaks {w['key_tie_break']} (non-output key {w['non_output_key']})",
                  f"UNSUPPORTED reasons: {json.dumps(dd['unsupported_reasons'])}",
                  f"No-keys ablation: " + ", ".join(f"{v} {dd['ablation_no_keys']['overall'][v]['n']}"
                                                   for v in ("DET", "NARROW", "ALL", "UNSUPPORTED")) +
                  f"; mean width {dd['ablation_no_keys']['tie_break_mean']}", ""]
        for eng in ("duckdb", "postgres"):
            p = paths[eng]
            if not os.path.exists(p):
                L.append(f"{eng}: (not available yet)")
                continue
            sr = [json.loads(l) for l in open(p)]
            c = row(p, keep)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                table(p, keep, eng)
            div = [{"db_id": r["db_id"], "sql": r["sql"], "verdict": r["verdict"],
                    "rewrite": (r.get("policies", {}).get("certified", {}).get("sql"))}
                   for r in sr if (r["db_id"], r["sql"]) in keep and r.get("policies") and r["verdict"] in SUP
                   and r["policies"]["certified"]["diverged"]]
            ent[eng] = {"row": c, "certified_diverged": div, "table": buf.getvalue(),
                        "records_in_keep": sum((r["db_id"], r["sql"]) in keep for r in sr)}
            L += [f"{eng}: statements in file and keep set {ent[eng]['records_in_keep']} of {len(keep)}; row() = {json.dumps(c)}",
                  "```", buf.getvalue().rstrip(), "```"]
            for x in div:
                L.append(f"  - CERTIFIED DIVERGED ({eng}): {x['db_id']} {x['verdict']}: {' '.join(x['sql'].split())[:220]}")
        res["sets"][key] = ent
        L.append("")
    json.dump(res, open(out_path, "w"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
