"""E3 analysis. Prints Markdown; writes <out>.json and <out>_per_probe.csv.

python cost_analyze.py <cost_dir> <out_prefix> <duck_tag> <pg_tag> <cert_probes.jsonl> <catalog.json>
  A. preview + count model (primary): duck_pcnat_<duck_tag>_*.jsonl, duck_pcctl_<duck_tag>.jsonl,
     pg_pcnat_<pg_tag>_*.jsonl, pg_pcctl_<pg_tag>_*.jsonl; total = preview + count (bar), preview alone (secondary).
  B. "tool as implemented in the pilot" (capped fetch <= 100k rows, cert file v3): duck_nat_*, pg_nat_*, duck_ctl,
     pg_ctl_*.
Probe sets per engine (fixed across scales and policies):
  main        probes whose queries succeed at SF1, with no error at any scale and no timeout at any scale;
  sensitivity main + probes with a timeout at some scale, each timed-out query counted at the timeout (60 s, a
              lower bound); probes skipped at xmax because all policies timed out at x10 are counted at 60 s.
Probes that fail with an error at some scale (e.g. "more than one row returned by a subquery" once rows are
duplicated) cannot be timed and are excluded from both, counted and listed.
Scales x10/x100/x30 replicate the SF1 data (offset copies): a stress test, not a representative workload.
"""
import csv
import glob
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict

POL = ("raw", "smartlex", "certified")
CLASSES = ("order_limit", "order_only", "limit_no_order", "distinct", "group_by", "other")
VERDICTS = ("DET", "NARROW", "ALL", "UNSUPPORTED")
TIMEOUT = 60.0
CSV = []
LIMLAB = {"L1": "L1: LIMIT/OFFSET, verdict != DET (predeclared class)", "L2": "L2: LIMIT without ORDER BY (syntactic)",
          "L3": "L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired)"}


def med(x):
    return statistics.median(x) if x else None


def load(pattern):
    return [json.loads(line) for f in sorted(glob.glob(pattern)) for line in open(f)]


def fmt_s(x):
    return f"{x:.2f}" if x >= 1 else f"{x:.3f}"


def ratio(a, b):
    return a / b if b else float("nan")


def q_time(s):
    """(median preview/query time, status) of one policy's result; timeouts count as TIMEOUT."""
    if s["status"] in ("ok", "timeout_count"):
        return med(s["t"]), "ok"
    return (TIMEOUT, "timeout") if s["status"].startswith("timeout") else (None, "error")


def probe_row(r, has_count):
    """Per-probe values: preview t, total tot (= preview + count, or the pctxn transaction), count; None if error."""
    if "res" not in r:  # skipped at xmax: all three policies timed out at x10
        c = TIMEOUT if has_count else 0.0
        return {"t": {p: TIMEOUT for p in POL}, "tot": {p: TIMEOUT + c for p in POL}, "count": c, "cens": True, "rec": r}
    res = r["res"]
    tt = {p: q_time(res[p]) for p in POL}
    if any(v[1] == "error" for v in tt.values()):
        return None
    cens = any(v[1] == "timeout" for v in tt.values())
    if "txn_t" in res["raw"]:  # PostgreSQL pctxn: preview + count inside each policy's read-only transaction
        tot, cnts = {}, []
        for p in POL:
            s = res[p]
            if s["status"] == "ok":
                tot[p] = med(s["txn_t"])
                cnts.append(med(s["count_t"]))
            elif s["status"] == "timeout_count":
                tot[p], cens = med(s["t"]) + TIMEOUT, True
                cnts.append(TIMEOUT)
            else:
                tot[p] = TIMEOUT
        cnt = statistics.mean(cnts) if cnts else TIMEOUT
    elif "count" in res:
        c, st = q_time(res["count"])
        if st == "error":
            return None
        cens |= st == "timeout"
        tot, cnt = {p: tt[p][0] + c for p in POL}, c
    else:
        tot, cnt = {p: tt[p][0] for p in POL}, 0.0
    return {"t": {p: tt[p][0] for p in POL}, "tot": tot, "count": cnt, "cens": cens, "rec": r}


