"""Exa search provider for grounding pipeline stages in real web content.

Used by:
- Stage 1: Search for causal research on target variable (academic/NLP papers)
- Stage 3: Search for measurement research (NLP text analysis methods)
- Stage 5: Search for real social media / LinkedIn content as pair anchors
"""

import os
from typing import Optional

from evalweaver.artifacts import log


def _get_client():
    """Get Exa client, loading key from env or .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        raise ValueError("EXA_API_KEY not set. Add it to .env or export it.")

    from exa_py import Exa
    return Exa(api_key=api_key)


def search_causal_research(target_variable: str, num_results: int = 10) -> list[dict]:
    """
    Stage 1: Search for academic/research content about causal factors affecting the target variable.

    Returns list of {title, url, snippet, published_date} dicts.
    """
    exa = _get_client()
    queries = [
        f"what makes text {target_variable} causal factors research",
        f"persuasion {target_variable} text NLP measurement linguistics",
        f"{target_variable} communication psychology mechanisms evidence",
    ]

    all_results = []
    seen_urls = set()
    per_query = max(num_results // len(queries), 3)

    for query in queries:
        try:
            response = exa.search(
                query,
                num_results=per_query,
                type="neural",
            )
            for r in response.results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append({
                        "title": r.title or "",
                        "url": r.url or "",
                        "snippet": getattr(r, "text", "")[:300] if hasattr(r, "text") else "",
                        "published_date": getattr(r, "published_date", None),
                        "score": getattr(r, "score", None),
                    })
        except Exception as e:
            log("exa_search", f"Query failed: {query[:40]}... → {e}", "warn")

    log("exa_search", f"Causal research: found {len(all_results)} results for '{target_variable}'")
    return all_results[:num_results]


def search_measurement_research(target_variable: str, causal_nodes: list[str], num_results: int = 10) -> list[dict]:
    """
    Stage 3: Search for NLP/text-analysis methods to measure causal nodes.

    Returns list of {title, url, snippet, causal_node_query} dicts.
    """
    exa = _get_client()
    all_results = []
    seen_urls = set()

    # Build queries from causal nodes
    queries = []
    for node in causal_nodes[:6]:  # limit to top 6 nodes to avoid too many calls
        queries.append(f"NLP text analysis measure {node} in writing")

    # Add general measurement queries
    queries.append(f"computational linguistics measure {target_variable} text features")
    queries.append(f"text analysis {target_variable} scoring automated evaluation")

    per_query = max(num_results // len(queries), 2)

    for query in queries:
        try:
            response = exa.search(
                query,
                num_results=per_query,
                type="neural",
            )
            for r in response.results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append({
                        "title": r.title or "",
                        "url": r.url or "",
                        "snippet": getattr(r, "text", "")[:300] if hasattr(r, "text") else "",
                        "query": query,
                        "published_date": getattr(r, "published_date", None),
                    })
        except Exception as e:
            log("exa_search", f"Measurement query failed: {query[:40]}... → {e}", "warn")

    log("exa_search", f"Measurement research: found {len(all_results)} results across {len(queries)} queries")
    return all_results[:num_results]


def search_social_content(
    channel: str = "LinkedIn",
    topic: str = "",
    audience: str = "",
    num_results: int = 15,
) -> list[dict]:
    """
    Stage 5: Search for real social media content to use as pair anchors.

    Returns list of {title, url, snippet, domain} dicts.
    """
    exa = _get_client()

    # Build channel-specific queries
    domain_filter = None
    if channel.lower() == "linkedin":
        domain_filter = "linkedin.com"
    elif channel.lower() == "twitter":
        domain_filter = "twitter.com"

    queries = [
        f"{topic} {audience} {channel} post",
        f"{topic} product launch announcement {channel}",
        f"startup {topic} {audience} tips {channel}",
    ]

    all_results = []
    seen_urls = set()
    per_query = max(num_results // len(queries), 4)

    for query in queries:
        try:
            kwargs = {
                "num_results": per_query,
                "type": "neural",
            }
            if domain_filter:
                kwargs["include_domains"] = [domain_filter]

            response = exa.search(query, **kwargs)
            for r in response.results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append({
                        "title": r.title or "",
                        "url": r.url or "",
                        "snippet": getattr(r, "text", "")[:500] if hasattr(r, "text") else "",
                        "domain": r.url.split("/")[2] if r.url else "",
                    })
        except Exception as e:
            log("exa_search", f"Social query failed: {query[:40]}... → {e}", "warn")

    log("exa_search", f"Social content: found {len(all_results)} results for {channel}/{topic}")
    return all_results[:num_results]


def search_with_contents(query: str, num_results: int = 5) -> list[dict]:
    """
    Generic search with full text content extraction.
    Useful for getting page text to feed as context.
    """
    exa = _get_client()
    try:
        response = exa.search(
            query,
            num_results=num_results,
            type="neural",
            contents={"text": {"max_characters": 1000}},
        )
        results = []
        for r in response.results:
            results.append({
                "title": r.title or "",
                "url": r.url or "",
                "text": getattr(r, "text", "") or "",
                "published_date": getattr(r, "published_date", None),
            })
        return results
    except Exception as e:
        log("exa_search", f"search_with_contents failed: {e}", "warn")
        return []
