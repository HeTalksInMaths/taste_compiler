"""Concrete heuristic analyzers for common agent anti-patterns."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from llm_agent_battery.heuristics.base import BaseHeuristicAnalyzer
from llm_agent_battery.models import (
    ClassifiedFile,
    FileCategory,
    Finding,
    FindingCategory,
    Severity,
)

logger = logging.getLogger(__name__)


def _safe_read(path: Path, max_bytes: int = 64 * 1024) -> str | None:
    """Read file content, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except (OSError, UnicodeDecodeError):
        return None


def _relevant_files(
    files: list[ClassifiedFile], categories: set[FileCategory]
) -> list[ClassifiedFile]:
    """Filter files to those matching any of the given categories."""
    result = []
    for f in files:
        all_cats = {f.primary_category} | set(f.secondary_categories)
        if all_cats & categories:
            result.append(f)
    return result


# ---------------------------------------------------------------------------
# MissingErrorHandlingAnalyzer
# ---------------------------------------------------------------------------


class MissingErrorHandlingAnalyzer(BaseHeuristicAnalyzer):
    """Detects tool/API calls without try/except in TOOL_DEFINITION and AGENT_LOGIC files."""

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        target_files = _relevant_files(
            files, {FileCategory.TOOL_DEFINITION, FileCategory.AGENT_LOGIC}
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
        """Check a single file for missing error handling around calls."""
        findings: list[Finding] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Look for call expressions that appear to be external/tool calls
            calls_without_handler = self._find_unhandled_calls(node)
            for call_name, lineno in calls_without_handler:
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.EDGE_CASE,
                    file_path=cf.relative_path,
                    location=node.name,
                    title=f"Missing error handling around '{call_name}'",
                    description=(
                        f"The call to '{call_name}' in function '{node.name}' "
                        f"is not wrapped in a try/except block. If this call fails, "
                        f"the error will propagate unhandled."
                    ),
                    impact="Unhandled exceptions may crash the agent or leave state inconsistent.",
                    remediation=f"Wrap the call to '{call_name}' in a try/except block with appropriate error handling.",
                    source_layer="heuristic",
                ))

        return findings

    def _find_unhandled_calls(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[tuple[str, int]]:
        """Find external-looking calls not inside try/except blocks."""
        # Collect line ranges covered by try blocks
        try_ranges: list[tuple[int, int]] = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Try):
                start = node.lineno
                # End is the last line of the try body
                end = max(
                    getattr(n, "end_lineno", n.lineno)
                    for n in node.body
                )
                try_ranges.append((start, end))

        # Find calls that look like external/tool invocations
        unhandled: list[tuple[str, int]] = []
        external_patterns = re.compile(
            r"(client\.|api\.|request\.|fetch|invoke|execute|call|send|run_tool|tool_call)"
        )

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            call_name = self._get_call_name(node)
            if not call_name:
                continue

            # Check if it looks like an external call
            if not external_patterns.search(call_name):
                continue

            # Check if it's within a try block
            lineno = node.lineno
            in_try = any(start <= lineno <= end for start, end in try_ranges)
            if not in_try:
                unhandled.append((call_name, lineno))

        return unhandled

    @staticmethod
    def _get_call_name(node: ast.Call) -> str | None:
        """Extract a readable name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            return node.func.attr
        return None


# ---------------------------------------------------------------------------
# UnguardedMutationAnalyzer
# ---------------------------------------------------------------------------


class UnguardedMutationAnalyzer(BaseHeuristicAnalyzer):
    """Detects dict/list mutations in ORCHESTRATION/STATE_MANAGEMENT without guards."""

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        target_files = _relevant_files(
            files, {FileCategory.ORCHESTRATION, FileCategory.STATE_MANAGEMENT}
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
        """Check for unguarded state mutations."""
        findings: list[Finding] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            mutations = self._find_unguarded_mutations(node)
            for mutation_desc, lineno in mutations:
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.DATA_INTEGRITY,
                    file_path=cf.relative_path,
                    location=node.name,
                    title=f"Unguarded state mutation: {mutation_desc}",
                    description=(
                        f"State mutation '{mutation_desc}' in '{node.name}' "
                        f"at line {lineno} has no validation or guard condition."
                    ),
                    impact="Corrupted state may cause incorrect agent behavior or data loss.",
                    remediation="Add a validation check or guard condition before mutating shared state.",
                    source_layer="heuristic",
                ))

        return findings

    def _find_unguarded_mutations(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[tuple[str, int]]:
        """Find dict/list mutations not preceded by an if-guard."""
        mutations: list[tuple[str, int]] = []

        # Collect lines that are guarded (inside an if statement)
        guarded_lines: set[int] = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.If):
                for child in ast.walk(node):
                    if hasattr(child, "lineno"):
                        guarded_lines.add(child.lineno)

        # Look for mutation calls: .append(), .update(), .pop(), .extend(), etc.
        mutation_methods = {"append", "update", "pop", "extend", "remove", "insert", "clear", "setdefault"}

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in mutation_methods:
                continue

            # Check if the target is self.something (state)
            if isinstance(node.func.value, ast.Attribute):
                if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == "self":
                    if node.lineno not in guarded_lines:
                        target = f"self.{node.func.value.attr}.{node.func.attr}()"
                        mutations.append((target, node.lineno))

        # Also check direct subscript assignments: self.state[key] = value
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Attribute):
                        if isinstance(target.value.value, ast.Name) and target.value.value.id == "self":
                            if node.lineno not in guarded_lines:
                                attr_name = target.value.attr
                                mutations.append((f"self.{attr_name}[...] = ...", node.lineno))

        return mutations


# ---------------------------------------------------------------------------
# MissingConfirmationGateAnalyzer
# ---------------------------------------------------------------------------


class MissingConfirmationGateAnalyzer(BaseHeuristicAnalyzer):
    """Detects destructive operations (delete, remove, drop) without confirmation patterns."""

    # Patterns that indicate a destructive operation
    # Use word-start boundary only — destructive words may be prefixes (e.g. delete_records)
    _DESTRUCTIVE_PATTERNS = re.compile(
        r"\b(delete|remove|drop|destroy|purge|truncate|wipe|erase)",
        re.IGNORECASE,
    )

    # Patterns that indicate a confirmation gate
    _CONFIRMATION_PATTERNS = re.compile(
        r"(confirm|approval|authorize|verify|prompt_user|ask_user|human_in_the_loop|gate|guard)",
        re.IGNORECASE,
    )

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        # Check all non-test files for destructive ops
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
        """Check for destructive operations without confirmation."""
        findings: list[Finding] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Get the source lines for this function
            func_source = ast.get_source_segment(content, node)
            if not func_source:
                continue

            # Check if function contains destructive operations
            if not self._DESTRUCTIVE_PATTERNS.search(func_source):
                continue

            # Check if function has a confirmation gate
            if self._CONFIRMATION_PATTERNS.search(func_source):
                continue

            # Find specific destructive calls
            destructive_calls = self._DESTRUCTIVE_PATTERNS.findall(func_source)
            if destructive_calls:
                findings.append(Finding(
                    severity=Severity.HIGH,
                    category=FindingCategory.SECURITY,
                    file_path=cf.relative_path,
                    location=node.name,
                    title=f"Destructive operation without confirmation gate",
                    description=(
                        f"Function '{node.name}' performs destructive operations "
                        f"({', '.join(set(c.lower() for c in destructive_calls[:3]))}) "
                        f"without requiring explicit confirmation."
                    ),
                    impact="Accidental or unauthorized data deletion may occur without user consent.",
                    remediation=(
                        "Add a confirmation gate (user prompt, approval flag, or "
                        "human-in-the-loop check) before executing destructive operations."
                    ),
                    source_layer="heuristic",
                ))

        return findings


# ---------------------------------------------------------------------------
# PromptInjectionAnalyzer
# ---------------------------------------------------------------------------


class PromptInjectionAnalyzer(BaseHeuristicAnalyzer):
    """Detects f-strings or .format() that include user input variables directly in prompt strings."""

    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        findings: list[Finding] = []
        # Focus on files likely to contain prompts
        target_files = _relevant_files(
            files,
            {
                FileCategory.AGENT_LOGIC,
                FileCategory.PROMPT_TEMPLATE,
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
        """Check for user input interpolated into prompt strings."""
        findings: list[Finding] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            issues = self._find_prompt_injection_risks(node, content)
            for desc, lineno in issues:
                findings.append(Finding(
                    severity=Severity.HIGH,
                    category=FindingCategory.SECURITY,
                    file_path=cf.relative_path,
                    location=node.name,
                    title="Potential prompt injection via user input interpolation",
                    description=(
                        f"In function '{node.name}' at line {lineno}: {desc}"
                    ),
                    impact=(
                        "User-controlled input interpolated directly into prompts can "
                        "allow prompt injection attacks, potentially subverting agent behavior."
                    ),
                    remediation=(
                        "Sanitize user input before interpolation, use parameterized prompt "
                        "templates, or place user input in a clearly delimited section."
                    ),
                    source_layer="heuristic",
                ))

        return findings

    def _find_prompt_injection_risks(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, source: str
    ) -> list[tuple[str, int]]:
        """Find f-strings or .format() with user input variables in prompt contexts."""
        risks: list[tuple[str, int]] = []

        # Variables that likely contain user input
        user_input_names = re.compile(
            r"(user_input|user_message|user_query|user_text|message|query|input_text|user_prompt|request)"
        )

        # Prompt-related variable names that indicate the string is a prompt
        prompt_context = re.compile(
            r"(prompt|system_prompt|instruction|system_message|template)",
            re.IGNORECASE,
        )

        for node in ast.walk(func_node):
            # Check f-strings (JoinedStr nodes)
            if isinstance(node, ast.JoinedStr):
                # Check if this f-string is assigned to a prompt variable
                parent_line = node.lineno
                # Check surrounding lines for prompt context
                lines = source.splitlines()
                if 0 < parent_line <= len(lines):
                    context_line = lines[parent_line - 1]
                    if prompt_context.search(context_line):
                        # Check if any interpolated value is user input
                        for value in node.values:
                            if isinstance(value, ast.FormattedValue):
                                val_src = ast.get_source_segment(source, value)
                                if val_src and user_input_names.search(val_src):
                                    risks.append((
                                        f"User input variable interpolated into prompt via f-string",
                                        node.lineno,
                                    ))
                                    break

            # Check .format() calls on strings
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                    # Check if it's called on a prompt-related variable
                    call_src = ast.get_source_segment(source, node)
                    if call_src and prompt_context.search(call_src):
                        # Check args for user input
                        for arg in node.args:
                            arg_src = ast.get_source_segment(source, arg)
                            if arg_src and user_input_names.search(arg_src):
                                risks.append((
                                    f"User input passed to .format() on prompt string",
                                    node.lineno,
                                ))
                                break
                        for kw in node.keywords:
                            kw_src = ast.get_source_segment(source, kw.value)
                            if kw_src and user_input_names.search(kw_src):
                                risks.append((
                                    f"User input keyword passed to .format() on prompt string",
                                    node.lineno,
                                ))
                                break

        return risks