def totals(rows, keys, m):
    return {p: sum(rows[k][m][p] for k in keys) for p in POL}


def boot(values_fn, keys, n=2000, seed=0):
    rng, out = random.Random(seed), []
    for _ in range(n):
        out.append(values_fn([rng.choice(keys) for _ in keys]))
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n) - 1]


def lim_class(rec, which):
    c, v = rec["cls"], rec["verdict"]
    if which == "L1":
        return c in ("order_limit", "limit_no_order") and v != "DET"
    if which == "L2":
        return c == "limit_no_order"
    return c in ("order_limit", "limit_no_order") and v in ("NARROW", "ALL")


def dominance(rows, keys, m):
    """Largest single-probe share of the smartlex total, the certified total and of smartlex - certified."""
    T = totals(rows, keys, m)
    d = {k: rows[k][m]["smartlex"] - rows[k][m]["certified"] for k in keys}
    top = max(keys, key=lambda k: abs(d[k]))
    diff = T["smartlex"] - T["certified"]
    return {"share_S": max(rows[k][m]["smartlex"] for k in keys) / T["smartlex"],
            "share_C": max(rows[k][m]["certified"] for k in keys) / T["certified"],
            "top_diff_probe": top, "top_diff_share": d[top] / diff if diff else float("inf")}


