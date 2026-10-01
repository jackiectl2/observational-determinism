"""Task-disjoint replication: summary of the agent-level (E4) and held-out statement (E1-H) results.

Reads, from <td_dir>: e4_v6td_qwen3_8b/summary_e4.json and e4_v6td_phi4/summary_e4.json (analyze3.py),
td_funnel.json (td_filter.py), distribution_td.json (distribution.py), sound_td.jsonl (replay_sound.py) and
sound_pg_td.jsonl (replay_pg.py); for comparison, results/final/e4_v5_*/summary_e4.json (original tasks).
Soundness counts use row() of figures/gen_table_soundness.py unchanged (imported with a stub for its plotting-style
module), and the per-verdict tables use heldout_dedup.table unchanged.

Usage: python td_analyze.py <td_dir> <out.json>
"""
import contextlib
import io
import json
import os
import sys
import types
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = os.path.join(HERE, "results", "final")
sys.modules["paper_plot_style"] = types.SimpleNamespace(DATA=FINAL, OUT=None)
sys.path.insert(0, os.path.join(HERE, "..", "..", "figures"))
from gen_table_soundness import row, SUP  # noqa: E402  (also puts results/final/code on sys.path)
from heldout_dedup import table  # noqa: E402

GROUPS = [("raw_phys", "raw, 3 physical orders"), ("slx_phys", "smart-lex, 3 physical orders"),
          ("cer_phys", "hybrid (certified), 3 physical orders"), ("str_phys", "strict (fail-closed), 3 physical orders"),
          ("raw_threads", "raw, 1 vs 8 threads"), ("cer_threads", "hybrid, 1 vs 8 threads"),
          ("str_threads", "strict, 1 vs 8 threads")]
FLAGS = ["traj_changed", "final_sql_changed", "final_result_changed", "correctness_changed"]
MODELS = [("qwen3_8b", "Qwen3-8B"), ("phi4", "phi-4")]


def e4_rows(summ):
    a = summ["all"]
    out = {}
    for g, _ in GROUPS:
        s = a["stability"][g]
        out[g] = {"counts": [s[f]["count"] for f in FLAGS], "n": [s[f]["n"] for f in FLAGS],
                  "censored": [s[f]["censored"] for f in FLAGS],
                  "unattributed": s["unattributed_divergence"]["count"],
                  "obs_diverged_same_sql": s["obs_diverged_same_sql"]["count"],
                  "sources": a.get("divergent_statement_sources", {}).get(g, {})}
    return out


def fmt_counts(r):
    c = [str(x) for x in r["counts"]]
    if r["censored"][2]:
        c[2] += f" (cens. {r['censored'][2]})"
    return " / ".join(c)


