# EvalWeaver Stages 1–4 Reasoning Spec

## Managed Input

```json
{
  "target_variable": "trustworthy",
  "raw_text": "Most professionals now need to learn AI tools because the work around them is changing faster than traditional training can keep up. The point is not to replace judgment, but to learn how to use AI to search, draft, test, debug, and explain work more effectively while still checking the result."
}
```

Stages 1–4 operate only on `target_variable`.

## Stage 1 — Causal Research Search

### Objective
Build a source-backed causal evidence base for the target variable.
The output should capture: causal variable → effect direction → mechanism → evidence.
This stage should discover what causes more or less of the target variable.

### Prompt
```
Research question: What factors causally affect whether text is perceived as {target_variable}?

Search across psychology, communication, rhetoric, linguistics, behavioral science, marketing science, and related fields.

Return source-backed claims about:
1. variables that increase {target_variable}
2. variables that decrease {target_variable}
3. variables that mediate or moderate {target_variable}
4. mechanisms explaining why those variables matter
5. disagreements, tensions, or boundary conditions in the research
```

### Output Schema
```json
{
  "target_variable": "trustworthy",
  "causal_research": [
    {
      "source_id": "SRC_001",
      "title": "...",
      "url": "...",
      "claim": "...",
      "causal_variable": "...",
      "effect_direction": "increases | decreases | mediates | moderates",
      "mechanism": "...",
      "evidence_strength": "high | medium | low"
    }
  ],
  "research_tensions": [
    {
      "claim": "...",
      "variables": ["...", "..."]
    }
  ]
}
```

### Eval

**North Star:** A strong Stage 1 output is a causal evidence base, not generic advice.
- Good: "Credibility increases persuasiveness because readers assign more weight to claims they trust."
- Bad: "Persuasive text should be clear, engaging, and effective."

### Deterministic Eval Signals
```json
{
  "num_research_items": 0,
  "num_unique_causal_variables": 0,
  "mechanism_completeness_rate": 0.0,
  "effect_direction_coverage": {"increases": 0, "decreases": 0, "mediates": 0, "moderates": 0},
  "source_trace_rate": 0.0,
  "causal_specificity_score": 0.0,
  "generic_advice_penalty": 0.0,
  "tension_count": 0,
  "pass": false
}
```

### Scoring Guidance
- **mechanism_completeness_rate**: Fraction of items with claim, causal_variable, effect_direction, mechanism, and source_id.
- **causal_specificity_score**: Reward claims with mechanistic language: because, leads to, increases, decreases, mediates, moderates, causes, drives, reduces, through, by making, as a result
- **generic_advice_penalty**: Penalize vague advice words when no mechanism is present: clear, good, engaging, effective, strong, better, important, high quality
- **tension_count**: Count tensions that name at least two variables and explain a tradeoff.

### Pass Criteria
```json
{
  "num_research_items_min": 8,
  "num_unique_causal_variables_min": 5,
  "mechanism_completeness_rate_min": 0.75,
  "source_trace_rate_min": 0.9,
  "causal_specificity_score_min": 0.6,
  "tension_count_min": 1,
  "generic_advice_penalty_max": 0.25
}
```

---

## Stage 2 — Causal Graph Generation

### Objective
Convert Stage 1 research into a compact causal graph for the target variable.
The output should capture: nodes → roles → mechanisms → edges → tensions.
This stage defines the theory of the target variable.

### Prompt
```
You are building a causal graph for the target variable: {target_variable}

Use only the causal research provided.

Your task:
1. identify the main causal nodes
2. define each node clearly
3. assign each node a role: increases, decreases, mediates, or moderates
4. explain the mechanism for each node
5. add edges where one causal node affects another
6. preserve important tensions or tradeoffs
7. write a concise summary theory

Return valid JSON.
```

### Output Schema
```json
{
  "target_variable": "trustworthy",
  "causal_nodes": [
    {
      "node_id": "credibility",
      "label": "Credibility",
      "role": "increases",
      "definition": "...",
      "mechanism": "...",
      "evidence": ["SRC_001"]
    }
  ],
  "causal_edges": [
    {
      "from": "specificity",
      "to": "credibility",
      "relationship": "supports",
      "claim": "Specific details can increase perceived credibility."
    }
  ],
  "causal_tensions": [
    {
      "claim": "Specificity improves credibility when grounded, but damages credibility when unsupported.",
      "nodes": ["specificity", "credibility"]
    }
  ],
  "summary_theory": "..."
}
```

