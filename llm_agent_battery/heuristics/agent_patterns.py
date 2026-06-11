"""Heuristic analyzers for agent-architecture design failure patterns.

Extends the base anti-pattern battery (analyzers.py) with detectors for
failure modes specific to LLM agent systems:

- UnboundedAgentLoopAnalyzer: agent loops with no exit path or no iteration budget
- MissingTimeoutAnalyzer: network/HTTP calls without a timeout
- UnsafeCodeExecutionAnalyzer: eval/exec/shell execution of dynamic (LLM) output
- UnboundedContextGrowthAnalyzer: conversation history growth without truncation
- HardcodedCredentialsAnalyzer: secrets/API keys committed in source or config
- UnvalidatedLLMOutputAnalyzer: parsing LLM responses without error handling

All analyzers are deterministic (AST + regex) and require no LLM invocations,
so they run in fast mode and CI.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from llm_agent_battery.heuristics.analyzers import _relevant_files, _safe_read
from llm_agent_battery.heuristics.base import BaseHeuristicAnalyzer
from llm_agent_battery.models import (
    ClassifiedFile,
    FileCategory,
    Finding,
    FindingCategory,
    Severity,
)

logger = logging.getLogger(__name__)


def _get_call_name(node: ast.Call) -> str | None:
    """Extract a readable dotted name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
        return node.func.attr
    return None


def _try_ranges(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[int, int]]:
    """Collect line ranges covered by try statements (body, handlers, finally)."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Try):
            end = getattr(node, "end_lineno", node.lineno)
            ranges.append((node.lineno, end))
    return ranges


def _iter_functions(tree: ast.AST):
    """Yield all function and async function definitions in a tree."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _parse(content: str) -> ast.AST | None:
    try:
        return ast.parse(content)
    except SyntaxError:
        return None


# ---------------------------------------------------------------------------
# UnboundedAgentLoopAnalyzer
# ---------------------------------------------------------------------------


