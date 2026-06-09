"""Computed spec criteria -- self-validation from runtime artifacts."""


def spec_criterion(name, value, threshold=True, warn_only=False):
    """
    Build a spec criterion result dict.
    F9 FIX: all criteria computed from runtime artifacts, not hardcoded.
    """
    if isinstance(threshold, bool):
        status = "pass" if value == threshold else ("warning" if warn_only else "fail")
    else:
        status = "pass" if value >= threshold else ("warning" if warn_only else "fail")
    return {"criterion": name, "status": status, "computed_value": value, "threshold": str(threshold)}


def compute_all_criteria(context):
    """
    Compute all spec criteria from pipeline artifacts.

    Args:
        context: dict with keys:
            - raw_research: dict of research topics
            - taste_map: dict with rewards/punishes
            - scorer_hypotheses_r0: list
            - count_valid_r0: int
            - invalid_pairs_r0: list
            - invalid_pairs_r1: list
            - pair_suite_r0: dict with test list
            - pareto_r0: list
            - failure_packet_r0: dict
            - scorer_hypotheses_r1: list
            - valid_adv: list
            - trap_dist: dict (R0 pair types)
            - trap_dist_r1: dict (R1 pair types)
            - pair_suite_r1: dict with test list
            - pareto_r1: list
            - candidate_ensemble: list
            - selected_candidate: dict or None
            - scored_candidates: list
            - c002: dict (C002 scored candidate)
            - failure_packet_r1: dict
            - config: dict
    """
    cfg = context["config"]
    n_init_scorers = cfg.get("n_init_scorers", 8)
    n_repair_scorers = cfg.get("n_repair_scorers", 6)
    n_repair_pairs = cfg.get("n_repair_pairs", 12)
    min_init_heldout = cfg.get("min_init_heldout", 8)
    min_r1_heldout = cfg.get("min_r1_heldout", 15)

    pair_policy_invalid = len(context["invalid_pairs_r0"]) + len(context["invalid_pairs_r1"])
    final_heldout_count = len(context["pair_suite_r1"]["test"])
    pareto_nonempty_r1 = len(context["pareto_r1"]) > 0
    scored_candidates = context["scored_candidates"]
    c002 = context["c002"]
    fp_r1 = context["failure_packet_r1"]

    trap_dist = context["trap_dist"]
    trap_dist_r1 = context["trap_dist_r1"]

    computed_criteria = [
        spec_criterion("taste_research_present", len(context["raw_research"]), 3),
        spec_criterion("taste_map_rewards_present", len(context["taste_map"]["rewards"]), 3),
        spec_criterion("taste_map_punishes_present", len(context["taste_map"]["punishes"]), 1),
        spec_criterion("scorer_hypotheses_r0", len(context["scorer_hypotheses_r0"]), n_init_scorers),
        spec_criterion("scorer_code_valid_r0", context["count_valid_r0"], 2),
        spec_criterion("pair_policy_violations", pair_policy_invalid, 0),
        spec_criterion("initial_heldout_count", len(context["pair_suite_r0"]["test"]), min_init_heldout),
        spec_criterion("pareto_r0_nonempty", len(context["pareto_r0"]) > 0, True),
        spec_criterion("failure_packet_has_instructions",
                       len(context["failure_packet_r0"]["mutation_instructions"]) > 0, True),
        spec_criterion("repair_hypotheses_generated", len(context["scorer_hypotheses_r1"]), n_repair_scorers),
        spec_criterion("adversarial_pairs_generated", len(context["valid_adv"]), n_repair_pairs),
        spec_criterion("fake_mechanism_pairs",
                       trap_dist_r1.get("fake_mechanism", 0) + trap_dist.get("fake_mechanism", 0), 3),
        spec_criterion("heldout_grew",
                       final_heldout_count > len(context["pair_suite_r0"]["test"]), True),
        spec_criterion("final_heldout_count", final_heldout_count, min_r1_heldout),
        spec_criterion("pareto_r1_nonempty", pareto_nonempty_r1, True),
        spec_criterion("eligible_ensemble_exists", len(context["candidate_ensemble"]) > 0, True),
        spec_criterion("candidate_selected", context["selected_candidate"] is not None, True),
        spec_criterion("hype_baseline_zeroed",
                       scored_candidates[-1]["ensemble_score"] < 0.05 if scored_candidates else False, True),
        spec_criterion("c002_not_zeroed", c002["ensemble_score"] > 0.05, True),
        spec_criterion("mutation_instructions_not_all_repeated",
                       len(fp_r1.get("applied_from_prior_round", [])) < len(fp_r1["mutation_instructions"]),
                       True, warn_only=True),
    ]

    return computed_criteria
