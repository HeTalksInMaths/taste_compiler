"""Prompt template builders for Stages 1–4 reasoning pipeline."""

import json


def build_stage_1_prompt(target_variable: str) -> tuple[str, str]:
    """Build Stage 1 prompt: Causal Research Search."""
    system = (
        "You are a research assistant specializing in causal evidence synthesis. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )
    user = f"""Research question: What factors causally affect whether text is perceived as {target_variable}?

Search across psychology, communication, rhetoric, linguistics, behavioral science, marketing science, and related fields.

Return source-backed claims about:
1. variables that increase {target_variable}
2. variables that decrease {target_variable}
3. variables that mediate or moderate {target_variable}
4. mechanisms explaining why those variables matter
5. disagreements, tensions, or boundary conditions in the research

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "causal_research": [
    {{
      "source_id": "SRC_001",
      "title": "...",
      "url": "...",
      "claim": "...",
      "causal_variable": "...",
      "effect_direction": "increases | decreases | mediates | moderates",
      "mechanism": "...",
      "evidence_strength": "high | medium | low"
    }}
  ],
  "research_tensions": [
    {{
      "claim": "...",
      "variables": ["...", "..."]
    }}
  ]
}}"""
    return (system, user)


def build_stage_2_prompt(target_variable: str, stage1_research: list) -> tuple[str, str]:
    """Build Stage 2 prompt: Causal Graph Generation."""
    system = (
        "You are building a causal graph from research evidence. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )
    research_json = json.dumps(stage1_research, indent=2)
    user = f"""You are building a causal graph for the target variable: {target_variable}

Use only the causal research provided below.

Your task:
1. identify the main causal nodes (consolidate into 8–12 distinct nodes maximum)
2. define each node clearly
3. assign each node a role: increases, decreases, mediates, or moderates
4. explain the mechanism for each node
5. add edges where one causal node affects another
6. preserve important tensions or tradeoffs
7. write a concise summary theory

IMPORTANT: Consolidate related variables into single nodes. Aim for 8–12 nodes that capture the major causal dimensions, not 20+ fine-grained variables.

Causal research:
{research_json}

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "causal_nodes": [
    {{
      "node_id": "credibility",
      "label": "Credibility",
      "role": "increases",
      "definition": "...",
      "mechanism": "...",
      "evidence": ["SRC_001"]
    }}
  ],
  "causal_edges": [
    {{
      "from": "specificity",
      "to": "credibility",
      "relationship": "supports",
      "claim": "Specific details can increase perceived credibility."
    }}
  ],
  "causal_tensions": [
    {{
      "claim": "...",
      "nodes": ["specificity", "credibility"]
    }}
  ],
  "summary_theory": "..."
}}"""
    return (system, user)


def build_stage_3_prompt(target_variable: str, causal_nodes: list) -> tuple[str, str]:
    """Build Stage 3 prompt: Measurement Research Search."""
    system = (
        "You are a measurement research specialist mapping causal variables to observable text signals. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )
    nodes_summary = json.dumps([{"node_id": n["node_id"], "label": n["label"], "definition": n.get("definition", "")} for n in causal_nodes], indent=2)
    user = f"""Research question: How can NLP, computational linguistics, discourse analysis, or text analysis measure the following variables in text?

Target variable: {target_variable}
Causal nodes: {nodes_summary}

Return source-backed measurement ideas for each causal node.
IMPORTANT: Provide at least 2 different measurement approaches for most nodes.

For each measurement idea, include:
1. the causal node being measured
2. the observable text signal
3. concrete linguistic indicators
4. implementation ideas that could be converted into code

Focus on measurable text features.

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "measurement_research": [
    {{
      "source_id": "MSRC_001",
      "causal_node": "credibility",
      "title": "...",
      "url": "...",
      "measurement_claim": "...",
      "text_features": ["evidence markers", "hedging", "certainty markers"],
      "implementation_ideas": [
        "count evidence phrases",
        "count absolute certainty terms",
        "measure hedge density"
      ]
    }}
  ]
}}"""
    return (system, user)


def build_stage_4_prompt(target_variable: str, causal_graph: dict, measurement_research: list) -> tuple[str, str]:
    """Build Stage 4 prompt: Scorer Hypothesis and Function Generation."""
    system = (
        "You are generating scoring hypotheses and Python scorer functions. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )
    graph_json = json.dumps(causal_graph, indent=2)
    measurement_json = json.dumps(measurement_research, indent=2)
    user = f"""You are generating scoring hypotheses and Python scorer functions for the target variable: {target_variable}

You are given:
1. a causal graph for {target_variable}
2. measurement research about how the causal nodes can be detected in text

Create multiple distinct scorer hypotheses and functions (at least 5).

For each scorer:
1. Choose a causal hypothesis (use causal nodes, edges, tensions)
2. Explain the functional form (additive? multiplicative? gated? penalty? tension_balance?)
3. Choose measurable text features from the measurement research
4. Write executable Python code

CRITICAL REQUIREMENTS for the code:
- The function must have this exact shape: def scorer(text, anchor, params): ... return score
- The score must be between 0.0 and 1.0. Higher = more of the target variable.
- The scorer MUST analyze the actual text content (word counts, pattern matching, regex, etc.)
- The scorer MUST produce DIFFERENT scores for different texts. Do NOT use hardcoded constants.
- Use text.lower(), text.split(), re.findall(), len() etc. to extract real features from the text.
- Available imports in the execution namespace: re, math, collections, string, statistics, unicodedata
- IMPORTANT: Your scorer will be tested on these 4 texts and MUST give different scores for at least 2 of them:
  1. "This works because it gives teams a concrete way to test ideas before committing."
  2. "This is the best and most revolutionary solution ever made."
  3. "The tool helps users compare options, see tradeoffs, and choose a next step."
  4. "Maybe it helps in some cases, but the limits are unclear."
- Use features that vary across short texts: word choice, superlatives, hedging, causal connectives, specificity of nouns/verbs.

Causal graph:
{graph_json}

Measurement research:
{measurement_json}

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "scorers": [
    {{
      "scorer_id": "S0",
      "hypothesis": "...",
      "causal_nodes_used": ["causal_explanation", "credibility"],
      "causal_edges_used": [{{"from": "causal_explanation", "to": "credibility"}}],
      "causal_tensions_used": [],
      "measurement_ideas_used": ["causal connective density", "evidence marker density"],
      "functional_form": "interaction",
      "functional_form_rationale": "...",
      "expected_failure_mode": "...",
      "code": "def scorer(text, anchor, params):\\n    ...\\n    return score"
    }}
  ]
}}"""
    return (system, user)


def build_stage_5_prompt(
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    scorers: list,
    source_policy: dict,
) -> tuple[str, str]:
    """Build Stage 5 prompt: Evaluation Pair Generation."""
    system = (
        "You are generating evaluation text pairs that test slightly more vs slightly less "
        "of a target variable. Each pair isolates a clean local contrast. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Compact representations to save tokens
    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "role": n.get("role", ""), "mechanism": n.get("mechanism", "")[:80]}
         for n in causal_graph.get("causal_nodes", [])],
        indent=None,
    )
    edges_summary = json.dumps(
        [{"from": e["from"], "to": e["to"]} for e in causal_graph.get("causal_edges", [])],
        indent=None,
    )
    measurement_summary = json.dumps(
        [{"causal_node": m["causal_node"], "text_features": m["text_features"]}
         for m in measurement_research],
        indent=None,
    )
    scorer_summary = json.dumps(
        [{"scorer_id": s.get("scorer_id", ""), "hypothesis": s.get("hypothesis", "")[:60],
          "causal_nodes_used": s.get("causal_nodes_used", [])}
         for s in scorers],
        indent=None,
    )
    policy_json = json.dumps(source_policy, indent=None)

    user = f"""Generate positive/negative text pairs for the target variable: {target_variable}

Each pair must test SLIGHTLY MORE vs SLIGHTLY LESS of {target_variable}.
Pairs should isolate clean local contrasts — NOT adversarial traps.
Each pair tests specific causal nodes from the graph below.

Causal nodes: {nodes_summary}
Causal edges: {edges_summary}
Measurement research: {measurement_summary}
Existing scorers (for context): {scorer_summary}
Source policy: {policy_json}

REQUIREMENTS:
1. Generate at least 10 pairs (more is better, aim for 12-15)
2. Each pair has a shared anchor (context), a positive text (MORE {target_variable}), and a negative text (LESS {target_variable})
3. Control for length — positive and negative variants should be similar word counts
4. Each pair should test 1-2 causal nodes (not 3+) for clean isolation
5. Include a label_contract explaining why positive > negative
6. Reference specific causal nodes and measurement ideas
7. Vary the channel/topic/audience across pairs for diversity
8. Do NOT create adversarial or trick pairs — focus on genuine, subtle contrasts

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "pairs": [
    {{
      "pair_id": "P001",
      "source_id": "...",
      "source_trace": "...",
      "anchor": "shared context or topic for both variants",
      "positive": "text with slightly MORE {target_variable}",
      "negative": "text with slightly LESS {target_variable}",
      "split": "train",
      "target_delta": "what differs between positive and negative",
      "controlled_variables": ["length", "topic", "tone"],
      "causal_nodes_tested": ["node_id_1"],
      "causal_edges_tested": [{{"from": "node1", "to": "node2"}}],
      "measurement_ideas_tested": ["idea1"],
      "causal_tensions_tested": [],
      "label_contract": "positive scores higher because...",
      "source_policy": "compliant",
      "policy_violations": []
    }}
  ]
}}"""
    return (system, user)


def build_stage_7_prompt(
    target_variable: str,
    scorer_summaries: list,
    train_eval_rows: list,
    pareto_frontier: list,
    train_pairs: list,
    causal_graph: dict,
    measurement_research: list,
    heldout_aggregate: dict,
) -> tuple[str, str]:
    """Build Stage 7 prompt: Failure Packet Generation.

    CRITICAL: This prompt must NOT include raw heldout pair text.
    Only train-split data and heldout aggregates (accuracy/gap per scorer) are included.
    """
    system = (
        "You are diagnosing scorer failures and producing actionable repair instructions. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Compact representations
    summaries_json = json.dumps(scorer_summaries, indent=None)
    pareto_json = json.dumps(pareto_frontier, indent=None)
    heldout_agg_json = json.dumps(heldout_aggregate, indent=None)

    # Train eval rows: only include failures and low-margin cases to save tokens
    failed_rows = [r for r in train_eval_rows if not r.get("correct", True)]
    low_margin_rows = [r for r in train_eval_rows if r.get("correct") and 0 < r.get("gap", 1) < 0.1]
    train_failures_json = json.dumps(failed_rows, indent=None)
    train_low_margin_json = json.dumps(low_margin_rows, indent=None)

    # Train pairs with text for context
    train_pairs_json = json.dumps(
        [{"pair_id": p.get("pair_id", ""), "anchor": p.get("anchor", ""),
          "positive": p.get("positive", ""), "negative": p.get("negative", ""),
          "causal_nodes_tested": p.get("causal_nodes_tested", []),
          "label_contract": p.get("label_contract", "")}
         for p in train_pairs],
        indent=None,
    )

    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "role": n.get("role", ""), "mechanism": n.get("mechanism", "")[:80]}
         for n in causal_graph.get("causal_nodes", [])],
        indent=None,
    )
    measurement_summary = json.dumps(
        [{"causal_node": m["causal_node"], "text_features": m["text_features"],
          "implementation_ideas": m["implementation_ideas"]}
         for m in measurement_research],
        indent=None,
    )

    user = f"""Diagnose scorer failures for target variable: {target_variable}

You are given scorer performance data from the TRAIN split only, plus aggregate heldout metrics.
Your job: identify WHY scorers fail on specific pairs and produce actionable repair instructions.

IMPORTANT: You are seeing ONLY train-split pair text and heldout AGGREGATE metrics (no raw heldout text).

Scorer summaries: {summaries_json}
Pareto frontier scorers: {pareto_json}
Heldout aggregate metrics (accuracy and mean_gap per scorer): {heldout_agg_json}

Train-split failures (scorer got wrong answer): {train_failures_json}
Train-split low-margin correct (gap < 0.1): {train_low_margin_json}
Train pairs (text for context): {train_pairs_json}

Causal nodes: {nodes_summary}
Measurement research: {measurement_summary}

REQUIREMENTS:
1. Identify the top scorers (best heldout performance from aggregates)
2. List visible (train) failures and low-margin pairs per scorer
3. Identify failure PATTERNS — groups of failures sharing a common cause
4. For each pattern: which causal nodes are implicated? What reasoning error do the scorers make?
5. Produce mutation instructions: concrete, actionable changes to scorer logic
6. Each instruction must contain action verbs (add, remove, replace, combine, split, increase, decrease, weight, gate, normalize, multiply)
7. Focus on functional changes that would fix the identified patterns
8. NEVER include raw heldout pair text in your response

Return valid JSON with this exact schema:
{{
  "failure_packet": {{
    "top_scorers": [
      {{"scorer_id": "S0", "hypothesis": "...", "heldout_accuracy": 0.8, "heldout_mean_gap": 0.15}}
    ],
    "failed_visible_pairs": [
      {{"scorer_id": "S0", "pair_id": "P001", "positive_score": 0.4, "negative_score": 0.6, "gap": -0.2}}
    ],
    "low_margin_visible_pairs": [
      {{"scorer_id": "S0", "pair_id": "P002", "gap": 0.02}}
    ]
  }},
  "heldout_aggregate_only": {{
    "heldout_accuracy_by_scorer": {{"S0": 0.8, "S1": 0.6}},
    "heldout_mean_gap_by_scorer": {{"S0": 0.15, "S1": 0.05}}
  }},
  "failure_patterns": [
    {{
      "pattern_id": "FP001",
      "scorer_ids": ["S0", "S1"],
      "visible_pair_ids": ["P001", "P003"],
      "causal_nodes_implicated": ["credibility", "specificity"],
      "reasoning_error": "scorers weight X but miss Y",
      "severity": "high"
    }}
  ],
  "mutation_instructions": [
    {{
      "instruction_id": "MI001",
      "targets_failure_patterns": ["FP001"],
      "instruction": "Add weight for Z feature and normalize against...",
      "expected_metric_movement": "heldout_accuracy +0.1"
    }}
  ],
  "pair_suite_coverage_notes": "summary of which causal nodes are well/poorly covered by pairs"
}}"""
    return (system, user)


