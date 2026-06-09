#!/usr/bin/env python3
"""
LLM-powered code review of evalweaver taste compiler pipeline.

Sends code function-by-function to Bedrock/Sonnet for targeted review,
then aggregates findings.

Usage:
    python3.11 scripts/llm_code_review.py [--model-id MODEL] [--region REGION]
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def get_file_from_branch(branch: str, filepath: str) -> str:
    """Read a file from a git branch without checking it out."""
    result = subprocess.run(
        ["git", "show", f"{branch}:{filepath}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise FileNotFoundError(f"Cannot read {filepath} from {branch}: {result.stderr}")
    return result.stdout


def extract_functions(source: str) -> list[dict]:
    """Split Python source into top-level functions/classes with context."""
    chunks = []
    lines = source.split("\n")
    current_chunk = {"name": "__module_header__", "start": 0, "lines": []}

    for i, line in enumerate(lines):
        # Detect top-level def or class
        if re.match(r'^(def |class )', line):
            # Save previous chunk
            if current_chunk["lines"]:
                chunks.append(current_chunk)
            name = re.match(r'^(def |class )(\w+)', line)
            current_chunk = {
                "name": name.group(2) if name else f"block_{i}",
                "start": i,
                "lines": [line]
            }
        else:
            current_chunk["lines"].append(line)

    if current_chunk["lines"]:
        chunks.append(current_chunk)

    return chunks


def chunk_by_size(source: str, filename: str, max_chars: int = 12000) -> list[dict]:
    """Split source into reviewable chunks, respecting function boundaries."""
    functions = extract_functions(source)
    chunks = []
    current = {"name": "", "content": "", "functions": []}

    for func in functions:
        func_text = "\n".join(func["lines"])
        # If single function is too big, send it alone
        if len(func_text) > max_chars:
            if current["content"]:
                chunks.append(current)
                current = {"name": "", "content": "", "functions": []}
            chunks.append({
                "name": func["name"],
                "content": func_text[:max_chars],  # truncate if massive
                "functions": [func["name"]]
            })
            continue

        # If adding this function exceeds limit, start new chunk
        if len(current["content"]) + len(func_text) > max_chars:
            if current["content"]:
                chunks.append(current)
            current = {"name": func["name"], "content": func_text, "functions": [func["name"]]}
        else:
            current["content"] += "\n" + func_text
            current["functions"].append(func["name"])

    if current["content"]:
        chunks.append(current)

    # Label chunks
    for i, c in enumerate(chunks):
        if not c["name"]:
            c["name"] = f"chunk_{i}"
        c["file"] = filename

    return chunks


def call_bedrock(client, model_id: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Call Bedrock Converse API."""
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": user}]}],
        system=[{"text": system}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
    )
    return response["output"]["message"]["content"][0]["text"]


REVIEW_SYSTEM = """You are an expert code reviewer for an NLP text-scoring pipeline called "taste compiler".
The system:
1. Takes a quality goal (e.g., "persuasive")
2. Builds a taste map (rewards/punishes/preserves)
3. Generates scorer hypotheses and Python scorer functions
4. Evaluates scorers against labeled text pairs (positive > negative)
5. Uses Pareto selection to pick the best scorers
6. Selects a final candidate rewrite

Your job: Find REAL bugs, logic errors, and correctness issues in the code chunk shown.
Focus on things that cause WRONG results. Ignore style/formatting.

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|data_integrity|design_flaw",
  "location": "function_name or description of where",
  "title": "short title",
  "description": "what's wrong and why",
  "impact": "what breaks because of this"
}"""


def review_chunk(client, model_id: str, chunk: dict, file_context: str) -> list:
    """Review a single code chunk and return findings."""
    user_msg = (
        f"File: {chunk['file']}\n"
        f"Functions: {', '.join(chunk['functions'])}\n"
        f"Context: {file_context}\n\n"
        f"```python\n{chunk['content']}\n```\n\n"
        "Find bugs, logic errors, and correctness issues. Return JSON array."
    )
    try:
        response = call_bedrock(client, model_id, REVIEW_SYSTEM, user_msg, max_tokens=2048)
        # Parse JSON from response
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        findings = json.loads(text)
        if isinstance(findings, list):
            for f in findings:
                f["source_file"] = chunk["file"]
                f["reviewed_functions"] = chunk["functions"]
            return findings
    except (json.JSONDecodeError, IndexError):
        # If model didn't return valid JSON, try to extract what we can
        return [{"severity": "low", "category": "parse_error",
                 "location": chunk["name"], "title": "Review parse error",
                 "description": f"Could not parse model response for {chunk['file']}:{chunk['name']}",
                 "impact": "Review incomplete", "raw_response": response[:500]}]
    except Exception as e:
        return [{"severity": "low", "category": "error",
                 "location": chunk["name"], "title": f"Review error: {e}",
                 "description": str(e), "impact": "Review incomplete"}]
    return []


