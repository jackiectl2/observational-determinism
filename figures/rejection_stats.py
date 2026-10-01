"""Text numbers for Sections 3.5 and 5: UNSUPPORTED reason codes (final certifier v7) and smart-lex divergence by
reason, for the development probes, the held-out statements and the statements from the second set of unseen tasks, on
DuckDB and PostgreSQL. Reads experiments/obsdet/results/v7 (override with OBSDET_V7). Output: rejection_stats.txt.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
V7 = os.environ.get("OBSDET_V7", os.path.join(HERE, "..", "..", "experiments", "obsdet", "results", "v7"))
if not os.path.isdir(V7):  # when run from the project's figures/ directory
    V7 = os.path.join(HERE, "..", "experiments", "obsdet", "results", "v7")
SETS = [("development", "cert_probes_v7.jsonl", "sound_v7.jsonl", "sound_pg_v7.jsonl"),
        ("held-out", "cert_heldout_kept_v7.jsonl", "sound_heldout_v7.jsonl", "sound_pg_heldout_v7.jsonl"),
        ("unseen tasks I", "cert_td_new_v7.jsonl", "sound_td_v7.jsonl", "sound_pg_td_v7.jsonl"),
        ("unseen tasks II", "cert_td2_new.jsonl", "sound_td2.jsonl", "sound_pg_td2.jsonl")]


def load(name):
    return [json.loads(line) for line in open(os.path.join(V7, name))]


def main():
    out = []
    for name, cert, sd, spg in SETS:
        rows = load(cert)
        keep = {(r["db_id"], r["sql"]) for r in rows}
        reason = {(r["db_id"], r["sql"]): r.get("reason") for r in rows}
        c = collections.Counter((r.get("reason") or "?").split(":")[0] for r in rows if r["verdict"] == "UNSUPPORTED")
        out.append(f"{name}: {len(rows)} statements, UNSUPPORTED {sum(c.values())} ({100 * sum(c.values()) / len(rows):.1f}%)")
        out.append("  by reason code: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
        for eng, f in (("DuckDB", sd), ("PostgreSQL", spg)):
            div, tot = collections.Counter(), collections.Counter()
            for r in load(f):
                k = (r["db_id"], r["sql"])
                if k not in keep or r["verdict"] != "UNSUPPORTED" or not r.get("policies"):
                    continue
                if r["policies"]["smartlex"]["diverged"] is None:
                    continue
                rc = (r.get("reason") or reason.get(k) or "?").split(":")[0]
                tot[rc] += 1
                div[rc] += bool(r["policies"]["smartlex"]["diverged"])
            out.append(f"  {eng}: smart-lex diverged on UNSUPPORTED {sum(div.values())}/{sum(tot.values())}; by reason: "
                       + ", ".join(f"{k} {div[k]}/{tot[k]}" for k in sorted(tot, key=lambda x: -tot[x])))
    text = "\n".join(out) + "\n"
    open(os.path.join(HERE, "rejection_stats.txt"), "w").write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