def build_stage_8_prompt(
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    prior_scorers: list,
    failure_packet: dict,
) -> tuple[str, str]:
    """Build Stage 8 prompt: Repair Scorer Generation."""
    system = (
        "You are generating repaired scorer functions that address specific failure patterns. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Compact representations
    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "role": n.get("role", ""), "mechanism": n.get("mechanism", "")[:80]}
         for n in causal_graph.get("causal_nodes", [])],
        indent=None,
    )
    edges_summary = json.dumps(
        [{"from": e["from"], "to": e["to"]} for e in causal_graph.get("causal_edges", [])],
        indent=None,
    )
    measurement_summary = json.dumps(
        [{"causal_node": m["causal_node"], "text_features": m["text_features"],
          "implementation_ideas": m["implementation_ideas"]}
         for m in measurement_research],
        indent=None,
    )

    # Prior scorers: include id, hypothesis, form, and code for context
    prior_scorers_json = json.dumps(
        [{"scorer_id": s.get("scorer_id", ""), "hypothesis": s.get("hypothesis", "")[:80],
          "functional_form": s.get("functional_form", ""),
          "causal_nodes_used": s.get("causal_nodes_used", []),
          "code": s.get("code", "")}
         for s in prior_scorers],
        indent=None,
    )

    # Failure packet: patterns and mutation instructions
    failure_patterns_json = json.dumps(
        failure_packet.get("failure_patterns", []), indent=None
    )
    mutation_instructions_json = json.dumps(
        failure_packet.get("mutation_instructions", []), indent=None
    )

    user = f"""Generate repaired scorer functions for target variable: {target_variable}

Each repair scorer must address specific failure patterns identified in the failure analysis.
Use causal nodes and measurement ideas to construct improved scoring logic.

Causal nodes: {nodes_summary}
Causal edges: {edges_summary}
Measurement research: {measurement_summary}

Prior scorers (parents to improve upon): {prior_scorers_json}

Failure patterns identified: {failure_patterns_json}
Mutation instructions: {mutation_instructions_json}

REQUIREMENTS:
1. Generate at least 5 repair scorers (aim for 5-8)
2. Each repair scorer MUST target at least one failure pattern from above
3. Each repair scorer MUST have executable Python code with signature: def scorer(text, anchor, params): ... return score
4. Score must be 0.0 to 1.0 (higher = more {target_variable})
5. The scorer MUST analyze actual text content (re.findall, word counts, pattern matching)
6. The scorer MUST produce DIFFERENT scores for different texts
7. Available imports: re, math, collections, string, statistics, unicodedata
8. Each repair scorer should use a DIFFERENT functional form or approach than its parent
9. Include a repair_strategy explaining how this scorer addresses the failure pattern
10. Reference specific causal nodes and measurement ideas in your approach

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "repair_scorers": [
    {{
      "scorer_id": "RS0",
      "lineage": "repair_round_1",
      "parent_scorer_ids": ["S0"],
      "targets_failure_patterns": ["FP001"],
      "hypothesis": "...",
      "causal_nodes_used": ["credibility", "specificity"],
      "measurement_ideas_used": ["evidence marker density", "concrete noun ratio"],
      "functional_form": "interaction",
      "repair_strategy": "addresses FP001 by adding...",
      "expected_failure_mode": "...",
      "code_feature_map": {{"feature1": "implementation note", "feature2": "implementation note"}},
      "code": "def scorer(text, anchor, params):\\n    ...\\n    return score"
    }}
  ]
}}"""
    return (system, user)
