"""Shared plotting style: Linux Libertine (the acmart body font), 8 pt text, vector PDF output."""
import glob
import os
import shutil
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_data():
    """experiments/obsdet/results/final of the project that contains this directory (figures/ or paper/figures/)."""
    d = HERE
    while d != os.path.dirname(d):
        cand = os.path.join(d, "experiments", "obsdet", "results", "final")
        if os.path.isdir(cand):
            return cand
        d = os.path.dirname(d)
    return os.path.join(HERE, "..", "experiments", "obsdet", "results", "final")


DATA = os.environ.get("OBSDET_DATA", _find_data())
V7 = os.environ.get("OBSDET_V7", os.path.join(DATA, "..", "v7"))  # results with the final certifier (v7)
OUT = os.environ.get("FIG_OUT", HERE)

for f in glob.glob(os.path.join(HERE, "fonts", "*.otf")):
    font_manager.fontManager.addfont(f)
FAMILY = "Linux Libertine O" if any("Libertine" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Serif"

matplotlib.rcParams.update({
    "font.family": "serif", "font.serif": [FAMILY, "DejaVu Serif"], "font.size": 8,
    "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "pdf.fonttype": 42, "mathtext.fontset": "stix",
})
# colorblind-safe (Okabe-Ito); verdicts ordered from "no change needed" to "rejected"
VERDICT_COLORS = {"DET": "#009E73", "NARROW": "#56B4E9", "ALL": "#E69F00", "UNSUPPORTED": "#999999"}
POLICY_COLORS = {"certified": "#0072B2", "smartlex": "#D55E00"}
COL_WIDTH_IN = 3.33  # one column of the two-column acmart layout


def signed_pp(x):
    """A difference in percentage points with its sign; values that round to zero print as an unsigned 0.0."""
    v = round(100 * x, 1)
    return "$0.0$" if v == 0 else f"${v:+.1f}$"


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path)
    if path.endswith(".pdf") and shutil.which("gs"):
        # matplotlib embeds OpenType-CFF fonts in an OpenType wrapper, which some PDF readers report as a font-type
        # mismatch; ghostscript re-embeds them as plain CFF.
        tmp = path + ".tmp.pdf"
        subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-dEmbedAllFonts=true",
                        "-dSubsetFonts=true", "-dCompatibilityLevel=1.5", f"-sOutputFile={tmp}", path], check=True)
        os.replace(tmp, path)
    print("saved", path)
