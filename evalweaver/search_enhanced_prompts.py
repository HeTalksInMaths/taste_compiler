"""Search-enhanced prompt builders that inject Exa search results as grounding context.

These wrap the base prompt builders from stage_prompts.py, prepending real search
results so the LLM synthesizes from actual sources rather than hallucinating.

Usage:
    from evalweaver.search_enhanced_prompts import build_stage_1_prompt_with_search
    system, user = build_stage_1_prompt_with_search("trustworthy")
"""

import json
from typing import Optional

from evalweaver.artifacts import log


def _safe_search_causal(target_variable: str, num_results: int = 10) -> list[dict]:
    """Run Exa causal research search, return empty list on failure."""
    try:
        from evalweaver.providers.exa_search import search_causal_research
        return search_causal_research(target_variable, num_results=num_results)
    except Exception as e:
        log("search_enhanced", f"Exa causal search failed (falling back to LLM-only): {e}", "warn")
        return []


def _safe_search_measurement(target_variable: str, causal_nodes: list[str], num_results: int = 10) -> list[dict]:
    """Run Exa measurement research search, return empty list on failure."""
    try:
        from evalweaver.providers.exa_search import search_measurement_research
        return search_measurement_research(target_variable, causal_nodes, num_results=num_results)
    except Exception as e:
        log("search_enhanced", f"Exa measurement search failed (falling back to LLM-only): {e}", "warn")
        return []


def _safe_search_social(channel: str, topic: str, audience: str, num_results: int = 15) -> list[dict]:
    """Run Exa social content search, return empty list on failure."""
    try:
        from evalweaver.providers.exa_search import search_social_content
        return search_social_content(channel=channel, topic=topic, audience=audience, num_results=num_results)
    except Exception as e:
        log("search_enhanced", f"Exa social search failed (falling back to LLM-only): {e}", "warn")
        return []


