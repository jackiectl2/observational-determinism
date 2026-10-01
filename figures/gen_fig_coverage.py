"""Figure 3: (top) certificate verdicts (final certifier v7) by probe class for the development probes, the held-out
statements and the statements from the second set of unseen tasks; (bottom) number of appended sort columns for the
repaired statements: certified tie-break vs smart-lex (every output column)."""
import json
import os
import sys
from collections import Counter

import numpy as np

from paper_plot_style import COL_WIDTH_IN, DATA, POLICY_COLORS, V7, VERDICT_COLORS, plt, save

sys.path.insert(0, os.path.join(DATA, "code"))  # the frozen code snapshot next to the results
from distribution import probe_class  # noqa: E402

VERDICTS = ["DET", "NARROW", "ALL", "UNSUPPORTED"]
VERDICT_HATCH = {"DET": None, "NARROW": "////", "ALL": "....", "UNSUPPORTED": "xxxx"}  # readable in grayscale
CLASSES = ["unordered SELECT", "ORDER BY + LIMIT", "LIMIT, no ORDER BY", "ORDER BY, no LIMIT", "DISTINCT", "GROUP BY"]
LABELS = {"unordered SELECT": "no ORDER/LIMIT", "ORDER BY + LIMIT": "ORDER BY + LIMIT",
          "LIMIT, no ORDER BY": "LIMIT only", "ORDER BY, no LIMIT": "ORDER BY only",
          "DISTINCT": "DISTINCT", "GROUP BY": "GROUP BY"}


SETS = [("dev", "cert_probes_v7.jsonl", None), ("held-out", "cert_heldout_kept_v7.jsonl", "//"),
        ("unseen", "cert_td2_new.jsonl", "..")]


def load():
    out = []
    for name, f, hatch in SETS:
        ps = [json.loads(line) for line in open(os.path.join(V7, f))]
        out.append((name, [p for p in ps if "exec_error" not in p], hatch))
    return out


def main():
    sets = load()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COL_WIDTH_IN, 3.4), gridspec_kw={"height_ratios": [2.5, 1]})
    # (a) stacked horizontal bars, three per class
    y, ylabels = [], []
    for ci, cls in enumerate(CLASSES):
        for si, (name, ps, _) in enumerate(sets):
            sub = [p for p in ps if probe_class(p["info"]) == cls]
            c = Counter(p["verdict"] for p in sub)
            left = 0.0
            pos = ci * 3.6 + si
            for v in VERDICTS:
                w = c[v] / len(sub) if sub else 0
                ax1.barh(pos, w, left=left, color=VERDICT_COLORS[v], height=0.85, edgecolor="white", linewidth=0.3,
                         hatch=VERDICT_HATCH[v], label=v if (ci == 0 and si == 0) else None)
                left += w
            ax1.text(1.01, pos, f"{name}  n={len(sub)}", va="center", fontsize=6.5)
            y.append(pos)
            ylabels.append(LABELS[cls] if si == 0 else "")
    ax1.set_yticks([ci * 3.6 + 1.0 for ci in range(len(CLASSES))])
    ax1.set_yticklabels([LABELS[c] for c in CLASSES])
    ax1.invert_yaxis()
    ax1.set_xlim(0, 1)
    ax1.set_xlabel("Share of probes in class")
    ax1.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, handlelength=1.0,
               columnspacing=0.8)
    # (b) appended sort columns for repaired probes
    bins = [1, 2, 3, 4, 5, 6]
    series = []
    for pol in ("certified", "smart-lex"):
        for name, ps, hatch in sets:
            rep = [p for p in ps if p["verdict"] in ("NARROW", "ALL")]
            vals = [min(len(p["tie_break"]) if pol == "certified" else p["n_out"], 6) for p in rep]
            color = POLICY_COLORS["certified" if pol == "certified" else "smartlex"]
            series.append((f"{pol}, {name} (n={len(rep)})", vals, color, hatch))
    width = 0.13
    for k, (label, vals, color, hatch) in enumerate(series):
        c = Counter(vals)
        share = [c[b] / len(vals) for b in bins]
        ax2.bar(np.array(bins) + (k - 2.5) * width, share, width=width, color=color, hatch=hatch,
                edgecolor="white" if hatch is None else "black", linewidth=0.3, label=label,
                alpha=1.0 if "dev" in label else 0.6)
    ax2.set_xticks(bins)
    ax2.set_xticklabels(["1", "2", "3", "4", "5", "$\\geq$6"])
    ax2.set_xlabel("Appended sort columns (repaired probes)")
    ax2.set_ylabel("Share")
    # one compact legend row: colour = policy, hatch = statement set (the six policy x set entries took three rows)
    from matplotlib.patches import Patch
    keys = [Patch(facecolor=POLICY_COLORS["certified"], label="certified"),
            Patch(facecolor=POLICY_COLORS["smartlex"], label="smart-lex")]
    keys += [Patch(facecolor="0.8", edgecolor="black", linewidth=0.3, hatch=hatch, label=name) for name, _, hatch in SETS]
    ax2.legend(handles=keys, ncol=5, frameon=False, fontsize=6.5, loc="lower center", bbox_to_anchor=(0.5, 1.0),
               columnspacing=0.8, handlelength=1.2, handletextpad=0.3)
    fig.tight_layout(h_pad=0.6)
    save(fig, "fig_coverage.pdf")
    for name, ps, _ in sets:
        rep = [p for p in ps if p["verdict"] in ("NARROW", "ALL")]
        print(name, len(ps), Counter(p["verdict"] for p in ps), "repaired", len(rep),
              "mean widths", round(sum(len(p["tie_break"]) for p in rep) / len(rep), 2),
              round(sum(p["n_out"] for p in rep) / len(rep), 2))


if __name__ == "__main__":
    main()
