"""Exact-width layout and a QA gate for the data figures added in the final revision.

The gate (font size, label overlap, clipping, near-miss panel alignment, annotation budget) is adapted from
the author's own figure-style template. Unlike paper_plot_style.save, which crops the canvas
(savefig.bbox "tight"), save_exact keeps the canvas at the column width, so \\includegraphics[width=\\columnwidth]
prints every font at its nominal size.
"""
import os

import numpy as np

from paper_plot_style import OUT, plt

COL_W_IN = 241.14749 / 72.27  # \columnwidth of the acmart sigconf layout, measured
MIN_PT = 6.5
MAX_ANNOT = 120
PNG_OUT = os.environ.get("FIG_PNG_OUT", OUT)


def _boxes(fig):
    """Rendered boxes of the text that lands on paper: titles, axis labels, in-range tick labels, legends, texts."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    texts, in_legend = list(fig.texts), set()
    for leg in fig.legends:
        texts += leg.get_texts()
        in_legend.update(leg.get_texts())
    for ax in fig.get_axes():
        texts += [ax.title, ax.xaxis.label, ax.yaxis.label]
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for t in axis.get_major_ticks():
                if lo - 1e-9 <= t.get_loc() <= hi + 1e-9:
                    texts += [t.label1, t.label2]  # label2: ticks drawn on the top or right side
        texts += list(ax.texts)
        leg = ax.get_legend()
        if leg is not None:
            texts += leg.get_texts()
            in_legend.update(leg.get_texts())
    out = []
    for t in texts:
        if t is None or not t.get_visible() or not t.get_text().strip() or t.get_alpha() == 0:
            continue
        bb = t.get_window_extent(renderer=r)
        if bb.width > 0 and bb.height > 0:
            out.append((t, bb, t in in_legend))
    return out


def check_figure(fig, name):
    viol, boxes = [], _boxes(fig)
    for t, _, _ in boxes:
        if t.get_fontsize() < MIN_PT:
            viol.append(f"{name}: '{t.get_text()[:28]}' prints at {t.get_fontsize():.1f}pt (min {MIN_PT})")
    for i in range(len(boxes)):
        ti, bi, li = boxes[i]
        for tj, bj, lj in boxes[i + 1:]:
            if li and lj:
                continue
            ow, oh = min(bi.x1, bj.x1) - max(bi.x0, bj.x0), min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
            if ow > 1 and oh > 1 and ow * oh / max(min(bi.width * bi.height, bj.width * bj.height), 1) > 0.12:
                viol.append(f"{name}: OVERLAP '{ti.get_text()[:20]}' x '{tj.get_text()[:20]}'")
    fw, fh = fig.get_size_inches() * fig.dpi
    for t, bb, _ in boxes:
        if bb.x0 < -0.5 or bb.y0 < -0.5 or bb.x1 > fw + 0.5 or bb.y1 > fh + 0.5:
            viol.append(f"{name}: CLIPPED '{t.get_text()[:24]}'")
    axes = [ax for ax in fig.get_axes() if ax.get_visible()]
    for idx, side in enumerate(("left", "bottom", "right", "top")):
        vals = sorted({ax.get_position().extents[idx] for ax in axes})
        viol += [f"{name}: MISALIGNED {side} edges {a:.3f} vs {b:.3f}" for a, b in zip(vals, vals[1:])
                 if 0.002 < b - a < 0.02]
    annot = sum(len(t.get_text()) for ax in fig.get_axes() for t in ax.texts if t.get_gid() != "data")
    annot += sum(len(t.get_text()) for t in fig.texts if t.get_gid() != "data")
    if annot > MAX_ANNOT:
        viol.append(f"{name}: {annot} chars of annotation (max {MAX_ANNOT})")
    return viol


def save_exact(fig, name, width_in=COL_W_IN, rounds=4, fit=True, **layout):
    """Lay out at exactly width_in (height grows until nothing clips), run the gate, write PDF (for LaTeX) and PNG.

    fit=False keeps hand-placed axes: the figure must already be width_in wide; nothing is re-laid out.
    """
    if not fit:
        assert abs(fig.get_size_inches()[0] - width_in) < 1e-6, "hand-placed figure must be created at width_in"
    else:
        w, h = fig.get_size_inches()
        fig.set_size_inches(width_in, h)
        for _ in range(rounds):
            fig.tight_layout(**layout)
            fig.canvas.draw()
            bb = fig.get_tightbbox(fig.canvas.get_renderer())
            over = max(0.0, -bb.y0) + max(0.0, bb.y1 - fig.get_size_inches()[1])
            if over < 0.01:
                break
            fig.set_size_inches(width_in, fig.get_size_inches()[1] + over + 0.05)
        fig.tight_layout(**layout)
    viol = check_figure(fig, name)
    pdf = os.path.join(OUT, f"{name}.pdf")
    # the full canvas: bbox_inches=None would fall back to paper_plot_style's savefig.bbox "tight" and crop it
    fig.savefig(pdf, bbox_inches=fig.bbox_inches)
    fig.savefig(os.path.join(PNG_OUT, f"{name}.png"), dpi=400, bbox_inches=fig.bbox_inches)
    plt.close(fig)
    size = np.round(fig.get_size_inches(), 3)
    print(f"{'PASS' if not viol else 'FAIL'} {name} {size[0]}x{size[1]} in")
    for v in viol:
        print("   ", v)
    with open(os.path.join(OUT, f"QA_{name}.txt"), "w") as fh:
        fh.write(f"{'PASS' if not viol else 'FAIL'} {name} {size[0]}x{size[1]} in\n" + "".join(v + "\n" for v in viol))
    return viol
