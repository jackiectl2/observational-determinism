"""Table 3: agent results on two sets of 150 unseen BIRD tasks (E4 v7 = final certifier; tasks_v3 and tasks_v4, each
disjoint from the original tasks and from each other). Stability = tasks whose trajectory / correctness changed across
the three physical orders (1 thread); Delta = paired accuracy difference to raw (task-clustered bootstrap 95% CI).
"""
import json
import os

from paper_plot_style import OUT, V7, signed_pp

MODELS = [("qwen3_8b", "Qwen3-8B"), ("phi4", "phi-4")]
SETS = [("Unseen tasks I", "e4_v7td"), ("Unseen tasks II", "e4_v7td2")]
ROWS = [("Raw", "raw_phys", None), ("Smart-lex", "slx_phys", "slx-raw"), ("Hybrid", "cer_phys", "cer-raw"),
        ("Strict", "str_phys", "str-raw")]


def main():
    lines = [r"\begin{tabular}{@{}ll rrr rrr@{}}", r"\toprule",
             r" & & \multicolumn{3}{c}{Qwen3-8B} & \multicolumn{3}{c}{phi-4} \\",
             r"\cmidrule(lr){3-5}\cmidrule(l){6-8}",
             r"Tasks & Policy & Traj. & Corr. & $\Delta$Acc [95\% CI] & Traj. & Corr. & $\Delta$Acc [95\% CI] \\",
             r"\midrule"]
    for si, (label, tag) in enumerate(SETS):
        if si:
            lines.append(r"\midrule")
        S = {m: json.load(open(os.path.join(V7, f"{tag}_{m}", "summary_e4.json")))["all"] for m, _ in MODELS}
        for ri, (name, g, pair) in enumerate(ROWS):
            cells = [label if ri == 0 else "", name]
            for m, _ in MODELS:
                st = S[m]["stability"][g]
                cells += [str(st["traj_changed"]["count"]), str(st["correctness_changed"]["count"])]
                if pair:
                    p = S[m]["paired_accuracy"][pair]
                    lo, hi = p["ci95"]
                    cells.append(f"{signed_pp(p['mean_diff'])} [{signed_pp(lo)}, {signed_pp(hi)}]")
                else:
                    cells.append("--")
            lines.append(" & ".join(cells) + r" \\")
            print(label, name, cells[2:])
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = os.path.join(OUT, "TABLE_replication.tex")
    open(path, "w").write("\n".join(lines) + "\n")
    print("saved", path)


if __name__ == "__main__":
    main()
