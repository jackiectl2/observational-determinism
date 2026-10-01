"""Text numbers for Section 5 that no table prints (final certifier v7).

(1) Exact one-sided 95% Clopper-Pearson upper bounds for zero divergences among n statements (a reference under an
    iid per-statement model only): 1 - 0.05 ** (1 / n), for the supported statements of every set and engine.
(2) Set vs bag (duplicate-sensitive) BIRD accuracy per policy, averaged over the three physical orders of each agent
    run, and the sign of each paired difference to raw under both comparisons.
(3) Strict-policy burden per run from strict_burden.py's output captured in v7_analyze_output.md.
Reads experiments/obsdet/results/v7 (override with OBSDET_V7); writes text_stats.txt next to this script.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
V7 = os.environ.get("OBSDET_V7", os.path.join(HERE, "..", "..", "experiments", "obsdet", "results", "v7"))
if not os.path.isdir(V7):
    V7 = os.path.join(HERE, "..", "experiments", "obsdet", "results", "v7")
POL = {"raw": "Raw", "slx": "Smart-lex", "cer": "Hybrid", "str": "Strict"}
RUNS = [("original tasks", "e4_v7"), ("unseen tasks I", "e4_v7td"), ("unseen tasks II", "e4_v7td2")]
SUPPORTED = {"dev": (854, 836), "held-out": (776, 759), "unseen I": (999, 978), "unseen II": (945, 930)}


def main():
    out = ["Zero-divergence reference bounds (iid model): " + "; ".join(
        f"{k} DuckDB 0/{a}: {100 * (1 - 0.05 ** (1 / a)):.2f}%, PostgreSQL 0/{b}: {100 * (1 - 0.05 ** (1 / b)):.2f}%"
        for k, (a, b) in SUPPORTED.items())]
    na, nb = sum(a for a, _ in SUPPORTED.values()), sum(b for _, b in SUPPORTED.values())
    out.append(f"Pooled: DuckDB 0/{na}: {100 * (1 - 0.05 ** (1 / na)):.2f}%, PostgreSQL 0/{nb}: {100 * (1 - 0.05 ** (1 / nb)):.2f}%")
    lo, hi = 1.0, 0.0
    for label, tag in RUNS:
        for model in ("qwen3_8b", "phi4"):
            a = json.load(open(os.path.join(V7, f"{tag}_{model}", "summary_e4.json")))["all"]
            acc = {k: v["mean"] for k, v in a["accuracy"].items()}
            bag = a["bag_accuracy"]
            for k in acc:
                lo, hi = min(lo, acc[k] - bag[k]), max(hi, acc[k] - bag[k])
            mean = {p: (sum(acc[f"{p}_{o}_t1"] for o in ("orig", "p42", "p7")) / 3,
                        sum(bag[f"{p}_{o}_t1"] for o in ("orig", "p42", "p7")) / 3) for p in POL}
            for p in ("slx", "cer", "str"):
                ds, db = 100 * (mean[p][0] - mean["raw"][0]), 100 * (mean[p][1] - mean["raw"][1])
                same = (ds > 0) == (db > 0) or abs(ds) < 0.05 or abs(db) < 0.05
                out.append(f"{label} {model} {POL[p]} - Raw: set {ds:+.1f} pp, bag {db:+.1f} pp, same sign: {same}")
    out.append(f"Set minus bag accuracy per condition (all runs): {100 * lo:.1f}-{100 * hi:.1f} pp")
    burden = re.findall(r"(\S+): strict burden \(strict_burden.py\): (\d+)/150 tasks with >=1 withheld preview; "
                        r"median ([\d.]+) \(max (\d+)\) among them; hybrid-correct -> strict-wrong (\d+), "
                        r"hybrid-wrong -> strict-correct (\d+)", open(os.path.join(V7, "RESULTS_V7.md")).read())
    out += [f"strict burden {m}: {t}/150 tasks, median {md} (max {mx}), hybrid-correct->strict-wrong {a}, "
            f"reverse {b}" for m, t, md, mx, a, b in burden]
    text = "\n".join(out) + "\n"
    open(os.path.join(HERE, "text_stats.txt"), "w").write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