def engine_block(title, recs, scales, largest, m, full, tag):
    es = {}
    print(f"\n### {title}\n")
    first = scales[0]
    has_count = any("count" in (r.get("res") or {}) or "txn_t" in (r.get("res") or {}).get("raw", {}) for r in recs)
    pset = {r["i"] for r in recs if r["scale"] == first and r.get("res") and all(x["status"] == "ok" for x in r["res"].values())}
    per, err = {s: {} for s in scales}, defaultdict(set)
    for r in recs:
        if r["scale"] in per and r["i"] in pset:
            row = probe_row(r, has_count)
            if row is None:
                err[r["scale"]].add(r["i"])
            else:
                per[r["scale"]][r["i"]] = row
    errs = set().union(*err.values()) if err else set()
    missing = {i for i in pset for s in scales if i not in per[s] and i not in errs}
    sens = pset - errs - missing
    main = {i for i in sens if not any(per[s][i]["cens"] for s in scales)}
    print(f"Probes replayed: {len({r['i'] for r in recs})}; succeeding at {first}: {len(pset)}; failing with an error at a "
          f"larger scale (excluded, cannot be timed): {len(errs)} {sorted(errs)[:12]}{'...' if len(errs) > 12 else ''}; "
          f"missing: {len(missing)}; with a timeout at some scale: {len(sens - main)} {sorted(sens - main)}. "
          f"**Main set: {len(main)} probes, identical at every scale.** Scales beyond {first} are replicated-data stress tests.\n")
    print("| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) "
          "| largest single-probe share of S / C total | share of S-C from one probe |" + (" count s |" if has_count and m == "tot" else ""))
    print("|---|---|---|---|---|---|---|---|---|---|" + ("---|" if has_count and m == "tot" else ""))
    for s in scales:
        rows = per[s]
        for lab, keys in (("main", sorted(main)), ("sensitivity: + timeouts at 60 s (lower bounds)", sorted(sens))):
            if not keys or (lab != "main" and len(sens) == len(main)):
                continue
            T = totals(rows, keys, m)
            red = 1 - T["certified"] / T["smartlex"]
            ci = boot(lambda b: 1 - sum(rows[k][m]["certified"] for k in b) / sum(rows[k][m]["smartlex"] for k in b), keys)
            rat = lambda b: med([rows[k][m]["smartlex"] / rows[k][m]["certified"] for k in b])  # noqa: E731
            mr, mci = rat(keys), boot(rat, keys)
            dm = dominance(rows, keys, m)
            flag = " **(dominated)**" if max(dm["share_S"], dm["share_C"]) > 0.5 else ""
            dflag = " **(one probe)**" if dm["top_diff_share"] > 0.5 and red > 0 else ""
            cnt = sum(rows[k]["count"] for k in keys)
            print(f"| {s} | {lab} | {len(keys)} | {fmt_s(T['raw'])} | {fmt_s(T['smartlex'])} | {fmt_s(T['certified'])} | "
                  f"{100 * red:+.1f}% [{100 * ci[0]:+.1f}, {100 * ci[1]:+.1f}] | {mr:.3f}x [{mci[0]:.3f}, {mci[1]:.3f}] | "
                  f"{dm['share_S']:.0%} / {dm['share_C']:.0%}{flag} | "
                  + (f"#{dm['top_diff_probe']} {dm['top_diff_share']:.0%}{dflag} |" if abs(red) >= 0.005 else "n/a (difference < 0.5%) |")
                  + (f" {fmt_s(cnt)} |" if has_count and m == "tot" else ""))
            es.setdefault(s, {})[lab.split(":")[0]] = {"n": len(keys), "total": T, "reduction": red, "ci": ci,
                                                      "median_ratio": mr, "median_ratio_ci": mci, "dominance": dm,
                                                      "count_total": cnt}
        if m == "tot":
            for k in sorted(sens):
                v = rows[k]
                CSV.append([title.split(",")[0], tag, s, k, v["rec"]["db"], v["rec"]["cls"], v["rec"]["verdict"],
                            v["rec"].get("duckdb_verdict", v["rec"]["verdict"]), int(k in main)]
                           + [round(v["t"][p], 6) for p in POL] + [round(v["count"], 6)] + [round(v["tot"][p], 6) for p in POL])
    es["sets"] = {"main": len(main), "sensitivity": len(sens), "errors": sorted(errs), "timeouts": sorted(sens - main)}
    rows = per[largest]
    keys = sorted(main)
    if not keys:
        return es, {}
    rr = sorted(rows[k][m]["smartlex"] / rows[k][m]["certified"] for k in keys)
    q = lambda f: rr[min(len(rr) - 1, int(f * len(rr)))]  # noqa: E731
    es["distribution"] = {"p10": q(0.1), "p25": q(0.25), "p50": q(0.5), "p75": q(0.75), "p90": q(0.9),
                          "faster10": sum(x > 1.1 for x in rr) / len(rr), "slower10": sum(x < 1 / 1.1 for x in rr) / len(rr)}
    d = es["distribution"]
    print(f"\nPer-probe smartlex/certified at {largest} (main set, n={len(keys)}): p10 {d['p10']:.2f}x, p25 {d['p25']:.2f}x, "
          f"median {d['p50']:.2f}x, p75 {d['p75']:.2f}x, p90 {d['p90']:.2f}x; certified >10% faster on {d['faster10']:.0%} "
          f"of probes, >10% slower on {d['slower10']:.0%}.")
    lims = {}
    print(f"\nLIMIT classes at {largest} (main set):\n\n| class | n | raw s | smartlex s | certified s | smartlex/certified "
          "(ratio of totals) | 95% CI | median per-probe S/C |\n|---|---|---|---|---|---|---|---|")
    for w in ("L1", "L2", "L3"):
        ks = [k for k in keys if lim_class(rows[k]["rec"], w)]
        if ks:
            T = totals(rows, ks, m)
            ci = boot(lambda b: sum(rows[k][m]["smartlex"] for k in b) / sum(rows[k][m]["certified"] for k in b), ks)
            pr = med([rows[k][m]["smartlex"] / rows[k][m]["certified"] for k in ks])
            print(f"| {LIMLAB[w]} | {len(ks)} | {fmt_s(T['raw'])} | {fmt_s(T['smartlex'])} | {fmt_s(T['certified'])} | "
                  f"{ratio(T['smartlex'], T['certified']):.2f}x | [{ci[0]:.2f}, {ci[1]:.2f}] | {pr:.2f}x |")
            lims[w] = {"n": len(ks), **T, "ratio": ratio(T["smartlex"], T["certified"]), "ci": ci, "median_probe_ratio": pr}
    es["limit_classes"] = lims
    top = sorted(keys, key=lambda k: -(rows[k][m]["smartlex"] - rows[k][m]["certified"]))
    red = lambda ks: 1 - sum(rows[k][m]["certified"] for k in ks) / sum(rows[k][m]["smartlex"] for k in ks)  # noqa: E731
    es["leave_out"] = {"top1": red(top[1:]), "top5": red(top[5:])}
    print(f"\nLeave-out at {largest} (main set): certified vs smartlex {100 * red(keys):+.1f}%; without the largest "
          f"contributor #{top[0]} {100 * red(top[1:]):+.1f}%; without the top 5 {100 * red(top[5:]):+.1f}%.")
    if not full:
        return es, {k: rows[k] for k in keys}
    print(f"\nPer class at {largest} (main set; probe class x verdict), total seconds:\n")
    print("| class | verdict | n | raw | smartlex | certified | smartlex/certified | certified/raw |\n|---|---|---|---|---|---|---|---|")
    grp = defaultdict(list)
    for k in keys:
        grp[(rows[k]["rec"]["cls"], rows[k]["rec"]["verdict"])].append(k)
    cls = {}
    for c in CLASSES:
        for vd in VERDICTS + ("all",):
            ks = grp.get((c, vd)) if vd != "all" else [k for (cc, _), kk in grp.items() if cc == c for k in kk]
            if not ks:
                continue
            T = totals(rows, ks, m)
            b = "**" if vd == "all" else ""
            print(f"| {b}{c}{b} | {vd} | {len(ks)} | {fmt_s(T['raw'])} | {fmt_s(T['smartlex'])} | {fmt_s(T['certified'])} | "
                  f"{b}{ratio(T['smartlex'], T['certified']):.2f}x{b} | {ratio(T['certified'], T['raw']):.2f}x |")
            cls[f"{c}|{vd}"] = {"n": len(ks), **T}
    es["per_class"] = cls
    det = [k for k in keys if rows[k]["rec"]["verdict"] == "DET"]
    uns = [k for k in keys if rows[k]["rec"]["verdict"] == "UNSUPPORTED"]
    Td, Tu = totals(rows, det, "t"), totals(rows, uns, "t")
    es["aa"] = {"det_cert_over_raw": ratio(Td["certified"], Td["raw"]), "uns_cert_over_smartlex": ratio(Tu["certified"], Tu["smartlex"])}
    print(f"\nA/A check at {largest} (identical preview SQL timed as two policies): DET certified/raw = "
          f"{es['aa']['det_cert_over_raw']:.3f} (n={len(det)}); UNSUPPORTED certified/smartlex = "
          f"{es['aa']['uns_cert_over_smartlex']:.3f} (n={len(uns)}).")
    f = lambda k: (f"#{k} {rows[k]['rec']['db'][:10]} {rows[k]['rec']['cls']}/{rows[k]['rec']['verdict']} "  # noqa: E731
                   f"{rows[k][m]['smartlex'] - rows[k][m]['certified']:+.3f}")
    print(f"\nLargest per-probe smartlex - certified at {largest} (s): " + ", ".join(map(f, top[:5]))
          + "; most negative: " + ", ".join(map(f, top[-5:])) + ".")
    return es, {k: rows[k] for k in keys}


