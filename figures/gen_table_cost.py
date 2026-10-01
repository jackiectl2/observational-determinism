"""Table 3: observation cost at the largest scale per engine (final E3, experiments/obsdet/results/E3_analysis_v6.json).

Cost of one observation = preview (the policy's query, top-level LIMIT min(L, 20)) + the exact count (identical for
all policies); median of 5 repetitions per probe; one fixed probe set per engine. Change = certified vs smart-lex
total (probe-bootstrap 95% CI); ratio = smart-lex / certified; "top-5 left out" = the change after removing the five
probes that contribute most to the difference; LIMIT class = LIMIT/OFFSET without a total order (the predeclared
class). Predeclared bar: >= 20% lower total, or >= 5x on the LIMIT class.
"""
import json
import os

from paper_plot_style import DATA, OUT

E3 = os.environ.get("E3_ANALYSIS", os.path.join(DATA, "..", "E3_analysis_v6.json"))
ENGINES = [("DuckDB", "xmax", r"$\times$100 / $\times$30"), ("PostgreSQL", "x10", r"$\times$10")]


def pct(x):
    return f"${100 * x:+.1f}$\\%"


def main():
    d = json.load(open(E3))
    lines = [r"\begin{tabular}{@{}lrrrrrrr@{}}", r"\toprule",
             r"Engine (scale, $n$) & Raw & Smart-lex & Certified & Certified vs smart-lex [95\% CI] & "
             r"Median ratio & Top-5 left out & LIMIT class (ratio [CI], $n$) \\", r"\midrule"]
    for eng, sc, label in ENGINES:
        m = d[eng]["total"][sc]["main"]
        lo = d[eng]["total"]["leave_out"]
        l1 = d[eng]["total"]["limit_classes"]["L1"]
        t = m["total"]
        change = -m["reduction"]  # certified relative to smart-lex
        ci = sorted(-x for x in m["ci"])
        met = m["reduction"] >= 0.20 or l1["ratio"] >= 5
        lines.append(
            f"{eng} ({label}, {m['n']}) & {t['raw']:.1f}\\,s & {t['smartlex']:.1f}\\,s & {t['certified']:.1f}\\,s & "
            f"{pct(change)} [{pct(ci[0])}, {pct(ci[1])}] & {m['median_ratio']:.2f} & {pct(-lo['top5'])} & "
            f"{l1['ratio']:.2f} [{l1['ci'][0]:.2f}, {l1['ci'][1]:.2f}], {l1['n']} \\\\")
        print(eng, sc, m["n"], t, change, ci, m["median_ratio"], lo["top5"], l1["ratio"], l1["ci"], l1["n"], met)
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = os.path.join(OUT, "TABLE_cost.tex")
    open(path, "w").write("\n".join(lines) + "\n")
    print("saved", path)


if __name__ == "__main__":
    main()
