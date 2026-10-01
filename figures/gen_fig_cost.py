"""Figure: time of a smart-lex observation relative to a certified one (final E3, the data behind Table 4).

(a) histogram over the probes of one probe set per engine at its largest replicated scale (the n of Table 4):
per-probe smart-lex / certified database time, each the median of five repetitions (E3_analysis_v6_per_probe.csv);
(b) the controlled LIMIT 20 study: the same ratio for five tables and three query forms (E3_analysis_v6.json).
The plotted values are copied to fig_cost_data.json.
"""
import csv
import json
import os

import numpy as np
from matplotlib.lines import Line2D

from fig_qa import COL_W_IN, save_exact
from paper_plot_style import DATA, OUT, plt

E3 = os.path.join(DATA, "..", "E3_analysis_v6.json")
PER_PROBE = os.path.join(DATA, "..", "E3_analysis_v6_per_probe.csv")
ENGINES = [("DuckDB", "xmax", "DuckDB (largest scale)", dict(color="black", linestyle="-", marker="o", mfc="black")),
           ("PostgreSQL", "x10", "PostgreSQL ($\\times$10)", dict(color="0.45", linestyle="--", marker="D", mfc="white"))]
TABLES = ["cards", "comments", "posts", "users", "votes"]
FORMS = [("star", "SELECT *"), ("cols3", "3 columns"), ("cols3_where", "+ predicate")]
BIN = 1.25  # histogram bins: ratios within a factor 1.25, one bin centred on 1
H = 1.62
PANEL_A = [0.47, 0.54, 1.13, 0.76]
PANEL_B = [2.25, 0.54, 1.00, 0.76]


def axes_at(fig, box):
    return fig.add_axes([box[0] / COL_W_IN, box[1] / H, box[2] / COL_W_IN, box[3] / H])


def main():
    d = json.load(open(E3))
    rows = list(csv.DictReader(open(PER_PROBE)))
    data = {}
    for eng, sc, _, _ in ENGINES:
        sel = [r for r in rows if r["engine"] == eng and r["scale"] == sc and r["main_set"] == "1"]
        assert len(sel) == d[eng]["total"][sc]["main"]["n"], (eng, len(sel))  # the probe set of Table 4
        ratio = sorted(float(r["total_smartlex"]) / float(r["total_certified"]) for r in sel)
        ctrl = {f: [d[f"controlled_{eng}"][f"{t}.{f}.{sc}"]["smartlex"] / d[f"controlled_{eng}"][f"{t}.{f}.{sc}"]
                    ["certified"] for t in TABLES] for f, _ in FORMS}
        data[eng] = {"scale": sc, "n": len(ratio), "ratio_sorted": ratio, "distribution": d[eng]["total"]["distribution"],
                     "controlled": ctrl}
    fig = plt.figure(figsize=(COL_W_IN, H))
    ax1, ax2 = axes_at(fig, PANEL_A), axes_at(fig, PANEL_B)
    for ax in (ax1, ax2):
        ax.set_xscale("log")
        ax.axvline(1, color="0.6", linewidth=0.6, zorder=0)
    ax1.axvspan(1 / 1.1, 1.1, color="0.9", zorder=0, linewidth=0)
    bins = BIN ** np.arange(-round(np.log(100) / np.log(BIN)) - 0.5, round(np.log(100) / np.log(BIN)) + 1.5)
    for eng, _, label, st in ENGINES:
        counts, _ = np.histogram(data[eng]["ratio_sorted"], bins=bins)
        data[eng]["histogram"] = {"bin_edges": bins.tolist(), "counts": counts.tolist()}
        ax1.stairs(np.where(counts > 0, counts, 0.5), bins, color=st["color"], linestyle=st["linestyle"],
                   linewidth=1.0, baseline=0.5)
    ax1.set_yscale("log")
    ax1.set_xlim(0.01, 100)
    ax1.set_ylim(0.7, 2000)
    ax1.set_xticks([0.01, 0.1, 1, 10, 100], ["0.01", "0.1", "1", "10", "100"])
    ax1.set_yticks([1, 10, 100, 1000], ["1", "10", "100", "1000"])
    ax1.set_ylabel("Probes", fontsize=7.5, labelpad=2)
    ax1.set_xlabel("(a) Natural probes:\nsmart-lex / certified time", fontsize=7.5)

    offsets = {"DuckDB": -0.16, "PostgreSQL": 0.16}
    for eng, _, _, st in ENGINES:
        for i, (f, _) in enumerate(FORMS):
            v = data[eng]["controlled"][f]
            ax2.plot(v, [i + offsets[eng]] * len(v), linestyle="none", marker=st["marker"], markersize=3.2,
                     markerfacecolor=st["mfc"], markeredgecolor=st["color"], markeredgewidth=0.8)
    ax2.set_xlim(0.3, 3000)
    ax2.set_xticks([1, 10, 100, 1000], ["1", "10", "100", "1000"])
    ax2.set_ylim(len(FORMS) - 0.5, -0.5)
    ax2.set_yticks(range(len(FORMS)), [lab for _, lab in FORMS], fontsize=7)
    ax2.tick_params(axis="y", length=0)
    ax2.set_xlabel("(b) Controlled LIMIT 20,\nsame ratio", fontsize=7.5)
    for ax in (ax1, ax2):
        ax.xaxis.set_label_coords(0.5, -0.235 / PANEL_A[3])  # 0.235 in below the axes
        ax.xaxis.label.set_va("top")
    handles = [Line2D([], [], color=st["color"], linestyle=st["linestyle"], linewidth=1.0, marker=st["marker"],
                      markersize=3.2, markerfacecolor=st["mfc"], markeredgewidth=0.8, label=label)
               for _, _, label, st in ENGINES]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False,
               handlelength=2.2, columnspacing=1.2, handletextpad=0.5, fontsize=7)
    json.dump(data, open(os.path.join(OUT, "fig_cost_data.json"), "w"), indent=1)
    save_exact(fig, "fig_cost", fit=False)
    for eng, _, _, _ in ENGINES:
        r = np.array(data[eng]["ratio_sorted"])
        print(eng, data[eng]["n"], "min/median/max", round(r.min(), 3), round(float(np.median(r)), 4), round(r.max(), 2),
              {f: [round(x, 2) for x in v] for f, v in data[eng]["controlled"].items()})


if __name__ == "__main__":
    main()