def tie_breakdown(rows, probes, cat, label, m, pg=False):
    grp = defaultdict(list)
    for k, v in rows.items():
        pr = probes[k]
        rec = v["rec"]
        if rec["verdict"] != "NARROW":
            continue
        tb = rec.get("tie_break") if pg else pr.get("tie_break")
        cols = [t.split(".")[-1].strip('"').lower() for t in tb or []]
        names = [n.lower() for n in pr["info"].get("select_names") or []]
        in_out = (any(n == "*" or n.endswith(".*") for n in names) or not names) or all(c in names for c in cols)
        types = {ty for t2 in cat[pr["db_id"]].values() for c2, ty in t2["columns"].items() if c2.lower() in cols}
        kt = "string" if "VARCHAR" in types else ("numeric" if types else "unknown")
        grp[("output" if in_out else "non-output", kt)].append(k)
    print(f"\nNARROW probes at {label} by certified tie-break column (output column or not (name match); type):\n")
    print("| tie-break | type | n | raw s | smartlex s | certified s | smartlex/certified |\n|---|---|---|---|---|---|---|")
    out = {}
    for (io, kt), ks in sorted(grp.items()):
        T = totals(rows, ks, m)
        print(f"| {io} | {kt} | {len(ks)} | {fmt_s(T['raw'])} | {fmt_s(T['smartlex'])} | {fmt_s(T['certified'])} | "
              f"{ratio(T['smartlex'], T['certified']):.2f}x |")
        out[f"{io}|{kt}"] = {"n": len(ks), **T}
    return out


