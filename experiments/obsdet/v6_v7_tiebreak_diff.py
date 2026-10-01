"""Which DuckDB certificates changed between the v6 certifier (7aa9c889) and the v7 certifier (1369ffca), apart from
identifier quoting and case? Compares the stored certificates statement by statement (by db_id and SQL text) and
separates verdict changes from tie-break changes; a tie-break change that disappears after removing double quotes and
lower-casing is a quoting change. Usage: python v6_v7_tiebreak_diff.py <out.json>"""
import json
import sys

R = "experiments/obsdet/results"
SETS = {  # name: (v6 certificates, v7 certificates)
    "development": (f"{R}/final/cert_probes_v6.jsonl", f"{R}/v7/cert_probes_v7.jsonl"),
    "held-out": (f"{R}/final/cert_heldout_all.jsonl", f"{R}/v7/cert_heldout_all_v7.jsonl"),
    "unseen tasks I": (f"{R}/final/taskdisjoint/cert_td_all.jsonl", f"{R}/v7/cert_td_all_v7.jsonl"),
}


def load(path):
    out = {}
    for line in open(path):
        r = json.loads(line)
        out[(r["db_id"], r["sql"])] = r
    return out


def norm(tie):
    return [t.replace('"', "").lower() for t in (tie or [])]


def main(out_path):
    report = {}
    for name, (p6, p7) in SETS.items():
        a, b = load(p6), load(p7)
        common = sorted(set(a) & set(b))
        verdict, quoting, other = [], 0, []
        for k in common:
            va, vb = a[k].get("verdict") or a[k].get("info", {}).get("verdict"), b[k].get("verdict") or b[k].get("info", {}).get("verdict")
            if va != vb:
                verdict.append({"db_id": k[0], "sql": k[1][:160], "v6": va, "v7": vb})
            elif (a[k].get("tie_break") or []) != (b[k].get("tie_break") or []):
                if norm(a[k].get("tie_break")) == norm(b[k].get("tie_break")):
                    quoting += 1
                else:
                    other.append({"db_id": k[0], "sql": k[1][:160], "v6": a[k].get("tie_break"), "v7": b[k].get("tie_break")})
        report[name] = {"common": len(common), "verdict_changes": verdict, "quoting_only": quoting, "other_tie_break_changes": other}
        print(f"{name}: common {len(common)}, verdict changes {len(verdict)} "
              f"({sorted(set((x['v6'], x['v7']) for x in verdict))}), quoting-only {quoting}, other tie-break changes {len(other)}")
    json.dump(report, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