### Eval

**North Star:** A strong Stage 2 output is a causal graph, not a flat list.
- Good: specificity → credibility → persuasiveness; hype → reactance → lower persuasiveness
- Bad: credibility, clarity, emotion, specificity, relevance

### Deterministic Eval Signals
```json
{
  "num_nodes": 0,
  "num_edges": 0,
  "node_mechanism_rate": 0.0,
  "node_evidence_rate": 0.0,
  "edge_validity_rate": 0.0,
  "edge_explanation_rate": 0.0,
  "graph_connectedness_score": 0.0,
  "role_diversity_score": 0,
  "tension_count": 0,
  "summary_uses_graph_terms": false,
  "pass": false
}
```

### Pass Criteria
```json
{
  "num_nodes_min": 5,
  "num_edges_min": 4,
  "node_mechanism_rate_min": 0.85,
  "node_evidence_rate_min": 0.8,
  "edge_validity_rate_min": 1.0,
  "edge_explanation_rate_min": 0.9,
  "graph_connectedness_score_min": 0.6,
  "role_diversity_score_min": 2,
  "tension_count_min": 1
}
```

---

## Stage 3 — Measurement Research Search

### Objective
Map causal nodes to measurable text features.
The output should capture: causal node → observable text signal → implementation idea.
This stage researches how each causal node can be approximated from text.

### Prompt
```
Research question: How can NLP, computational linguistics, discourse analysis, or text analysis measure the following variables in text?

Target variable: {target_variable}
Causal nodes: {causal_nodes}

Return source-backed measurement ideas for each causal node.

For each measurement idea, include:
1. the causal node being measured
2. the observable text signal
3. concrete linguistic indicators
4. implementation ideas that could be converted into code

Focus on measurable text features.
```

### Output Schema
```json
{
  "target_variable": "trustworthy",
  "measurement_research": [
    {
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
    }
  ]
}
```

### Eval

**North Star:** A strong Stage 3 output maps causal theory into measurable text signals.
- Good: credibility → evidence markers, calibrated claims, absence of unsupported certainty → count evidence terms and overclaim terms
- Bad: Use sentiment, readability, and keywords.

### Deterministic Eval Signals
```json
{
  "node_measurement_coverage": 0.0,
  "num_measurement_items": 0,
  "text_feature_specificity_score": 0.0,
  "implementation_actionability_score": 0.0,
  "generic_metric_penalty": 0.0,
  "multi_measurement_rate": 0.0,
  "node_reference_validity_rate": 0.0,
  "pass": false
}
```

### Pass Criteria
```json
{
  "node_measurement_coverage_min": 0.7,
  "num_measurement_items_min": 8,
  "text_feature_specificity_score_min": 0.6,
  "implementation_actionability_score_min": 0.65,
  "generic_metric_penalty_max": 0.3,
  "multi_measurement_rate_min": 0.5,
  "node_reference_validity_rate_min": 1.0
}
```

---

## Stage 4 — Scorer Hypothesis and Function Generation

### Objective
Generate diverse executable scoring theories.
Each scorer should represent: causal hypothesis → functional form → measurable features → executable code.
This stage is successful only if the scorer population contains distinct theories of how to measure the target variable.

### Prompt
```
You are generating scoring hypotheses and Python scorer functions for the target variable: {target_variable}

You are given:
1. a causal graph for {target_variable}
2. measurement research about how the causal nodes can be detected in text

Create multiple distinct scorer hypotheses and functions.

For each scorer:
1. Choose a causal hypothesis (use causal nodes, edges, tensions)
2. Explain the functional form (additive? multiplicative? gated? penalty? tension_balance?)
3. Choose measurable text features from the measurement research
4. Write executable Python code

The function must have this exact shape:
def scorer(text, anchor, params):
    ...
    return score

The score should be numeric. Higher score means the text has more of the target variable.

Return valid JSON.
```