def duck_profile(rows, label):
    agg, num, keys = {p: Counter() for p in POL}, {p: defaultdict(float) for p in POL}, {p: [] for p in POL}
    n = 0
    for v in rows.values():
        pr = v["rec"].get("prof")
        if not pr:
            continue
        n += 1
        for p in POL:
            x = pr[p]
            if x.get("status") != "ok":
                agg[p]["profile failed"] += 1
                continue
            main = max(x["sorts"], key=lambda s: s["rows_in"] or 0) if x["sorts"] else None
            agg[p][main["op"] if main else "no sort"] += 1
            agg[p]["late materialization"] += bool(x["late_mat"])
            if main:
                keys[p].append(main["keys"])
            num[p]["engine latency s"] += x["latency"] or 0
            num[p]["sort operators s (sum over threads)"] += sum(t for o, t in x["timing"].items() if o in ("TOP_N", "ORDER_BY"))
            num[p]["table scans s (sum over threads)"] += x["timing"].get("TABLE_SCAN", 0)
            num[p]["rows scanned (M)"] += (x["rows_scanned"] or 0) / 1e6
            num[p]["peak buffer memory (GB, sum over probes)"] += (x["peak_mem"] or 0) / 2 ** 30
    print(f"\nDuckDB plan attribution, {label} (one EXPLAIN ANALYZE per policy and probe, n={n}):\n")
    print("| quantity | raw | smartlex | certified |\n|---|---|---|---|")
    for q in ("TOP_N", "ORDER_BY", "no sort", "late materialization", "profile failed"):
        lab = f"main sort operator = {q}" if q in ("TOP_N", "ORDER_BY", "no sort") else q
        print(f"| {lab} |", " | ".join(str(agg[p][q]) for p in POL), "|")
    print("| mean sort keys in main sort |", " | ".join(f"{statistics.mean(keys[p]):.2f}" if keys[p] else "-" for p in POL), "|")
    for q in num["raw"]:
        print(f"| {q} |", " | ".join(f"{num[p][q]:.2f}" for p in POL), "|")
    return {p: {"counts": dict(agg[p]), **num[p], "mean_keys": statistics.mean(keys[p]) if keys[p] else None} for p in POL}


def pg_category(x):
    if x.get("status") != "ok":
        return "failed"
    types = {s["type"] for s in x["sorts"]}
    idx = any(s["type"] in ("Index Scan", "Index Only Scan") for s in x["scans"])
    if "Incremental Sort" in types:
        return "incremental sort"
    if "Sort" in types:
        return "top-N heapsort" if {s["method"] for s in x["sorts"] if s["type"] == "Sort"} == {"top-N heapsort"} else "sort (full)"
    return "index-ordered, no sort" if idx and x["chain"][0] == "Limit" else "no sort"