class UnboundedAgentLoopAnalyzer(BaseHeuristicAnalyzer):
    """Detects agent loops with no exit path or no iteration budget.

    Two failure modes in AGENT_LOGIC/ORCHESTRATION files:
    1. `while True` loops with no break/return/raise — guaranteed runaway.
    2. `while True` loops that drive LLM/tool calls but have no iteration
       budget (max_steps, max_turns, attempt counter) — the loop terminates
       only if the model cooperates, which is not guaranteed.
    """

    _LLM_CALL_PATTERN = re.compile(
        r"(client\.|api\.|llm|invoke|converse|\bchat\b|completion|complete|generate"
        r"|send|call_tool|run_tool|tool_call|\bstep\b)",
        re.IGNORECASE,
    )

    _BUDGET_PATTERN = re.compile(
        r"(max_?(iter\w*|steps?|turns?|rounds?|loops?|attempts?|retries|calls)"
        r"|iteration_limit|step_limit|turn_limit|budget|num_steps|n_steps"
        r"|loop_count|attempts?\s*[<>]|counter\s*[<>])",
        re.IGNORECASE,
    )

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        target_files = _relevant_files(
            files, {FileCategory.AGENT_LOGIC, FileCategory.ORCHESTRATION}
        )
        for cf in target_files:
            if cf.path.suffix != ".py":
                continue
            content = _safe_read(cf.path)
            if content is None:
                continue
            findings.extend(self._check_file(cf, content))
        return findings

    def _check_file(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        tree = _parse(content)
        if tree is None:
            return findings

        for func in _iter_functions(tree):
            func_source = ast.get_source_segment(content, func) or ""
            has_budget = bool(self._BUDGET_PATTERN.search(func_source))

            for node in ast.walk(func):
                if not isinstance(node, ast.While):
                    continue
                if not self._is_while_true(node):
                    continue

                has_exit = any(
                    isinstance(child, (ast.Break, ast.Return, ast.Raise))
                    for child in ast.walk(node)
                )
                loop_source = ast.get_source_segment(content, node) or ""
                drives_llm = bool(self._LLM_CALL_PATTERN.search(loop_source))

                if not has_exit:
                    findings.append(Finding(
                        severity=Severity.HIGH,
                        category=FindingCategory.LOGIC_ERROR,
                        file_path=cf.relative_path,
                        location=func.name,
                        title="Infinite agent loop with no exit path",
                        description=(
                            f"`while True` loop in '{func.name}' at line {node.lineno} "
                            f"contains no break, return, or raise — it can never terminate."
                        ),
                        impact="The agent runs forever, consuming tokens/compute until killed externally.",
                        remediation="Add an explicit exit condition (break/return) and an iteration budget.",
                        source_layer="heuristic",
                    ))
                elif drives_llm and not has_budget:
                    findings.append(Finding(
                        severity=Severity.HIGH,
                        category=FindingCategory.DESIGN_FLAW,
                        file_path=cf.relative_path,
                        location=func.name,
                        title="Agent loop without iteration budget",
                        description=(
                            f"`while True` loop in '{func.name}' at line {node.lineno} drives "
                            f"LLM/tool calls but has no iteration cap (max_steps, max_turns, "
                            f"attempt counter). Termination depends entirely on model behavior."
                        ),
                        impact=(
                            "If the model never emits the stop condition, the agent loops "
                            "indefinitely, accumulating cost and possibly repeating side effects."
                        ),
                        remediation="Add a max-iteration counter that force-exits the loop with a fallback result.",
                        source_layer="heuristic",
                    ))

        return findings

    @staticmethod
    def _is_while_true(node: ast.While) -> bool:
        return isinstance(node.test, ast.Constant) and bool(node.test.value) is True


# ---------------------------------------------------------------------------
# MissingTimeoutAnalyzer
# ---------------------------------------------------------------------------


class MissingTimeoutAnalyzer(BaseHeuristicAnalyzer):
    """Detects HTTP/network calls without a timeout in agent/tool code.

    An agent blocked on a hung network call cannot make progress, retry,
    or report failure — the whole loop stalls.
    """

    _HTTP_CALL_PATTERN = re.compile(
        r"^(requests|httpx)\.(get|post|put|patch|delete|head|options|request)$"
    )

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        target_files = _relevant_files(
            files,
            {
                FileCategory.TOOL_DEFINITION,
                FileCategory.AGENT_LOGIC,
                FileCategory.ORCHESTRATION,
            },
        )
        for cf in target_files:
            if cf.path.suffix != ".py":
                continue
            content = _safe_read(cf.path)
            if content is None:
                continue
            findings.extend(self._check_file(cf, content))
        return findings

    def _check_file(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        tree = _parse(content)
        if tree is None:
            return findings

        for func in _iter_functions(tree):
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                call_name = _get_call_name(node)
                if not call_name:
                    continue
                is_http = bool(self._HTTP_CALL_PATTERN.match(call_name))
                is_urlopen = call_name.endswith("urlopen")
                if not (is_http or is_urlopen):
                    continue
                if self._has_timeout(node):
                    continue
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.DESIGN_FLAW,
                    file_path=cf.relative_path,
                    location=func.name,
                    title=f"Network call without timeout: '{call_name}'",
                    description=(
                        f"The call to '{call_name}' in '{func.name}' at line {node.lineno} "
                        f"has no timeout parameter and can block forever."
                    ),
                    impact="A hung network call stalls the agent loop indefinitely with no recovery path.",
                    remediation=f"Pass an explicit timeout to '{call_name}' and handle the timeout exception.",
                    source_layer="heuristic",
                ))

        return findings

    @staticmethod
    def _has_timeout(node: ast.Call) -> bool:
        for kw in node.keywords:
            # arg is None for **kwargs splats — assume timeout may be inside
            if kw.arg is None or kw.arg in ("timeout", "request_timeout"):
                return True
        return False


# ---------------------------------------------------------------------------
# UnsafeCodeExecutionAnalyzer
# ---------------------------------------------------------------------------