### Output Schema
```json
{
  "target_variable": "trustworthy",
  "scorers": [
    {
      "scorer_id": "S0",
      "hypothesis": "...",
      "causal_nodes_used": ["causal_explanation", "credibility"],
      "causal_edges_used": [{"from": "causal_explanation", "to": "credibility"}],
      "causal_tensions_used": [],
      "measurement_ideas_used": ["causal connective density", "evidence marker density"],
      "functional_form": "interaction",
      "functional_form_rationale": "...",
      "expected_failure_mode": "...",
      "code": "def scorer(text, anchor, params):\n    ...\n    return score"
    }
  ]
}
```

### Eval

**North Star:** A strong Stage 4 output creates genuinely different scoring theories.
- Good: "causal explanation matters only when credibility signals are present"
- Bad: `score = 0.5` or `score = 0.2 * clarity + 0.2 * emotion + 0.2 * credibility` without meaningful measurement logic.

### Deterministic Eval Signals
```json
{
  "num_scorers": 0,
  "hypothesis_completeness_rate": 0.0,
  "causal_node_validity_rate": 0.0,
  "measurement_reference_rate": 0.0,
  "functional_form_diversity": 0,
  "interaction_usage_rate": 0.0,
  "normalization_usage_rate": 0.0,
  "code_exec_rate": 0.0,
  "numeric_return_rate": 0.0,
  "nonconstant_behavior_rate": 0.0,
  "scorer_distinctness_score": 0.0,
  "hypothesis_code_alignment_score": 0.0,
  "pass": false
}
```

### Scoring Guidance
- **hypothesis_completeness_rate**: Fraction of scorers with hypothesis, causal_nodes_used, measurement_ideas_used, functional_form, functional_form_rationale, expected_failure_mode, code
- **causal_node_validity_rate**: Fraction of referenced causal nodes that exist in Stage 2
- **measurement_reference_rate**: Fraction of scorers referencing measurement ideas from Stage 3
- **functional_form_diversity**: Count distinct functional forms: additive, interaction, gated, penalty, tension_balance, causal_path, ratio_or_density, threshold
- **interaction_usage_rate**: Fraction of scorers using interaction-like structures: *, min(, max(, if, penalty, gate, threshold, ratio, density
- **normalization_usage_rate**: Fraction of scorers normalizing by text length, sentence count, clause count, or token count
- **nonconstant_behavior_rate**: Run each scorer on smoke texts and require different outputs across at least two inputs
- **scorer_distinctness_score**: unique tuples of (functional_form, causal_nodes_used, measurement_ideas_used) / num_scorers
- **hypothesis_code_alignment_score**: Approximate overlap between causal_nodes_used + measurement_ideas_used and variable names / keyword lists / feature logic in code

### Smoke Texts for Stage 4 Eval
```json
[
  "This works because it gives teams a concrete way to test ideas before committing.",
  "This is the best and most revolutionary solution ever made.",
  "The tool helps users compare options, see tradeoffs, and choose a next step.",
  "Maybe it helps in some cases, but the limits are unclear."
]
```

### Pass Criteria
```json
{
  "num_scorers_min": 5,
  "hypothesis_completeness_rate_min": 1.0,
  "causal_node_validity_rate_min": 1.0,
  "measurement_reference_rate_min": 0.8,
  "functional_form_diversity_min": 4,
  "interaction_usage_rate_min": 0.4,
  "normalization_usage_rate_min": 0.5,
  "code_exec_rate_min": 1.0,
  "numeric_return_rate_min": 1.0,
  "nonconstant_behavior_rate_min": 0.8,
  "scorer_distinctness_score_min": 0.75,
  "hypothesis_code_alignment_score_min": 0.5
}
```

---

## Implementation Notes

- `--live-canary` flag runs all 4 stages live against Bedrock
- Model: `us.anthropic.claude-sonnet-4-6`
- Scorer code is executed safely via existing `py_run_scorer` (namespace isolation)
- Each stage saves: prompt, raw_response, parsed_json, eval_result, call_meta
- If any stage fails eval criteria → fail loudly, save `failure_points.md`
- Target for first run: `target_variable="trustworthy"`