def main(td_dir, out_path):
    res = {"e4": {}, "e4_v5_original": {}}
    lines = ["## Agent level (E4 design, task-disjoint tasks)", "",
             "| Group | " + " | ".join(f"{m} traj / final SQL / result / correctness" for _, m in MODELS) + " |",
             "|---|" + "---|" * len(MODELS)]
    summ = {k: json.load(open(os.path.join(td_dir, f"e4_v6td_{k}", "summary_e4.json"))) for k, _ in MODELS}
    v5 = {k: json.load(open(os.path.join(FINAL, f"e4_v5_{k}", "summary_e4.json"))) for k, _ in MODELS}
    rows = {k: e4_rows(s) for k, s in summ.items()}
    rows5 = {k: e4_rows(s) for k, s in v5.items()}
    for g, label in GROUPS:
        lines.append(f"| {label} | " + " | ".join(fmt_counts(rows[k][g]) for k, _ in MODELS) + " |")
    lines += ["", "Same groups on the original tasks (E4 v5, for comparison):", "",
              "| Group | " + " | ".join(f"{m} (v5)" for _, m in MODELS) + " |", "|---|" + "---|" * len(MODELS)]
    for g, label in GROUPS:
        lines.append(f"| {label} | " + " | ".join(fmt_counts(rows5[k][g]) for k, _ in MODELS) + " |")
    lines += ["", "Attribution (task-disjoint): unattributed divergence and same-SQL observation-change sources", ""]
    for k, m in MODELS:
        for g, label in GROUPS:
            r = rows[k][g]
            lines.append(f"- {m}, {label}: unattributed {r['unattributed']}/{r['n'][0]}; tasks with a same-SQL "
                         f"observation change {r['obs_diverged_same_sql']}; sources {r['sources']}")
    lines += ["", "Accuracy (set; bag) per condition, task-disjoint:", ""]
    for k, m in MODELS:
        a = summ[k]["all"]
        lines.append(f"- {m}: " + "; ".join(f"{c} {v['mean']:.3f} {v['ci95']} ({a['bag_accuracy'][c]:.3f})"
                                          for c, v in sorted(a["accuracy"].items())))
    lines += ["", "Paired accuracy differences over the three physical orders (task-clustered bootstrap 95% CI):", ""]
    for k, m in MODELS:
        pa = summ[k]["all"]["paired_accuracy"]
        lines.append(f"- {m}: " + "; ".join(f"{p} {100 * v['mean_diff']:+.1f} pp [{100 * v['ci95'][0]:+.1f}, "
                                          f"{100 * v['ci95'][1]:+.1f}]" for p, v in pa.items()))
    lines += ["", "Statements executed under the hybrid (cer) and strict (str) policies, by verdict:", ""]
    for k, m in MODELS:
        lines.append(f"- {m}: {summ[k]['certified_statement_verdicts']}")
    for k, _ in MODELS:
        res["e4"][k] = {"groups": rows[k], "accuracy": summ[k]["all"]["accuracy"],
                        "bag_accuracy": summ[k]["all"]["bag_accuracy"],
                        "paired_accuracy": summ[k]["all"]["paired_accuracy"],
                        "certified_statement_verdicts": summ[k]["certified_statement_verdicts"],
                        "n_tasks": summ[k]["all"]["n_tasks"]}
        res["e4_v5_original"][k] = {"groups": rows5[k]}

    # held-out statements
    funnel = json.load(open(os.path.join(td_dir, "td_funnel.json")))
    dist = json.load(open(os.path.join(td_dir, "distribution_td.json")))
    keep = {(json.loads(l)["db_id"], json.loads(l)["sql"]) for l in open(os.path.join(td_dir, "cert_td_new.jsonl"))}
    res["heldout"] = {"funnel": funnel, "verdicts": dist["overall"], "tie_break_width": dist["tie_break_width"],
                      "unsupported_reasons": dist["unsupported_reasons"], "by_class": dist["by_class"],
                      "e4_by_model": dist["e4_by_model"], "n_kept": len(keep)}
    lines += ["", "## Held-out statements (task-disjoint)", "", f"Funnel: {json.dumps(funnel['removed_in_order'])}; "
              f"distinct {funnel['distinct_statements']} -> kept {funnel['kept']}", "",
              "Verdicts: " + ", ".join(f"{v} {dist['overall'][v]['n']} ({dist['overall'][v]['pct']}%)"
                                       for v in ("DET", "NARROW", "ALL", "UNSUPPORTED")),
              f"Repaired (NARROW/ALL) {dist['tie_break_width']['n']}: mean appended sort columns "
              f"{dist['tie_break_width']['certified_mean']} vs smart-lex {dist['tie_break_width']['smartlex_mean']}",
              f"UNSUPPORTED reasons: {dist['unsupported_reasons']}", ""]
    for eng, fn in (("duckdb", "sound_td.jsonl"), ("postgres", "sound_pg_td.jsonl")):
        path = os.path.join(td_dir, fn)
        recs = [json.loads(l) for l in open(path)]
        c = row(path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            table(path, keep, eng)
        cert_div = [{"db_id": r["db_id"], "sql": r["sql"], "verdict": r["verdict"]} for r in recs
                    if r.get("policies") and r["verdict"] in SUP and r["policies"]["certified"]["diverged"]]
        cens = [r for r in recs if not r.get("policies") or any(p["diverged"] is None for p in r["policies"].values())]
        errs = Counter()
        for r in cens:
            if "transpile_error" in r:
                errs["transpile: " + r["transpile_error"][:60]] += 1
            for p in r.get("policies", {}).values():
                for e in p.get("errors", [])[:1]:
                    errs[e[:70]] += 1
        res[eng] = {"records": len(recs), "records_in_keep": sum((r["db_id"], r["sql"]) in keep for r in recs),
                    "row": c, "verdicts": dict(Counter(r["verdict"] for r in recs)), "certified_diverged": cert_div,
                    "censored_statements": len(cens), "censoring_errors": dict(errs.most_common(12)),
                    "table": buf.getvalue()}
        lines += [f"{eng}: records {len(recs)} (in keep {res[eng]['records_in_keep']}); row() = {c}",
                  f"verdicts in this file: {res[eng]['verdicts']}; certified diverged: {len(cert_div)}; "
                  f"censored statements: {len(cens)}", buf.getvalue()]
    json.dump(res, open(out_path, "w"), indent=1)
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
