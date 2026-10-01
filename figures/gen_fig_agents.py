"""Figure: agent behavior under each policy on the main tasks and both sets of unseen tasks (E4 v7, final certifier).

(a) tasks (of 150) whose trajectory / answer correctness changed across the three physical orders (1 thread);
(b) paired accuracy difference to raw with the task-clustered bootstrap 95% CI. Values are read from summary_e4.json
unchanged (the same fields as Tables 1 and 3) and copied to fig_agents_data.json.
"""
import json
import os

from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from fig_qa import COL_W_IN, save_exact
from paper_plot_style import OUT, POLICY_COLORS, V7, plt

MODELS = [("qwen3_8b", "Qwen3-8B"), ("phi4", "phi-4")]
SETS = [("e4_v7", "Main"), ("e4_v7td", "Unseen I"), ("e4_v7td2", "Unseen II")]
POLICIES = [("raw_phys", None, "Raw"), ("slx_phys", "slx-raw", "Smart-\nlex"), ("cer_phys", "cer-raw", "Hybrid"),
            ("str_phys", "str-raw", "Strict")]
PAIR_STYLE = {"slx-raw": (POLICY_COLORS["smartlex"], "s", "Smart-lex"),
              "cer-raw": (POLICY_COLORS["certified"], "o", "Hybrid"), "str-raw": ("#CC79A7", "^", "Strict")}
GAP = 0.45  # extra space between the two model groups, in rows
# hand layout, inches: [left, bottom, width, height]
H = 2.00
HEAT = [0.72, 0.52, 1.40, 1.06]
FOREST = [2.30, 0.52, 0.99, 1.06]


def load():
    rows = []
    for m, mlabel in MODELS:
        for tag, slabel in SETS:
            s = json.load(open(os.path.join(V7, f"{tag}_{m}", "summary_e4.json")))["all"]
            rows.append({"model": mlabel, "set": slabel,
                         "traj": [s["stability"][g]["traj_changed"]["count"] for g, _, _ in POLICIES],
                         "corr": [s["stability"][g]["correctness_changed"]["count"] for g, _, _ in POLICIES],
                         "dacc": {p: [s["paired_accuracy"][p]["mean_diff"]] + list(s["paired_accuracy"][p]["ci95"])
                                  for _, p, _ in POLICIES if p}})
    return rows


def axes_at(fig, box):
    return fig.add_axes([box[0] / COL_W_IN, box[1] / H, box[2] / COL_W_IN, box[3] / H])


def main():
    rows = load()
    json.dump(rows, open(os.path.join(OUT, "fig_agents_data.json"), "w"), indent=1)
    ys = [i + (GAP if i >= 3 else 0) for i in range(len(rows))]
    fig = plt.figure(figsize=(COL_W_IN, H))
    ax1, ax2 = axes_at(fig, HEAT), axes_at(fig, FOREST)

    norm = LogNorm(vmin=1, vmax=max(max(r["traj"]) for r in rows))
    cmap = plt.get_cmap("Greys")
    for y, r in zip(ys, rows):
        for x, (t, c) in enumerate(zip(r["traj"], r["corr"])):
            shade = cmap(0.08 + 0.8 * norm(t)) if t > 0 else "white"
            ax1.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=shade, edgecolor="white", linewidth=1.2))
            ax1.text(x, y, f"{t}/{c}", ha="center", va="center", fontsize=7, gid="data",
                     color="white" if t > 0 and norm(t) > 0.55 else "black")
    ax1.set_xlim(-0.5, len(POLICIES) - 0.5)
    ax1.set_ylim(ys[-1] + 0.5, -0.5)
    ax1.set_xticks(range(len(POLICIES)), [p[2] for p in POLICIES], fontsize=7, va="bottom")
    ax1.xaxis.tick_top()
    ax1.tick_params(length=0, pad=2)
    ax1.set_yticks(ys, [r["set"] for r in rows], fontsize=7)
    for side in ("left", "bottom", "top", "right"):
        ax1.spines[side].set_visible(False)
    for g, (_, mlabel) in enumerate(MODELS):
        ax1.text(-0.12 / COL_W_IN - 0.60 / HEAT[2], 1 + g * (3 + GAP), mlabel, transform=ax1.get_yaxis_transform(),
                 rotation=90, ha="center", va="center", fontsize=7.5, fontweight="bold")
    ax1.set_xlabel("(a) Changed tasks\n(trajectory/correctness)", fontsize=7.5)

    offsets = {"slx-raw": -0.25, "cer-raw": 0.0, "str-raw": 0.25}
    for y, r in zip(ys, rows):
        for p, (mean, lo, hi) in r["dacc"].items():
            color, marker, _ = PAIR_STYLE[p]
            yy = y + offsets[p]
            ax2.plot([100 * lo, 100 * hi], [yy, yy], color=color, linewidth=1.0, solid_capstyle="butt")
            ax2.plot(100 * mean, yy, marker=marker, color=color, markersize=3.4, linestyle="none")
    ax2.axvline(0, color="0.4", linewidth=0.6, linestyle="--", zorder=0)
    ax2.set_ylim(ys[-1] + 0.5, -0.5)
    ax2.set_xlim(-10.5, 7.5)
    ax2.set_xticks([-8, -4, 0, 4], ["$-8$", "$-4$", "0", "$+4$"])
    ax2.set_yticks([])
    ax2.spines["left"].set_visible(False)
    ax2.set_xlabel("(b) $\\Delta$Acc vs raw\n(points, 95% CI)", fontsize=7.5)
    handles = [Line2D([], [], color=c, marker=mk, markersize=3.4, linewidth=1.0, label=lab)
               for c, mk, lab in PAIR_STYLE.values()]
    ax2.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=1, frameon=False,
               handlelength=1.3, handletextpad=0.4, labelspacing=0.15, fontsize=7, borderaxespad=0.1)
    for ax in (ax1, ax2):  # same height and axes coordinates, so both labels sit on one line
        ax.xaxis.set_label_coords(0.5, -0.205 / HEAT[3])  # 0.205 in below the axes
        ax.xaxis.label.set_va("top")
    save_exact(fig, "fig_agents", fit=False)
    for r in rows:
        print(r["model"], r["set"], r["traj"], r["corr"], {k: [round(100 * v, 1) for v in vals]
                                                           for k, vals in r["dacc"].items()})


if __name__ == "__main__":
    main()
