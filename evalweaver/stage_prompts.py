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