def pg_explain(rows, label):
    out = {}
    for sel_lab, sel in (("all probes", lambda v: True), ("NARROW", lambda v: v["rec"]["verdict"] == "NARROW"),
                         ("NARROW with LIMIT", lambda v: v["rec"]["verdict"] == "NARROW"
                          and v["rec"]["cls"] in ("order_limit", "limit_no_order"))):
        cnt, num = {p: Counter() for p in POL}, {p: defaultdict(float) for p in POL}
        for v in rows.values():
            ex = v["rec"].get("explain")
            if not ex or not sel(v):
                continue
            for p in POL:
                cnt[p][pg_category(ex[p])] += 1
                if ex[p].get("status") == "ok":
                    num[p]["execution time s (EXPLAIN ANALYZE)"] += (ex[p]["exec_ms"] or 0) / 1000
                    num[p]["rows scanned (M)"] += ex[p]["rows_scanned"] / 1e6
                    num[p]["shared buffers hit+read (k)"] += ((ex[p]["hit"] or 0) + (ex[p]["read"] or 0)) / 1e3
                    num[p]["temp blocks written (k)"] += (ex[p]["temp_written"] or 0) / 1e3
        print(f"\nPostgreSQL plans, {label}, {sel_lab}:\n\n| quantity | raw | smartlex | certified |\n|---|---|---|---|")
        for c in sorted({c for p in POL for c in cnt[p]}):
            print(f"| plan: {c} |", " | ".join(str(cnt[p][c]) for p in POL), "|")
        for q in num["raw"]:
            print(f"| {q} |", " | ".join(f"{num[p][q]:.2f}" for p in POL), "|")
        out[sel_lab] = {p: {"plans": dict(cnt[p]), **num[p]} for p in POL}
    return out


def controlled(recs, name, scales):
    pcm = any("count" in r["res"] or "txn_t" in r["res"]["raw"] for r in recs)
    print(f"\n### Controlled LIMIT study, {name} (median ms over 5 repetitions; S/C = smartlex/certified preview"
          + ("; in brackets the count query / the pctxn transaction of certified" if pcm else "") + ")\n")
    by = defaultdict(dict)
    for r in recs:
        by[(r["db"], r["table"], r["form"])][r["scale"]] = r
    print("| table | form | verdict, tie-break | " + " | ".join(f"{s} raw / smartlex / certified | {s} S/C" for s in scales) + " |")
    print("|---|---|---|" + "---|---|" * len(scales))
    out = {}
    for (db, t, f), d in sorted(by.items()):
        cells = []
        for s in scales:
            r = d.get(s)
            if not r:
                cells += ["-", "-"]
                continue
            mm = {p: (med(r["res"][p]["t"]) if r["res"][p]["status"] == "ok" else None) for p in POL}
            extra = None
            if "count" in r["res"]:
                extra = med(r["res"]["count"]["t"])
            elif "txn_t" in r["res"]["raw"]:
                extra = med(r["res"]["certified"]["txn_t"])
            cells.append(" / ".join(f"{1000 * mm[p]:.2f}" if mm[p] is not None else r["res"][p]["status"][:8] for p in POL)
                         + (f" [{1000 * extra:.2f}]" if extra is not None else ""))
            cells.append(f"{mm['smartlex'] / mm['certified']:.1f}x" if mm["smartlex"] and mm["certified"] else "-")
            out[f"{t}.{f}.{s}"] = {**mm, "extra": extra}
        fr = d[min(d, key=scales.index)]
        print(f"| {t} | {f} | {fr['verdict']} {fr.get('tie_break') or ''} | " + " | ".join(cells) + " |")
    return out


def bar_line(label, es, big):
    if big not in es or "main" not in es[big]:
        return f"- {label}: no data at {big}."
    mn, sn = es[big]["main"], es[big].get("sensitivity")
    l1 = es.get("limit_classes", {}).get("L1", {})
    s = (f"- **{label}**, {big}, main set (n={mn['n']}): certified vs smartlex {100 * mn['reduction']:+.1f}% "
         f"(95% CI [{100 * mn['ci'][0]:+.1f}, {100 * mn['ci'][1]:+.1f}]) -> criterion 1 (>= 20% lower): "
         f"**{'MET' if mn['reduction'] >= 0.20 else 'NOT MET'}**")
    if sn:
        s += (f"; sensitivity with timeouts at 60 s (n={sn['n']}): {100 * sn['reduction']:+.1f}% "
              f"(largest single-probe share of the smartlex-certified difference {sn['dominance']['top_diff_share']:.0%}, "
              f"#{sn['dominance']['top_diff_probe']})")
    s += (f". L1 (n={l1.get('n', 0)}): smartlex/certified {l1.get('ratio', float('nan')):.2f}x -> criterion 2 (>= 5x): "
          f"**{'MET' if l1.get('ratio', 0) >= 5 else 'NOT MET'}**.")
    return s


