"""Table 1: agent stability and accuracy per policy (E4 v7 = final certifier, original 150 BIRD tasks, both models).

Stability = tasks (of 150) whose trajectory / correctness differs across the compared executions: the three
physical orders (1 thread) or 1 vs 8 threads (original order). Accuracy = mean BIRD execution accuracy over the three
physical orders; Delta = paired difference to raw over the same tasks and orders (task-clustered bootstrap 95% CI).
"""
import json
import os

from paper_plot_style import OUT, V7, signed_pp

MODELS = [("qwen3_8b", "Qwen3-8B"), ("phi4", "phi-4")]
ROWS = [("Physical order", "Raw", "raw_phys", "raw", None), ("", "Smart-lex", "slx_phys", "slx", "slx-raw"),
        ("", "Hybrid", "cer_phys", "cer", "cer-raw"), ("", "Strict", "str_phys", "str", "str-raw"),
        ("1 vs 8 threads", "Raw", "raw_threads", None, None), ("", "Hybrid", "cer_threads", None, None),
        ("", "Strict", "str_threads", None, None)]
ORDERS = ["orig_t1", "p42_t1", "p7_t1"]
# The 1-vs-8-thread rows are left out of the table for space; their counts are printed and quoted in Section 5.2/5.5.
THREADS_IN_TABLE = False


def pct(x):
    return f"{100 * x:.1f}"


def main():
    S = {m: json.load(open(os.path.join(V7, f"e4_v7_{m}", "summary_e4.json")))["all"] for m, _ in MODELS}
    lines = [r"\begin{tabular}{@{}ll rrrr rrrr@{}}", r"\toprule",
             r" & & \multicolumn{4}{c}{Qwen3-8B} & \multicolumn{4}{c}{phi-4} \\",
             r"\cmidrule(lr){3-6}\cmidrule(l){7-10}",
             r"Executions & Policy & Traj. & Corr. & Acc. & $\Delta$Acc [95\% CI] & Traj. & Corr. & Acc. & $\Delta$Acc [95\% CI] \\",
             r"\midrule"]
    for i, (grp, name, g, pol, pair) in enumerate(ROWS):
        if "threads" in g and not THREADS_IN_TABLE:
            print("text only:", name, g, [(S[m]["stability"][g]["traj_changed"]["count"],
                                            S[m]["stability"][g]["correctness_changed"]["count"]) for m, _ in MODELS])
            continue
        if i == 4:
            lines.append(r"\midrule")
        cells = [grp, name]
        for m, _ in MODELS:
            st = S[m]["stability"][g]
            cells += [str(st["traj_changed"]["count"]), str(st["correctness_changed"]["count"])]
            if pol:
                acc = sum(S[m]["accuracy"][f"{pol}_{o}"]["mean"] for o in ORDERS) / len(ORDERS)
                cells.append(pct(acc))
                if pair:
                    p = S[m]["paired_accuracy"][pair]
                    lo, hi = p["ci95"]
                    cells.append(f"{signed_pp(p['mean_diff'])} [{signed_pp(lo)}, {signed_pp(hi)}]")
                else:
                    cells.append("--")
            else:
                cells += ["", ""]
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = os.path.join(OUT, "TABLE_agents.tex")
    open(path, "w").write("\n".join(lines) + "\n")
    print("saved", path)


if __name__ == "__main__":
    main()