def build_stage_1_prompt_with_search(target_variable: str, num_results: int = 10) -> tuple[str, str]:
    """
    Build Stage 1 prompt with real Exa search results injected as grounding.

    The LLM gets real paper titles/URLs/snippets to synthesize from,
    rather than inventing sources from memory.
    """
    from evalweaver.stage_prompts import build_stage_1_prompt

    search_results = _safe_search_causal(target_variable, num_results=num_results)

    if not search_results:
        # Fall back to the base prompt (LLM searches its own memory)
        return build_stage_1_prompt(target_variable)

    system = (
        "You are a research assistant specializing in causal evidence synthesis. "
        "You have access to real search results below. Use them as primary sources. "
        "You may supplement with your own knowledge but prefer the provided sources. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Format search results for injection
    sources_text = "\n".join([
        f"- [{r['title']}]({r['url']})" + (f" — {r['snippet'][:150]}" if r.get('snippet') else "")
        for r in search_results
    ])

    user = f"""Research question: What factors causally affect whether text is perceived as {target_variable}?

REAL SEARCH RESULTS (use these as primary sources):
{sources_text}

Using these sources (and your own knowledge of psychology, communication, rhetoric, linguistics, behavioral science):

Return source-backed claims about:
1. variables that increase {target_variable}
2. variables that decrease {target_variable}
3. variables that mediate or moderate {target_variable}
4. mechanisms explaining why those variables matter
5. disagreements, tensions, or boundary conditions in the research

IMPORTANT: Use the actual titles and URLs from the search results above as your source_id, title, and url fields. Synthesize causal claims from the real papers.

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "causal_research": [
    {{
      "source_id": "SRC_001",
      "title": "actual paper title from search results",
      "url": "actual URL from search results",
      "claim": "specific causal claim from or supported by this source",
      "causal_variable": "the variable name",
      "effect_direction": "increases | decreases | mediates | moderates",
      "mechanism": "WHY this variable has this effect (the causal mechanism)",
      "evidence_strength": "high | medium | low"
    }}
  ],
  "research_tensions": [
    {{
      "claim": "where sources disagree or boundary conditions exist",
      "variables": ["var1", "var2"]
    }}
  ]
}}"""
    return (system, user)


def build_stage_3_prompt_with_search(target_variable: str, causal_nodes: list, num_results: int = 10) -> tuple[str, str]:
    """
    Build Stage 3 prompt with real Exa measurement research injected.

    The LLM gets real NLP/text-analysis papers to ground measurement ideas.
    """
    from evalweaver.stage_prompts import build_stage_3_prompt

    node_ids = [n["node_id"] for n in causal_nodes if isinstance(n, dict)]
    search_results = _safe_search_measurement(target_variable, node_ids, num_results=num_results)

    if not search_results:
        return build_stage_3_prompt(target_variable, causal_nodes)

    system = (
        "You are a measurement research specialist mapping causal variables to observable text signals. "
        "You have access to real NLP research papers below. Use them to ground your measurement ideas. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    sources_text = "\n".join([
        f"- [{r['title']}]({r['url']})" + (f" — {r['snippet'][:150]}" if r.get('snippet') else "")
        for r in search_results
    ])

    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "label": n["label"], "definition": n.get("definition", "")}
         for n in causal_nodes],
        indent=2
    )

    user = f"""Research question: How can NLP, computational linguistics, or text analysis measure the following variables in text?

Target variable: {target_variable}
Causal nodes: {nodes_summary}

REAL NLP RESEARCH RESULTS (use these to ground measurement approaches):
{sources_text}

Using these real research papers (and your own knowledge of NLP measurement):

Return source-backed measurement ideas for each causal node.
IMPORTANT: Provide at least 2 different measurement approaches for most nodes.
IMPORTANT: Use actual paper titles and URLs from the search results where applicable.

For each measurement idea, include:
1. the causal node being measured
2. the observable text signal
3. concrete linguistic indicators
4. implementation ideas that could be converted into code

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "measurement_research": [
    {{
      "source_id": "MSRC_001",
      "causal_node": "credibility",
      "title": "actual paper title",
      "url": "actual URL",
      "measurement_claim": "specific measurable approach from this source",
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


def build_stage_5_prompt_with_search(
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    scorers: list,
    source_policy: dict,
    channel: str = "LinkedIn",
    topic: str = "AI tools for professionals",
    audience: str = "startup founders",
    num_results: int = 10,
) -> tuple[str, str]:
    """
    Build Stage 5 prompt with real social media content injected as anchors.

    The LLM gets real LinkedIn/social posts to use as anchor texts for pairs,
    instead of inventing generic anchors.
    """
    from evalweaver.stage_prompts import build_stage_5_prompt

    search_results = _safe_search_social(channel, topic, audience, num_results=num_results)

    if not search_results:
        return build_stage_5_prompt(target_variable, causal_graph, measurement_research, scorers, source_policy)

    system = (
        "You are generating evaluation text pairs that test slightly more vs slightly less "
        "of a target variable. You have access to real social media posts below. "
        "Use them as realistic anchor texts for your pairs. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Format social content for injection
    anchors_text = "\n".join([
        f"- {r['title'][:80]}" + (f"\n  Snippet: {r['snippet'][:200]}" if r.get('snippet') else "")
        for r in search_results[:8]
    ])

    # Compact graph/measurement data
    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "role": n.get("role", ""), "mechanism": n.get("mechanism", "")[:60]}
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
    policy_json = json.dumps(source_policy, indent=None)

    user = f"""Generate positive/negative text pairs for the target variable: {target_variable}

Channel: {channel}
Topic: {topic}
Audience: {audience}

REAL SOCIAL MEDIA POSTS (use these as inspiration for realistic anchor texts):
{anchors_text}

Causal nodes: {nodes_summary}
Causal edges: {edges_summary}
Measurement research: {measurement_summary}
Source policy: {policy_json}

REQUIREMENTS:
1. Generate at least 12 pairs (aim for 15)
2. Use the real social media posts above as inspiration for realistic anchor texts
3. Each pair: anchor (shared context), positive (slightly MORE {target_variable}), negative (slightly LESS {target_variable})
4. Control for length — positive and negative should be similar word counts
5. Each pair should test 1-2 causal nodes for clean isolation
6. Include a label_contract explaining why positive > negative
7. Vary topics across pairs for diversity
8. Do NOT create adversarial tricks — focus on genuine, subtle contrasts

Return valid JSON with this exact schema:
{{
  "target_variable": "{target_variable}",
  "pairs": [
    {{
      "pair_id": "P001",
      "source_id": "from real post or generated",
      "source_trace": "inspired by [post title] or generated",
      "anchor": "shared context (can be based on real posts above)",
      "positive": "text with slightly MORE {target_variable}",
      "negative": "text with slightly LESS {target_variable}",
      "split": "train",
      "target_delta": "what differs between positive and negative",
      "controlled_variables": ["length", "topic", "tone"],
      "causal_nodes_tested": ["node_id_1"],
      "causal_edges_tested": [],
      "measurement_ideas_tested": [],
      "causal_tensions_tested": [],
      "label_contract": "positive scores higher because...",
      "source_policy": "compliant",
      "policy_violations": []
    }}
  ]
}}"""
    return (system, user)