def main(cdir, out_prefix, dtag, ptag, probes_path, cat_path):
    probes = [json.loads(line) for line in open(probes_path)]
    cat = json.load(open(cat_path))
    S, bars = {"duck_tag": dtag, "pg_tag": ptag}, []
    print(f"# E3 cost analysis (cost_analyze.py): preview + count model, DuckDB {dtag}, PostgreSQL {ptag}; pilot tool on v3")
    print("\nScales x10 / x100 / x30 replicate SF1 data (offset copies): a stress test, not a representative workload.")
    print("\n## A. Preview + count model: observation = first 20 rows under the policy's order + exact row count\n")
    for eng, pat, scales, big in (("DuckDB", f"duck_pcnat_{dtag}_*.jsonl", ["sf1", "x10", "xmax"], "xmax"),
                                  ("PostgreSQL", f"pg_pcnat_{ptag}_*.jsonl", ["sf1", "x10"], "x10")):
        recs = load(f"{cdir}/{pat}")
        if not recs:
            continue
        print("Records:", dict(Counter(r.get("probes") for r in recs)))
        if eng == "PostgreSQL":
            agree = Counter((r.get("duckdb_verdict"), r["verdict"]) for r in recs if r["scale"] == "sf1" and "res" in r)
            print("PostgreSQL-dialect vs DuckDB (v6) verdicts at sf1:", dict(sorted(agree.items(), key=str)))
            S["pg_verdict_agreement"] = {f"{a}->{b}": c for (a, b), c in agree.items()}
        es_tot, rows = engine_block(f"{eng}, total = preview + count", recs, scales, big, "tot", True, dtag if eng == "DuckDB" else ptag)
        if rows:
            es_tot["tie_breakdown"] = tie_breakdown(rows, probes, cat, f"{eng} {big}, total", "tot", pg=eng == "PostgreSQL")
            es_tot["attribution"] = (duck_profile(rows, f"preview queries at {big}") if eng == "DuckDB"
                                     else pg_explain(rows, f"preview queries at {big}"))
        es_pre, _ = engine_block(f"{eng}, preview only (secondary view)", recs, scales, big, "t", False, "")
        S[eng] = {"total": es_tot, "preview": es_pre}
        bars += [bar_line(f"{eng}, total = preview + count", es_tot, big), bar_line(f"{eng}, preview only", es_pre, big)]
    for name, pat, scales in (("DuckDB", f"duck_pcctl_{dtag}.jsonl", ["sf1", "x10", "xmax"]),
                              ("PostgreSQL", f"pg_pcctl_{ptag}_*.jsonl", ["sf1", "x10"])):
        recs = load(f"{cdir}/{pat}")
        if recs:
            S[f"controlled_{name}"] = controlled(recs, f"{name} (DuckDB xmax = x30 codebase_community, x100 card_games)", scales)
    print("\n## B. Tool as implemented in the pilot (each policy's SQL fetched up to 100,000 rows; cert file v3)\n")
    for eng, pat, scales, big in (("DuckDB", "duck_nat_*.jsonl", ["sf1", "x10", "xmax"], "xmax"),
                                  ("PostgreSQL", "pg_nat_*.jsonl", ["sf1", "x10"], "x10")):
        recs = load(f"{cdir}/{pat}")
        if recs:
            es, _ = engine_block(f"{eng}, pilot tool (capped fetch)", recs, scales, big, "t", False, "v3")
            S[f"pilot_{eng}"] = es
            bars.append(bar_line(f"{eng}, pilot tool (capped fetch, v3)", es, big))
    print("\n## Predeclared materiality bar (primary: A total, main set; secondary: A preview; B for reference)\n")
    print("\n".join(bars))
    json.dump(S, open(out_prefix + ".json", "w"), indent=1, default=str)
    with open(out_prefix + "_per_probe.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["engine", "tag", "scale", "probe", "db", "class", "verdict", "duckdb_verdict", "main_set",
                    "preview_raw", "preview_smartlex", "preview_certified", "count", "total_raw", "total_smartlex",
                    "total_certified"])
        w.writerows(CSV)


if __name__ == "__main__":
    main(*sys.argv[1:7])
