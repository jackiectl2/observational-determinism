"""Table 2: preview divergence across equivalent executions, per statement set, certifier version and engine.

Supported = certificate DET/NARROW/ALL in the engine's dialect. A statement counts as diverged for a policy if its
rendered preview (header, first 20 rows, exact count) differed among the configurations; statements not observed in
every configuration are censored (reported as +cens., in addition to n). Statement sets: development probes; held-out
statements (deduplicated as in heldout_dedup.py); statements from the first and second sets of unseen tasks. All rows
use the final certifier (v7); the v6 result on the first set of unseen tasks is reported in the text.
"""
import json
import os

from paper_plot_style import OUT, V7

SUP = ("DET", "NARROW", "ALL")


def keys(path):
    return {(json.loads(line)["db_id"], json.loads(line)["sql"]) for line in open(path)}


def row(path, keep=None):
    c = {"sup": 0, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 0, "uns": 0, "uns_cens": 0, "uns_raw": 0, "uns_slx": 0}
    for line in open(path):
        r = json.loads(line)
        if keep is not None and (r["db_id"], r["sql"]) not in keep:
            continue
        pols = r.get("policies")
        if not pols:  # transpile error: no observation (PostgreSQL certificate UNSUPPORTED)
            c["uns_cens"] += 1
            continue
        cer = pols["certified"]["diverged"]
        if r["verdict"] in SUP:
            if cer is None:
                c["sup_cens"] += 1
                continue
            c["sup"] += 1
            c["cer"] += cer
            c["slx"] += bool(pols["smartlex"]["diverged"])
            c["raw"] += bool(pols["raw"]["diverged"])
        elif pols["raw"]["diverged"] is not None and pols["smartlex"]["diverged"] is not None:
            c["uns"] += 1
            c["uns_raw"] += pols["raw"]["diverged"]
            c["uns_slx"] += pols["smartlex"]["diverged"]
        else:
            c["uns_cens"] += 1
    return c


def main():
    held = keys(os.path.join(V7, "cert_heldout_kept_v7.jsonl"))
    td1 = keys(os.path.join(V7, "cert_td_new_v7.jsonl"))
    td2 = keys(os.path.join(V7, "cert_td2_new.jsonl"))
    rows = [(f"Development ({1015:,})", "", "DuckDB", row(os.path.join(V7, "sound_v7.jsonl"))),
            ("", "", "PostgreSQL", row(os.path.join(V7, "sound_pg_v7.jsonl"))),
            (f"Held-out ({len(held):,})", "", "DuckDB", row(os.path.join(V7, "sound_heldout_v7.jsonl"), held)),
            ("", "", "PostgreSQL", row(os.path.join(V7, "sound_pg_heldout_v7.jsonl"), held)),
            (f"Unseen tasks I ({len(td1):,})", "", "DuckDB", row(os.path.join(V7, "sound_td_v7.jsonl"), td1)),
            ("", "", "PostgreSQL", row(os.path.join(V7, "sound_pg_td_v7.jsonl"), td1)),
            (f"Unseen tasks II ({len(td2):,})", "", "DuckDB", row(os.path.join(V7, "sound_td2.jsonl"), td2)),
            ("", "", "PostgreSQL", row(os.path.join(V7, "sound_pg_td2.jsonl"), td2))]
    lines = [r"\begin{tabular}{@{}ll rrrr rrr@{}}", r"\toprule",
             r" & & \multicolumn{4}{c}{Supported (DET/NARROW/ALL)} & \multicolumn{3}{c}{UNSUPPORTED} \\",
             r"\cmidrule(lr){3-6}\cmidrule(l){7-9}",
             r"Statements & Engine & $n$ (+cens.) & Certified rewrite & Smart-lex & Raw & $n$ (+cens.) & Raw & Smart-lex \\",
             r"\midrule"]
    for i, (ps, _, eng, c) in enumerate(rows):
        if i in (2, 4, 6):
            lines.append(r"\midrule")
        lines.append(f"{ps} & {eng} & {c['sup']} (+{c['sup_cens']}) & {c['cer']} & {c['slx']} & {c['raw']} & "
                     f"{c['uns']} (+{c['uns_cens']}) & {c['uns_raw']} & {c['uns_slx']} \\\\")
        print(ps, eng, c)
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = os.path.join(OUT, "TABLE_soundness.tex")
    open(path, "w").write("\n".join(lines) + "\n")
    print("saved", path)


if __name__ == "__main__":
    main()
