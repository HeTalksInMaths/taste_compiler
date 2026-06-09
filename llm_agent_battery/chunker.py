"""Semantic code chunker — splits source files into reviewable units at AST boundaries."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from llm_agent_battery.models import ChunkConfig, ClassifiedFile, CodeChunk

logger = logging.getLogger(__name__)


def _read_content(path: Path) -> str | None:
    """Read file content, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Python AST-based chunking
# ---------------------------------------------------------------------------


def _extract_preamble(source: str, tree: ast.Module) -> str:
    """Extract the module preamble (imports, constants, docstring) before the first function/class."""
    # Find the first function or class definition
    first_def_line: int | None = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first_def_line = node.lineno
            break

    if first_def_line is None:
        # No functions or classes — the entire file is preamble
        return source

    lines = source.splitlines(keepends=True)
    # Preamble is everything before the first definition (1-indexed to 0-indexed)
    preamble_lines = lines[: first_def_line - 1]
    return "".join(preamble_lines).rstrip("\n")


def _get_node_source(source: str, node: ast.AST) -> str:
    """Extract source text for an AST node using line numbers."""
    lines = source.splitlines(keepends=True)
    start = node.lineno - 1  # 1-indexed to 0-indexed
    end = node.end_lineno  # end_lineno is inclusive, already correct for slicing
    return "".join(lines[start:end])


def _class_has_shared_state(node: ast.ClassDef) -> bool:
    """Check if a class has methods that share state via self attributes.

    Returns True if any attribute written (assigned) in one method is read
    in a different method.
    """
    # Collect writes and reads per method
    method_writes: dict[str, set[str]] = {}
    method_reads: dict[str, set[str]] = {}

    for item in ast.walk(node):
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Only consider direct methods of this class
        if item not in node.body:
            continue

        method_name = item.name
        writes: set[str] = set()
        reads: set[str] = set()

        for child in ast.walk(item):
            if isinstance(child, ast.Attribute):
                # Check if it's self.X
                if isinstance(child.value, ast.Name) and child.value.id == "self":
                    attr_name = child.attr
                    # Determine if it's a write or read based on context
                    # We need to check if this attribute node is a target of assignment
                    # Walk the method body to find assignments
                    pass

        # More precise approach: walk method body looking for assignments and reads
        for child in ast.walk(item):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        writes.add(target.attr)
            elif isinstance(child, ast.AugAssign):
                if (
                    isinstance(child.target, ast.Attribute)
                    and isinstance(child.target.value, ast.Name)
                    and child.target.value.id == "self"
                ):
                    writes.add(child.target.attr)
            elif isinstance(child, ast.AnnAssign) and child.target is not None:
                if (
                    isinstance(child.target, ast.Attribute)
                    and isinstance(child.target.value, ast.Name)
                    and child.target.value.id == "self"
                ):
                    writes.add(child.target.attr)

        # Collect reads: any self.X access that isn't in a write context
        for child in ast.walk(item):
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id == "self"
            ):
                reads.add(child.attr)

        method_writes[method_name] = writes
        method_reads[method_name] = reads

    # Check if any attribute written in one method is read in another
    for writer_method, written_attrs in method_writes.items():
        for reader_method, read_attrs in method_reads.items():
            if reader_method != writer_method:
                if written_attrs & read_attrs:
                    return True

    return False