FILE_CONTEXTS = {
    "evalweaver/pipeline.py": "Main orchestration: runs 12-step taste compilation. Contains hardcoded taste data, scorer hypotheses, scorer code, and the run_pipeline function.",
    "evalweaver/probes.py": "NLP probe functions that measure text properties (jargon density, argument progression, causal density, etc). Called by scorer functions.",
    "evalweaver/scorers.py": "Scorer validation logic: runs scorer code against validation pairs to check correctness.",
    "evalweaver/pairs.py": "Evaluation pair definitions and validation/splitting logic. Pairs have positive/negative texts.",
    "evalweaver/evaluation.py": "Scorer evaluation: runs each scorer against all pairs, computes accuracy/margin/spread.",
    "evalweaver/pareto.py": "Pareto front selection: picks non-dominated scorers from evaluation results.",
    "evalweaver/failure_packet.py": "Builds failure analysis from eval results: identifies which pairs each scorer fails on.",
    "evalweaver/repair.py": "Round 1 repair: evolved scorer hypotheses and code from failure analysis.",
    "evalweaver/candidates.py": "Candidate text generation and scoring with the final scorer ensemble.",
    "evalweaver/criteria.py": "Computed spec criteria: checks pipeline outputs meet minimum thresholds.",
    "evalweaver/policy.py": "Source policy enforcement: hard/soft rules for what rewrites can/cannot do.",
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LLM code review of taste compiler")
    parser.add_argument("--model-id", default="us.anthropic.claude-sonnet-4-6")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--branch", default="origin/main")
    parser.add_argument("--output-dir", default="evalweaver/.agentbattery/llm_review")
    parser.add_argument("--max-chunk-chars", type=int, default=12000)
    args = parser.parse_args()

    # Setup Bedrock client
    import boto3
    from botocore.config import Config

    session = boto3.Session(region_name=args.region)
    print("Checking AWS credentials...")
    try:
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"  Account: {identity['Account']}")
        print(f"  ✓ Credentials valid\n")
    except Exception as e:
        print(f"  ✗ Credential error: {e}")
        sys.exit(1)

    boto_config = Config(
        retries={"mode": "standard", "max_attempts": 3},
        connect_timeout=30,
        read_timeout=300,
    )
    client = session.client("bedrock-runtime", config=boto_config)

    # Read files from main branch
    files_to_review = list(FILE_CONTEXTS.keys())
    print(f"Reading source from {args.branch}...")
    source_code = {}
    for f in files_to_review:
        try:
            source_code[f] = get_file_from_branch(args.branch, f)
            print(f"  ✓ {f} ({len(source_code[f]):,} chars)")
        except FileNotFoundError:
            print(f"  ✗ {f} (not found)")

    # Chunk all files
    all_chunks = []
    for filepath, source in source_code.items():
        chunks = chunk_by_size(source, filepath, args.max_chunk_chars)
        all_chunks.extend(chunks)
        print(f"  {filepath}: {len(chunks)} chunks")

    print(f"\nTotal chunks to review: {len(all_chunks)}")

    # Output directory
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Review each chunk
    all_findings = []
    print(f"\n{'='*65}")
    print(f"REVIEWING {len(all_chunks)} CODE CHUNKS")
    print(f"{'='*65}\n")

    for i, chunk in enumerate(all_chunks):
        label = f"[{i+1}/{len(all_chunks)}] {chunk['file']}:{chunk['name']}"
        print(f"  {label}...", end=" ", flush=True)
        start = time.time()

        context = FILE_CONTEXTS.get(chunk["file"], "")
        findings = review_chunk(client, args.model_id, chunk, context)

        elapsed = time.time() - start
        n = len([f for f in findings if f.get("category") != "parse_error"])
        print(f"{'✓' if not n else '⚠'} {n} findings ({elapsed:.1f}s)")

        all_findings.extend(findings)

        # Small delay to avoid throttling
        time.sleep(1)

    # Filter out parse errors and dedupe
    real_findings = [f for f in all_findings if f.get("category") not in ("parse_error", "error")]

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    real_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 4))

    # Save results
    (out_dir / "all_findings.json").write_text(json.dumps(real_findings, indent=2))

    # Generate readable report
    report_lines = [
        "# LLM Code Review — Taste Compiler (main branch)",
        f"\n- Model: {args.model_id}",
        f"- Branch: {args.branch}",
        f"- Files reviewed: {len(source_code)}",
        f"- Chunks reviewed: {len(all_chunks)}",
        f"- Total findings: {len(real_findings)}",
        f"  - Critical: {sum(1 for f in real_findings if f.get('severity')=='critical')}",
        f"  - High: {sum(1 for f in real_findings if f.get('severity')=='high')}",
        f"  - Medium: {sum(1 for f in real_findings if f.get('severity')=='medium')}",
        f"  - Low: {sum(1 for f in real_findings if f.get('severity')=='low')}",
        "\n---\n",
    ]

    for f in real_findings:
        sev_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(f.get("severity"), "⚪")
        report_lines.append(f"### {sev_emoji} [{f.get('severity','?').upper()}] {f.get('title','Untitled')}")
        report_lines.append(f"- **File**: {f.get('source_file','?')}")
        report_lines.append(f"- **Location**: {f.get('location','?')}")
        report_lines.append(f"- **Category**: {f.get('category','?')}")
        report_lines.append(f"- **Description**: {f.get('description','')}")
        report_lines.append(f"- **Impact**: {f.get('impact','')}")
        report_lines.append("")

    report = "\n".join(report_lines)
    (out_dir / "review_report.md").write_text(report)

    # Print summary
    print(f"\n{'='*65}")
    print("REVIEW COMPLETE")
    print(f"{'='*65}")
    print(f"\n  Findings: {len(real_findings)}")
    for f in real_findings[:10]:
        sev = f.get("severity", "?")
        print(f"    [{sev.upper()}] {f.get('source_file')}:{f.get('location')} — {f.get('title')}")
    if len(real_findings) > 10:
        print(f"    ... and {len(real_findings)-10} more")
    print(f"\n  Full report: {out_dir}/review_report.md")
    print(f"  Raw JSON:    {out_dir}/all_findings.json")


if __name__ == "__main__":
    main()
