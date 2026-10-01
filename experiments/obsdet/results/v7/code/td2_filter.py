"""Second task-disjoint held-out set: from the distinct statements of the v7td2 agents (the output of heldout_probes.py
on the v7td2 runs), remove statements equal to a development probe, to a statement of the first held-out set
(cert_heldout_all.jsonl) or to a statement of the first task-disjoint set (cert_td_all.jsonl), each exactly and after
heldout_dedup.norm (comments, trailing semicolons, whitespace), then statements that fail on SF1. The kept records
are written unchanged (heldout_probes.py format), together with the selection funnel.

Usage: python td2_filter.py <dev_cert_probes.jsonl> <cert_heldout_all.jsonl> <cert_td_all.jsonl> <cert_td2_all.jsonl> <out_td2_new.jsonl> <out_funnel.json>
"""
import json
import sys
from collections import Counter

from heldout_dedup import norm

PRIOR = ["dev", "heldout1", "td1"]


def keys(path):
    recs = [json.loads(l) for l in open(path)]
    return {(r["db_id"], r["sql"]) for r in recs}, {(r["db_id"], norm(r["sql"])) for r in recs}


def main(dev_path, h1_path, td1_path, all_path, out_path, funnel_path):
    prior = [(name, *keys(p)) for name, p in zip(PRIOR, (dev_path, h1_path, td1_path))]
    recs = [json.loads(l) for l in open(all_path)]
    stage, kept, by_model = Counter(), [], Counter()
    for r in recs:
        k, kn = (r["db_id"], r["sql"]), (r["db_id"], norm(r["sql"]))
        s = next((f"{name}_exact" if k in ex else f"{name}_normalized" for name, ex, nm in prior if k in ex or kn in nm),
                 "fails_on_sf1" if "exec_error" in r else "kept")
        stage[s] += 1
        if s == "kept":
            kept.append(r)
            for m in r["models"]:
                by_model[m] += 1
    assert stage["dev_exact"] == sum(r["in_dev"] for r in recs)
    with open(out_path, "w") as f:
        for r in kept:
            f.write(json.dumps(r, default=str) + "\n")
    v = Counter(r["verdict"] for r in kept)
    order = [f"{n}_{x}" for n in PRIOR for x in ("exact", "normalized")] + ["fails_on_sf1"]
    funnel = {"distinct_statements": len(recs), "removed_in_order": {s: stage[s] for s in order},
              "kept": len(kept), "kept_distinct_after_norm": len({(r["db_id"], norm(r["sql"])) for r in kept}),
              "kept_by_model": dict(by_model), "kept_by_db": dict(sorted(Counter(r["db_id"] for r in kept).items())),
              "kept_in_both_models": sum(len(r["models"]) > 1 for r in kept),
              "kept_occurrences": sum(r["occurrences"] for r in kept),
              "verdicts": {x: {"n": v[x], "pct": round(100 * v[x] / len(kept), 1)} for x in ("DET", "NARROW", "ALL", "UNSUPPORTED")},
              "rewrite_failed": sum(r.get("rewrite_ok") is False for r in kept)}
    json.dump(funnel, open(funnel_path, "w"), indent=1)
    print(json.dumps(funnel, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:7])