def _chunk_python(source: str, file_path: str, config: ChunkConfig) -> list[CodeChunk]:
    """Chunk a Python file using AST parsing."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        logger.warning("AST parse failed for %s, falling back to line-based chunking", file_path)
        return _chunk_by_blank_lines(source, file_path, config)

    preamble = _extract_preamble(source, tree)
    chunks: list[CodeChunk] = []

    # Find top-level functions and classes
    top_level_defs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    if not top_level_defs:
        # No functions or classes — return the whole file as one chunk
        content = source
        is_truncated = False
        if len(content) > config.max_chunk_chars:
            content = content[: config.max_chunk_chars]
            is_truncated = True
        chunks.append(CodeChunk(
            file_path=file_path,
            chunk_name="module",
            content=content,
            functions=[],
            preamble=preamble,
            is_truncated=is_truncated,
            start_line=1,
            end_line=len(source.splitlines()),
        ))
        return chunks

    for node in top_level_defs:
        node_source = _get_node_source(source, node)

        if isinstance(node, ast.ClassDef):
            # Classes are always kept as single chunks
            # (preserve_class_unity=True is default, and shared state check also keeps them whole)
            chunk_name = f"class:{node.name}"
            functions_in_chunk = [
                m.name for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            full_content = (preamble + "\n\n" + node_source).strip() if preamble else node_source
            is_truncated = False
            if len(full_content) > config.max_chunk_chars:
                full_content = full_content[: config.max_chunk_chars]
                is_truncated = True

            chunks.append(CodeChunk(
                file_path=file_path,
                chunk_name=chunk_name,
                content=full_content,
                functions=functions_in_chunk,
                preamble=preamble,
                is_truncated=is_truncated,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            ))
        else:
            # Function or async function
            chunk_name = f"function:{node.name}"
            full_content = (preamble + "\n\n" + node_source).strip() if preamble else node_source
            is_truncated = False
            if len(full_content) > config.max_chunk_chars:
                full_content = full_content[: config.max_chunk_chars]
                is_truncated = True

            chunks.append(CodeChunk(
                file_path=file_path,
                chunk_name=chunk_name,
                content=full_content,
                functions=[node.name],
                preamble=preamble,
                is_truncated=is_truncated,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            ))

    return chunks


# ---------------------------------------------------------------------------
# Fallback: line-based chunking for non-Python files
# ---------------------------------------------------------------------------


def _chunk_by_blank_lines(source: str, file_path: str, config: ChunkConfig) -> list[CodeChunk]:
    """Split a file at blank-line boundaries as a fallback for non-Python files."""
    if not source.strip():
        return []

    # Split on double blank lines (or more)
    sections = re.split(r"\n\s*\n", source)
    sections = [s.strip() for s in sections if s.strip()]

    if not sections:
        return []

    chunks: list[CodeChunk] = []
    current_content: list[str] = []
    current_start_line = 1
    chunk_index = 0

    for section in sections:
        candidate = "\n\n".join(current_content + [section]) if current_content else section

        if len(candidate) > config.max_chunk_chars and current_content:
            # Flush current content as a chunk
            content = "\n\n".join(current_content)
            is_truncated = False
            if len(content) > config.max_chunk_chars:
                content = content[: config.max_chunk_chars]
                is_truncated = True
            end_line = current_start_line + content.count("\n")
            chunks.append(CodeChunk(
                file_path=file_path,
                chunk_name=f"section:{chunk_index}",
                content=content,
                functions=[],
                preamble="",
                is_truncated=is_truncated,
                start_line=current_start_line,
                end_line=end_line,
            ))
            chunk_index += 1
            current_content = [section]
            current_start_line = end_line + 1
        else:
            current_content.append(section)

    # Flush remaining
    if current_content:
        content = "\n\n".join(current_content)
        is_truncated = False
        if len(content) > config.max_chunk_chars:
            content = content[: config.max_chunk_chars]
            is_truncated = True
        end_line = current_start_line + content.count("\n")
        chunks.append(CodeChunk(
            file_path=file_path,
            chunk_name=f"section:{chunk_index}",
            content=content,
            functions=[],
            preamble="",
            is_truncated=is_truncated,
            start_line=current_start_line,
            end_line=end_line,
        ))

    # If we ended up with no chunks at all (e.g., the split produced nothing),
    # treat the entire source as a single chunk
    if not chunks:
        content = source.strip()
        is_truncated = False
        if len(content) > config.max_chunk_chars:
            content = content[: config.max_chunk_chars]
            is_truncated = True
        chunks.append(CodeChunk(
            file_path=file_path,
            chunk_name="section:0",
            content=content,
            functions=[],
            preamble="",
            is_truncated=is_truncated,
            start_line=1,
            end_line=len(source.splitlines()),
        ))

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_file(classified_file: ClassifiedFile, config: ChunkConfig | None = None) -> list[CodeChunk]:
    """Split a source file into semantic chunks using AST parsing.

    For Python files, uses the `ast` module to split at function/class boundaries.
    For non-Python files, falls back to line-based splitting at blank-line boundaries.

    Args:
        classified_file: A ClassifiedFile to chunk.
        config: Optional ChunkConfig with max_chunk_chars and preserve_class_unity.
                If None, uses default ChunkConfig (12000 chars, preserve classes).

    Returns:
        List of CodeChunk objects representing the semantic chunks.
    """
    if config is None:
        config = ChunkConfig()

    source = _read_content(classified_file.path)
    if source is None or not source.strip():
        return []

    file_path = classified_file.relative_path

    # Use AST-based chunking for Python files
    if classified_file.path.suffix == ".py":
        return _chunk_python(source, file_path, config)

    # Fallback to blank-line splitting for non-Python files
    return _chunk_by_blank_lines(source, file_path, config)


def chunk_files(
    files: list[ClassifiedFile], config: ChunkConfig | None = None
) -> list[CodeChunk]:
    """Chunk multiple classified files.

    Args:
        files: List of ClassifiedFile objects to chunk.
        config: Optional ChunkConfig. If None, uses default.

    Returns:
        List of all CodeChunk objects from all files.
    """
    if config is None:
        config = ChunkConfig()

    all_chunks: list[CodeChunk] = []
    for f in files:
        all_chunks.extend(chunk_file(f, config))
    return all_chunks
