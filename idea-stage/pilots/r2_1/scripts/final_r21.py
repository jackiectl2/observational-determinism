# Pilot R2-1: assemble r2_1_results.json and evaluate both predeclared decision rules.
import json
import os
import sys

R = os.environ["PROJECT_ROOT"] + "/runs/pilot_r2_1"


def main():
    div = json.load(open(f"{R}/div_summary.json"))
    ag2 = json.load(open(f"{R}/agent_summary_v2.json"))
    ag1 = json.load(open(f"{R}/agent_summary_v1.json"))
    run1_turn1 = json.load(open(f"{R}/run1_turn1_nondeterminism.json"))
    anyp = div["any_perturbation"]
    perm = ag2["pairs"]["raw: original vs permuted order (1 thread)"]
    thr = ag2["pairs"]["raw: 1 vs 8 threads (original order)"]
    rep = ag2["pairs"]["raw: 8 threads, repeated"]
    operm = ag2["pairs"]["OBSERVE: original vs permuted order (1 thread)"]
    othr = ag2["pairs"]["OBSERVE: 1 vs 8 threads (original order)"]
    ov = div["overhead"]
    det = div.get("determinism_v3_v4", {})

    def traj_removed(raw, obs):
        a = raw["all"]["attributable"]
        return 1 - obs["all"]["traj_changed"] / a if a else None

    impl = {}
    for v in ("v2", "v3", "v4"):
        s1, s10 = ov.get("timing_run_sf1", {}).get(v), ov.get("timing_run_sf10", {}).get(v)
        if v == "v2":
            removal = anyp["canon_removed_share_probes"]
        else:
            d = det.get(v, {})
            removal = (1 - d["diverging_frac_probes"] / anyp["raw_text_frac_probes"]) if d else None
        impl[v] = {"obs_divergence_removed": removal, "overhead_sf1": s1, "overhead_sf10": s10,
                   "median_lt_10pct_sf1": s1 is not None and s1["median_probes"] < 0.10,
                   "p95_lt_25pct_sf1": s1 is not None and s1["p95_probes"] < 0.25,
                   "median_lt_10pct_sf10": s10 is not None and s10["median_probes"] < 0.10,
                   "p95_lt_25pct_sf10": s10 is not None and s10["p95_probes"] < 0.25}
    strict = {
        "1_raw_obs_differ_ge_15pct_eligible_probes": {"value": anyp["raw_text_frac_probes"], "pass": anyp["raw_text_frac_probes"] >= 0.15},
        "2_next_sql_action_changes_ge_10pct_tasks": {"value_permuted": perm["all"]["next_action_changed"],
                                                     "value_threads": thr["all"]["next_action_changed"],
                                                     "value_repeat": rep["all"]["next_action_changed"],
                                                     "pass": perm["all"]["next_action_changed"] >= 0.10},
        "3_final_sql_or_answer_changes_ge_5pct_tasks": {"value_permuted": perm["all"]["final_sql_or_answer_changed"],
                                                        "value_threads": thr["all"]["final_sql_or_answer_changed"],
                                                        "value_repeat": rep["all"]["final_sql_or_answer_changed"],
                                                        "final_answer_only_permuted": perm["all"]["final_result_changed"],
                                                        "pass": perm["all"]["final_sql_or_answer_changed"] >= 0.05},
        "4a_canonical_observe_removes_ge_95pct_obs_divergence": {"value": anyp["canon_removed_share_probes"],
                                                                 "pass": anyp["canon_removed_share_probes"] >= 0.95},
        "4b_removes_ge_80pct_attributable_trajectory_divergence": {"value_permuted": traj_removed(perm, operm),
                                                                   "value_threads": traj_removed(thr, othr),
                                                                   "pass": (traj_removed(perm, operm) or 0) >= 0.80},
        "5_no_semantic_contract_violations": {"violations": div["contract"]["violations"],
                                              "executions_checked": div["contract"]["executions_checked"],
                                              "pass": not any(div["contract"]["violations"].values())},
        "6_overhead_median_lt_10pct_p95_lt_25pct": {"by_implementation": impl,
                                                    "pass_any_implementation_sf1": any(x["median_lt_10pct_sf1"] and x["p95_lt_25pct_sf1"] for x in impl.values()),
                                                    "pass_v2_canonical_sf1": impl["v2"]["median_lt_10pct_sf1"] and impl["v2"]["p95_lt_25pct_sf1"]},
    }
    strict_go = all(v["pass"] for k, v in strict.items() if k != "6_overhead_median_lt_10pct_p95_lt_25pct") and \
        strict["6_overhead_median_lt_10pct_p95_lt_25pct"]["pass_any_implementation_sf1"]
    earlier = {
        "raw_obs_differ_ge_15pct": anyp["raw_text_frac_probes"] >= 0.15,
        "alter_downstream_sql_ge_10pct_tasks": perm["all"]["attributable"] >= 0.10,
        "observe_removes_ge_90pct": anyp["canon_removed_share_probes"] >= 0.90,
        "overhead_le_20pct_v2_sum_sf1": ov.get("timing_run_sf1", {}).get("v2", {}).get("sum_ratio", 9) <= 0.20,
        "overhead_le_20pct_any_impl_median_sf1": any((ov.get("timing_run_sf1", {}).get(v, {}).get("median_probes", 9) <= 0.20) for v in ("v2", "v3", "v4")),
        "kill_obs_lt_5pct": anyp["raw_text_frac_probes"] < 0.05,
        "kill_traj_lt_3pct": perm["all"]["traj_changed"] < 0.03,
    }
    out = {"strict_rule": strict, "strict_rule_GO": strict_go, "earlier_rule": earlier,
           "divergence_summary": div, "agent_run2_primary": ag2, "agent_run1_llm_nondeterminism": ag1,
           "run1_turn1_identical_prompt_nondeterminism": run1_turn1,
           "compute": json.load(open(f"{R}/compute.json"))}
    json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
    print(json.dumps({"strict": {k: {kk: vv for kk, vv in v.items() if kk != "by_implementation"} for k, v in strict.items()},
                      "strict_GO": strict_go, "earlier": earlier}, indent=1, default=str))
    for v, x in impl.items():
        print(v, "removal", x["obs_divergence_removed"], "sf1", {k: round(vv, 3) for k, vv in (x["overhead_sf1"] or {}).items()},
              "sf10", {k: round(vv, 3) for k, vv in (x["overhead_sf10"] or {}).items()})


if __name__ == "__main__":
    main()