class UnsafeCodeExecutionAnalyzer(BaseHeuristicAnalyzer):
    """Detects execution of dynamic content: eval/exec, shell=True, os.system.

    In agent systems the dynamic value is frequently model output, which makes
    these sinks remote-code-execution paths for prompt injection.
    """

    _LLM_SOURCE_PATTERN = re.compile(
        r"(response|completion|output|llm|generated|model|content|answer|reply|code|result)",
        re.IGNORECASE,
    )

    _SUBPROCESS_PATTERN = re.compile(r"^subprocess\.(run|call|check_call|check_output|Popen)$")

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        for cf in files:
            if cf.primary_category == FileCategory.TEST:
                continue
            if cf.path.suffix != ".py":
                continue
            content = _safe_read(cf.path)
            if content is None:
                continue
            findings.extend(self._check_file(cf, content))
        return findings

    def _check_file(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        tree = _parse(content)
        if tree is None:
            return findings

        for func in _iter_functions(tree):
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                call_name = _get_call_name(node)
                if not call_name:
                    continue

                finding = self._check_call(cf, content, func.name, node, call_name)
                if finding is not None:
                    findings.append(finding)

        return findings

    def _check_call(
        self,
        cf: ClassifiedFile,
        content: str,
        func_name: str,
        node: ast.Call,
        call_name: str,
    ) -> Finding | None:
        first_arg = node.args[0] if node.args else None
        arg_is_dynamic = first_arg is not None and not isinstance(first_arg, ast.Constant)

        # eval()/exec() on dynamic content
        if call_name in ("eval", "exec") and arg_is_dynamic:
            arg_src = ast.get_source_segment(content, first_arg) or ""
            llm_sourced = bool(self._LLM_SOURCE_PATTERN.search(arg_src))
            severity = Severity.CRITICAL if llm_sourced else Severity.HIGH
            qualifier = "model-generated" if llm_sourced else "dynamic"
            return Finding(
                severity=severity,
                category=FindingCategory.SECURITY,
                file_path=cf.relative_path,
                location=func_name,
                title=f"'{call_name}()' on {qualifier} content",
                description=(
                    f"'{call_name}()' in '{func_name}' at line {node.lineno} executes "
                    f"a {qualifier} value ('{arg_src[:60]}'). In an agent system this "
                    f"is an arbitrary code execution path."
                ),
                impact=(
                    "Model output (or injected content) executed as code can read/write "
                    "files, exfiltrate secrets, or take any action the process can."
                ),
                remediation=(
                    "Never eval/exec model output directly. Use a sandboxed interpreter, "
                    "a restricted DSL, or structured tool calls instead."
                ),
                source_layer="heuristic",
            )

        # subprocess with shell=True and a dynamic command
        if self._SUBPROCESS_PATTERN.match(call_name) and arg_is_dynamic:
            shell_true = any(
                kw.arg == "shell"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            )
            if shell_true:
                return Finding(
                    severity=Severity.HIGH,
                    category=FindingCategory.SECURITY,
                    file_path=cf.relative_path,
                    location=func_name,
                    title=f"Shell execution of dynamic command via '{call_name}'",
                    description=(
                        f"'{call_name}' in '{func_name}' at line {node.lineno} runs a "
                        f"dynamically built command with shell=True."
                    ),
                    impact="Command injection: crafted input (or model output) can run arbitrary shell commands.",
                    remediation="Pass the command as an argument list with shell=False, or validate against an allowlist.",
                    source_layer="heuristic",
                )

        # os.system with a dynamic command
        if call_name == "os.system" and arg_is_dynamic:
            return Finding(
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                file_path=cf.relative_path,
                location=func_name,
                title="os.system() on dynamic command",
                description=(
                    f"'os.system' in '{func_name}' at line {node.lineno} runs a "
                    f"dynamically built shell command."
                ),
                impact="Command injection: crafted input (or model output) can run arbitrary shell commands.",
                remediation="Use subprocess with an argument list (shell=False) and validated inputs.",
                source_layer="heuristic",
            )

        return None


# ---------------------------------------------------------------------------
# UnboundedContextGrowthAnalyzer
# ---------------------------------------------------------------------------


class UnboundedContextGrowthAnalyzer(BaseHeuristicAnalyzer):
    """Detects conversation history growth without any truncation strategy.

    Appending to messages/history/memory with no pruning eventually overflows
    the model's context window, causing API errors or silent truncation of
    the system prompt.
    """

    _CONTEXT_VAR_PATTERN = re.compile(
        r"^(messages|history|conversation|memory|context|transcript|chat_log|chat_history|turns)$",
        re.IGNORECASE,
    )

    _TRUNCATION_PATTERN = re.compile(
        r"(truncat|trim|prune|pop\(0\)|popleft|\[-\s*\d+\s*:|maxlen|deque"
        r"|max_(history|messages|context|turns|len)|summar|compact|sliding|window|evict)",
        re.IGNORECASE,
    )

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        target_files = _relevant_files(
            files,
            {
                FileCategory.AGENT_LOGIC,
                FileCategory.ORCHESTRATION,
                FileCategory.STATE_MANAGEMENT,
            },
        )
        for cf in target_files:
            if cf.path.suffix != ".py":
                continue
            content = _safe_read(cf.path)
            if content is None:
                continue
            findings.extend(self._check_file(cf, content))
        return findings

    def _check_file(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        # A truncation signal anywhere in the file counts as a strategy
        if self._TRUNCATION_PATTERN.search(content):
            return []

        tree = _parse(content)
        if tree is None:
            return []

        findings: list[Finding] = []
        reported_vars: set[str] = set()

        for func in _iter_functions(tree):
            for node in ast.walk(func):
                var_name = self._appended_context_var(node)
                if var_name is None or var_name.lower() in reported_vars:
                    continue
                reported_vars.add(var_name.lower())
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.DESIGN_FLAW,
                    file_path=cf.relative_path,
                    location=func.name,
                    title=f"Unbounded context growth: '{var_name}'",
                    description=(
                        f"'{var_name}' is appended to in '{func.name}' at line {node.lineno} "
                        f"but the file contains no truncation, pruning, or summarization logic."
                    ),
                    impact=(
                        "Conversation history grows without bound until the model's context "
                        "window overflows, causing API errors or silently dropped instructions."
                    ),
                    remediation=(
                        "Add a context management strategy: sliding window, max-message cap, "
                        "or periodic summarization of older turns."
                    ),
                    source_layer="heuristic",
                ))

        return findings

    def _appended_context_var(self, node: ast.AST) -> str | None:
        """Return the context-like variable name if this node grows it."""
        # x.append(...) / self.x.append(...) / x.extend(...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("append", "extend"):
                target = node.func.value
                name = self._target_name(target)
                if name and self._CONTEXT_VAR_PATTERN.match(name):
                    return name
        # x += [...] / self.x += [...]
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            name = self._target_name(node.target)
            if name and self._CONTEXT_VAR_PATTERN.match(name):
                return name
        return None

    @staticmethod
    def _target_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


