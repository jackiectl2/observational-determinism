"""Figure: where previews diverge, pooled over the four statement sets of Table 2 (final certifier v7).

(a) supported statements (certificate DET/NARROW/ALL in the engine's dialect, observed in every configuration): share
whose raw preview diverged, by statement class (the classes of the coverage figure), and whose certified preview
diverged (zero in every class); (b) rejected (UNSUPPORTED) statements: share whose smart-lex preview diverged, by
reason code. Inclusion rules are those of Table 2 (gen_table_soundness.row), which the totals are checked against.
The plotted counts are copied to fig_divergence_data.json.
"""
import collections
import json
import os
import sys

from matplotlib.lines import Line2D

from fig_qa import COL_W_IN, save_exact
from gen_table_soundness import row as table2_row
from paper_plot_style import DATA, OUT, POLICY_COLORS, V7, plt

sys.path.insert(0, os.path.join(DATA, "code"))  # the frozen code snapshot next to the results
from distribution import probe_class  # noqa: E402

SUP = ("DET", "NARROW", "ALL")
SETS = [("cert_probes_v7.jsonl", "sound_v7.jsonl", "sound_pg_v7.jsonl", False),
        ("cert_heldout_kept_v7.jsonl", "sound_heldout_v7.jsonl", "sound_pg_heldout_v7.jsonl", True),
        ("cert_td_new_v7.jsonl", "sound_td_v7.jsonl", "sound_pg_td_v7.jsonl", True),
        ("cert_td2_new.jsonl", "sound_td2.jsonl", "sound_pg_td2.jsonl", True)]
CLASSES = [("unordered SELECT", "no ORDER/LIMIT"), ("ORDER BY + LIMIT", "ORDER BY + LIMIT"),
           ("LIMIT, no ORDER BY", "LIMIT only"), ("ORDER BY, no LIMIT", "ORDER BY only"), ("DISTINCT", "DISTINCT"),
           ("GROUP BY", "GROUP BY")]
REASONS = [("derived-table", "derived table"), ("no-base-table", "no base table"), ("float-aggregate", "float SUM/AVG"),
           ("cte", "CTE"), ("outer-or-special-join", "outer/special join"), ("other", "other")]  # by frequency
ENGINES = [("DuckDB", 1, dict(color="black", marker="o", mfc="black")),
           ("PostgreSQL", 2, dict(color="0.45", marker="D", mfc="white"))]
H = 1.64
PANEL_A = [0.86, 0.50, 0.74, 0.84]
PANEL_B = [2.52, 0.50, 0.74, 0.84]


def load(name):
    return [json.loads(line) for line in open(os.path.join(V7, name))]


def analyze():
    sup = {e: collections.defaultdict(lambda: [0, 0, 0]) for e, _, _ in ENGINES}  # n, raw diverged, cert diverged
    uns = {e: collections.defaultdict(lambda: [0, 0]) for e, _, _ in ENGINES}  # n, smart-lex diverged
    for cert, *sound, dedup in SETS:
        certs = {(r["db_id"], r["sql"]): r for r in load(cert)}
        for (eng, idx, _), f in zip(ENGINES, sound):
            t2 = table2_row(os.path.join(V7, f), set(certs) if dedup else None)
            n_sup = n_raw = n_cer = n_uns = n_slx = 0
            for r in load(f):
                k = (r["db_id"], r["sql"])
                pols = r.get("policies")
                if (dedup and k not in certs) or not pols:
                    continue
                if r["verdict"] in SUP:
                    if pols["certified"]["diverged"] is None:
                        continue
                    c = sup[eng][probe_class(certs[k]["info"])]
                    c[0] += 1
                    c[1] += bool(pols["raw"]["diverged"])
                    c[2] += bool(pols["certified"]["diverged"])
                    n_sup, n_raw, n_cer = n_sup + 1, n_raw + bool(pols["raw"]["diverged"]), n_cer + bool(
                        pols["certified"]["diverged"])
                elif pols["raw"]["diverged"] is not None and pols["smartlex"]["diverged"] is not None:
                    rc = (r.get("reason") or certs[k].get("reason") or "?").split(":")[0]
                    rc = rc if rc in dict(REASONS) else "other"
                    uns[eng][rc][0] += 1
                    uns[eng][rc][1] += bool(pols["smartlex"]["diverged"])
                    n_uns, n_slx = n_uns + 1, n_slx + bool(pols["smartlex"]["diverged"])
            # the same statements and outcomes as the Table 2 row of this set and engine
            assert (n_sup, n_raw, n_cer, n_uns, n_slx) == (t2["sup"], t2["raw"], t2["cer"], t2["uns"], t2["uns_slx"]), \
                (f, (n_sup, n_raw, n_cer, n_uns, n_slx), t2)
    return {"supported_by_class": {e: {c: sup[e][c] for c, _ in CLASSES} for e in sup},
            "unsupported_by_reason": {e: {r: uns[e][r] for r, _ in REASONS} for e in uns}}