# ---------------------------------------------------------------------------
# HardcodedCredentialsAnalyzer
# ---------------------------------------------------------------------------


class HardcodedCredentialsAnalyzer(BaseHeuristicAnalyzer):
    """Detects API keys and secrets committed in source or config files."""

    _CRED_NAME_PATTERN = re.compile(
        r"(api_?key|secret|token|passwd|password|access_?key|auth_?key|private_?key|client_secret)",
        re.IGNORECASE,
    )

    _PLACEHOLDER_PATTERN = re.compile(
        r"(\$\{|\{\{|[<>]|\bexample\b|placeholder|your[-_ ]|change[-_ ]?me|dummy|xxx+|redacted|os\.environ|\benv\b)",
        re.IGNORECASE,
    )

    # Well-known credential shapes (provider token prefixes)
    _TOKEN_SHAPE_PATTERN = re.compile(
        r"(sk-ant-[A-Za-z0-9\-_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
        r"|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}"
        r"|xox[baprs]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z\-_]{35})"
    )

    _CONFIG_LINE_PATTERN = re.compile(
        r"(api_?key|secret|token|password|access_?key)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_\-/+\.]{16,})",
        re.IGNORECASE,
    )

    _CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".ini", ".env", ".cfg"}

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        for cf in files:
            if cf.primary_category == FileCategory.TEST:
                continue
            content = _safe_read(cf.path)
            if content is None:
                continue

            # Token-shaped literals are flagged in any scanned file type
            findings.extend(self._check_token_shapes(cf, content))

            if cf.path.suffix == ".py":
                findings.extend(self._check_python_assignments(cf, content))
            elif cf.path.suffix in self._CONFIG_SUFFIXES:
                findings.extend(self._check_config_lines(cf, content))

        return findings

    def _check_token_shapes(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for match in self._TOKEN_SHAPE_PATTERN.finditer(content):
            lineno = content.count("\n", 0, match.start()) + 1
            token = match.group(0)
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category=FindingCategory.SECURITY,
                file_path=cf.relative_path,
                location=f"line {lineno}",
                title="Hardcoded credential with known provider token shape",
                description=(
                    f"Line {lineno} contains what appears to be a real credential "
                    f"('{token[:12]}...'). Provider token prefixes are recognizable "
                    f"and harvested by scanners."
                ),
                impact="Anyone with repository access (or a leak) can use this credential.",
                remediation="Revoke the credential immediately and load secrets from environment variables or a secret manager.",
                source_layer="heuristic",
            ))
        return findings

    def _check_python_assignments(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        tree = _parse(content)
        if tree is None:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                continue
            value = node.value.value
            if len(value) < 12 or self._PLACEHOLDER_PATTERN.search(value):
                continue
            # URLs without embedded credentials are not secrets
            if value.startswith(("http://", "https://")) and "@" not in value:
                continue

            for target in node.targets:
                name = None
                if isinstance(target, ast.Name):
                    name = target.id
                elif isinstance(target, ast.Attribute):
                    name = target.attr
                if name and self._CRED_NAME_PATTERN.search(name):
                    findings.append(Finding(
                        severity=Severity.HIGH,
                        category=FindingCategory.SECURITY,
                        file_path=cf.relative_path,
                        location=name,
                        title=f"Hardcoded credential assigned to '{name}'",
                        description=(
                            f"Variable '{name}' at line {node.lineno} is assigned a "
                            f"string literal that looks like a real secret."
                        ),
                        impact="Secrets in source code leak via version control, logs, and error reports.",
                        remediation=f"Load '{name}' from an environment variable or secret manager instead.",
                        source_layer="heuristic",
                    ))
                    break

        return findings

    def _check_config_lines(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for i, line in enumerate(content.splitlines(), start=1):
            match = self._CONFIG_LINE_PATTERN.search(line)
            if not match:
                continue
            value = match.group(2)
            if self._PLACEHOLDER_PATTERN.search(value):
                continue
            findings.append(Finding(
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                file_path=cf.relative_path,
                location=f"line {i}",
                title="Hardcoded credential in config file",
                description=(
                    f"Line {i} assigns a literal value to a credential-named key "
                    f"('{match.group(1)}')."
                ),
                impact="Secrets in committed config files leak via version control.",
                remediation="Reference an environment variable or secret manager instead of a literal value.",
                source_layer="heuristic",
            ))
        return findings


# ---------------------------------------------------------------------------
# UnvalidatedLLMOutputAnalyzer
# ---------------------------------------------------------------------------


class UnvalidatedLLMOutputAnalyzer(BaseHeuristicAnalyzer):
    """Detects parsing of LLM responses without error handling.

    LLMs return malformed JSON, refusals, and prose wrapped around payloads.
    A bare json.loads() on model output crashes the agent on the first
    non-conforming response.
    """

    _LLM_VALUE_PATTERN = re.compile(
        r"(response|completion|output|llm|content|message|reply|answer|generated|result|text)",
        re.IGNORECASE,
    )

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        target_files = _relevant_files(
            files,
            {
                FileCategory.AGENT_LOGIC,
                FileCategory.TOOL_DEFINITION,
                FileCategory.ORCHESTRATION,
            },
        )
        for cf in target_files:
            if cf.path.suffix != ".py":
                continue
            content = _safe_read(cf.path)
            if content is None:
                continue
            findings.extend(self._check_file(cf, content))
        return findings

    def _check_file(self, cf: ClassifiedFile, content: str) -> list[Finding]:
        findings: list[Finding] = []
        tree = _parse(content)
        if tree is None:
            return findings

        for func in _iter_functions(tree):
            try_ranges = _try_ranges(func)
            for node in ast.walk(func):
                if not self._is_json_loads(node):
                    continue
                if not node.args:
                    continue
                arg_src = ast.get_source_segment(content, node.args[0]) or ""
                if not self._LLM_VALUE_PATTERN.search(arg_src):
                    continue
                in_try = any(start <= node.lineno <= end for start, end in try_ranges)
                if in_try:
                    continue
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.EDGE_CASE,
                    file_path=cf.relative_path,
                    location=func.name,
                    title="LLM output parsed without error handling",
                    description=(
                        f"'json.loads({arg_src[:50]})' in '{func.name}' at line "
                        f"{node.lineno} parses model output with no try/except. "
                        f"LLM responses are not guaranteed to be valid JSON."
                    ),
                    impact=(
                        "The first malformed response (prose, markdown fences, refusal) "
                        "raises JSONDecodeError and crashes the agent step."
                    ),
                    remediation=(
                        "Wrap parsing in try/except, strip markdown fences first, and "
                        "define fallback behavior (retry with a fix-it prompt, or fail gracefully)."
                    ),
                    source_layer="heuristic",
                ))

        return findings

    @staticmethod
    def _is_json_loads(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "loads"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "json"
        )