def axes_at(fig, box):
    return fig.add_axes([box[0] / COL_W_IN, box[1] / H, box[2] / COL_W_IN, box[3] / H])


def main():
    data = analyze()
    json.dump(data, open(os.path.join(OUT, "fig_divergence_data.json"), "w"), indent=1)
    fig = plt.figure(figsize=(COL_W_IN, H))
    ax1, ax2 = axes_at(fig, PANEL_A), axes_at(fig, PANEL_B)
    off = {"DuckDB": -0.14, "PostgreSQL": 0.14}
    for eng, _, st in ENGINES:
        for i, (c, _) in enumerate(CLASSES):
            n, raw, cer = data["supported_by_class"][eng][c]
            ax1.plot(100 * raw / n, i + off[eng], linestyle="none", marker=st["marker"], markersize=3.4,
                     markerfacecolor=st["mfc"], markeredgecolor=st["color"], markeredgewidth=0.8)

        for i, (r, _) in enumerate(REASONS):
            n, slx = data["unsupported_by_reason"][eng][r]
            ax2.plot(100 * slx / n, i + off[eng], linestyle="none", marker=st["marker"], markersize=3.4,
                     markerfacecolor=st["mfc"], markeredgecolor=st["color"], markeredgewidth=0.8)
    for i, (c, _) in enumerate(CLASSES):  # certified: one marker per class, since it is the same on both engines
        cer = {eng: data["supported_by_class"][eng][c] for eng, _, _ in ENGINES}
        assert len({v[2] / v[0] for v in cer.values()}) == 1, cer
        ax1.plot(100 * cer["DuckDB"][2] / cer["DuckDB"][0], i, linestyle="none", marker="s", markersize=3.0,
                 markerfacecolor="none", markeredgecolor=POLICY_COLORS["certified"], markeredgewidth=0.9)
    for ax, labels in ((ax1, CLASSES), (ax2, REASONS)):
        ax.set_xlim(-9, 100)
        ax.set_xticks([0, 25, 50, 75, 100], ["0", "", "50", "", "100"])
        ax.set_ylim(len(labels) - 0.5, -0.5)
        ax.set_yticks(range(len(labels)), [lab for _, lab in labels], fontsize=7)
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="0.9", linewidth=0.5, zorder=0)
        ax.set_axisbelow(True)
        ax.xaxis.set_label_coords(0.5, -0.232 / PANEL_A[3])  # 0.232 in below the axes
        ax.xaxis.label.set_va("top")
    ax1.set_xlabel("(a) Supported, raw\nand certified (%)", fontsize=7.5)
    ax2.set_xlabel("(b) Rejected,\nsmart-lex (%)", fontsize=7.5)
    handles = [Line2D([], [], linestyle="none", marker=st["marker"], markersize=3.4, markerfacecolor=st["mfc"],
                      markeredgecolor=st["color"], markeredgewidth=0.8, label=eng)
               for eng, _, st in ENGINES]
    handles.append(Line2D([], [], linestyle="none", marker="s", markersize=3.0, markerfacecolor="none",
                          markeredgecolor=POLICY_COLORS["certified"], markeredgewidth=0.8, label="Certified"))
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False,
               handletextpad=0.2, columnspacing=0.9, fontsize=7)
    save_exact(fig, "fig_divergence", fit=False)
    for key, part in data.items():
        for eng, d in part.items():
            print(key, eng, {k: v for k, v in d.items()})


if __name__ == "__main__":
    main()
