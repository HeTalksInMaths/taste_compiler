"""Unit tests for the semantic chunker module."""

from pathlib import Path

import pytest

from llm_agent_battery.chunker import chunk_file, chunk_files
from llm_agent_battery.models import ChunkConfig, ClassifiedFile, FileCategory


def _make_classified_file(tmp_path: Path, filename: str, content: str) -> ClassifiedFile:
    """Helper to create a ClassifiedFile from content written to tmp_path."""
    filepath = tmp_path / filename
    filepath.write_text(content, encoding="utf-8")
    return ClassifiedFile(
        path=filepath,
        relative_path=filename,
        size_bytes=len(content.encode("utf-8")),
        primary_category=FileCategory.AGENT_LOGIC,
    )


class TestChunkFileBasic:
    """Basic chunking functionality tests."""

    def test_empty_file_returns_no_chunks(self, tmp_path: Path) -> None:
        """Empty files produce no chunks."""
        cf = _make_classified_file(tmp_path, "empty.py", "")
        chunks = chunk_file(cf)
        assert chunks == []

    def test_whitespace_only_file_returns_no_chunks(self, tmp_path: Path) -> None:
        """Files with only whitespace produce no chunks."""
        cf = _make_classified_file(tmp_path, "blank.py", "   \n\n  \n")
        chunks = chunk_file(cf)
        assert chunks == []

    def test_single_function_file(self, tmp_path: Path) -> None:
        """A file with one function produces one chunk."""
        source = "import os\n\ndef hello():\n    print('hello')\n"
        cf = _make_classified_file(tmp_path, "one_func.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert chunks[0].chunk_name == "function:hello"
        assert "hello" in chunks[0].functions
        assert "import os" in chunks[0].preamble

    def test_multiple_functions_produce_multiple_chunks(self, tmp_path: Path) -> None:
        """A file with multiple functions produces one chunk per function."""
        source = "import sys\n\ndef foo():\n    pass\n\ndef bar():\n    pass\n"
        cf = _make_classified_file(tmp_path, "multi.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 2
        assert chunks[0].chunk_name == "function:foo"
        assert chunks[1].chunk_name == "function:bar"

    def test_class_produces_single_chunk(self, tmp_path: Path) -> None:
        """A class is kept as a single chunk."""
        source = (
            "import logging\n\n"
            "class MyService:\n"
            "    def __init__(self):\n"
            "        self.data = []\n\n"
            "    def add(self, item):\n"
            "        self.data.append(item)\n\n"
            "    def get(self):\n"
            "        return self.data\n"
        )
        cf = _make_classified_file(tmp_path, "service.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert chunks[0].chunk_name == "class:MyService"
        assert "__init__" in chunks[0].functions
        assert "add" in chunks[0].functions
        assert "get" in chunks[0].functions

    def test_default_config_used_when_none(self, tmp_path: Path) -> None:
        """When config is None, default ChunkConfig is used."""
        source = "def f():\n    pass\n"
        cf = _make_classified_file(tmp_path, "def.py", source)
        chunks = chunk_file(cf, config=None)
        assert len(chunks) == 1


class TestChunkFilePreamble:
    """Tests for preamble preservation."""

    def test_preamble_includes_imports(self, tmp_path: Path) -> None:
        """Preamble contains import statements."""
        source = "import os\nimport sys\n\ndef main():\n    pass\n"
        cf = _make_classified_file(tmp_path, "imports.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert "import os" in chunks[0].preamble
        assert "import sys" in chunks[0].preamble

    def test_preamble_includes_constants(self, tmp_path: Path) -> None:
        """Preamble contains module-level constants."""
        source = "import os\n\nMAX_SIZE = 100\nDEFAULT_NAME = 'test'\n\ndef process():\n    pass\n"
        cf = _make_classified_file(tmp_path, "constants.py", source)
        chunks = chunk_file(cf)
        assert "MAX_SIZE = 100" in chunks[0].preamble
        assert "DEFAULT_NAME" in chunks[0].preamble

    def test_preamble_on_each_chunk(self, tmp_path: Path) -> None:
        """Each chunk from a module gets the same preamble."""
        source = "from pathlib import Path\n\nX = 42\n\ndef a():\n    pass\n\ndef b():\n    pass\n"
        cf = _make_classified_file(tmp_path, "multi_preamble.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 2
        for chunk in chunks:
            assert "from pathlib import Path" in chunk.preamble
            assert "X = 42" in chunk.preamble

    def test_preamble_in_content(self, tmp_path: Path) -> None:
        """The chunk content includes the preamble prepended to the function source."""
        source = "import math\n\ndef compute():\n    return math.pi\n"
        cf = _make_classified_file(tmp_path, "content.py", source)
        chunks = chunk_file(cf)
        assert "import math" in chunks[0].content
        assert "def compute():" in chunks[0].content

    def test_file_with_no_preamble(self, tmp_path: Path) -> None:
        """A file starting with a function has empty preamble."""
        source = "def immediate():\n    return 1\n"
        cf = _make_classified_file(tmp_path, "no_preamble.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert chunks[0].preamble == ""


class TestChunkFileClassSharedState:
    """Tests for class shared-state detection."""

    def test_class_with_shared_state_stays_unified(self, tmp_path: Path) -> None:
        """A class where one method writes self.X and another reads it stays as one chunk."""
        source = (
            "class Cache:\n"
            "    def __init__(self):\n"
            "        self.store = {}\n\n"
            "    def put(self, key, val):\n"
            "        self.store[key] = val\n\n"
            "    def get(self, key):\n"
            "        return self.store.get(key)\n"
        )
        cf = _make_classified_file(tmp_path, "cache.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert chunks[0].chunk_name == "class:Cache"

    def test_class_without_shared_state_still_unified(self, tmp_path: Path) -> None:
        """A class without shared state is still kept as one chunk (preserve_class_unity default)."""
        source = (
            "class Utilities:\n"
            "    @staticmethod\n"
            "    def add(a, b):\n"
            "        return a + b\n\n"
            "    @staticmethod\n"
            "    def multiply(a, b):\n"
            "        return a * b\n"
        )
        cf = _make_classified_file(tmp_path, "utils.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert chunks[0].chunk_name == "class:Utilities"


class TestChunkFileMaxSize:
    """Tests for max_chunk_chars enforcement."""

    def test_oversized_function_is_truncated(self, tmp_path: Path) -> None:
        """A function exceeding max_chunk_chars is marked is_truncated=True."""
        # Create a function that exceeds the max chunk size
        body = "    x = 1\n" * 100  # ~1000 chars
        source = f"def big_func():\n{body}"
        config = ChunkConfig(max_chunk_chars=200)
        cf = _make_classified_file(tmp_path, "big.py", source)
        chunks = chunk_file(cf, config=config)
        assert len(chunks) == 1
        assert chunks[0].is_truncated is True
        assert len(chunks[0].content) <= 200

    def test_small_function_not_truncated(self, tmp_path: Path) -> None:
        """A function within max_chunk_chars is not truncated."""
        source = "def small():\n    return 1\n"
        config = ChunkConfig(max_chunk_chars=12000)
        cf = _make_classified_file(tmp_path, "small.py", source)
        chunks = chunk_file(cf, config=config)
        assert len(chunks) == 1
        assert chunks[0].is_truncated is False

    def test_oversized_class_is_truncated(self, tmp_path: Path) -> None:
        """A class exceeding max_chunk_chars is marked is_truncated=True."""
        methods = "\n".join(
            f"    def method_{i}(self):\n        return {i}\n" for i in range(50)
        )
        source = f"class BigClass:\n{methods}"
        config = ChunkConfig(max_chunk_chars=500)
        cf = _make_classified_file(tmp_path, "bigclass.py", source)
        chunks = chunk_file(cf, config=config)
        assert len(chunks) == 1
        assert chunks[0].is_truncated is True
        assert len(chunks[0].content) <= 500


class TestChunkFileLineNumbers:
    """Tests for start_line and end_line tracking."""

    def test_single_function_line_numbers(self, tmp_path: Path) -> None:
        """Line numbers match the function's position in the file."""
        source = "import os\n\ndef hello():\n    print('hi')\n"
        cf = _make_classified_file(tmp_path, "lines.py", source)
        chunks = chunk_file(cf)
        assert chunks[0].start_line == 3
        assert chunks[0].end_line == 4

    def test_multiple_functions_line_numbers(self, tmp_path: Path) -> None:
        """Each function chunk has correct line numbers."""
        source = "def a():\n    pass\n\ndef b():\n    pass\n"
        cf = _make_classified_file(tmp_path, "multi_lines.py", source)
        chunks = chunk_file(cf)
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 2
        assert chunks[1].start_line == 4
        assert chunks[1].end_line == 5


class TestChunkFileNonPython:
    """Tests for non-Python file chunking (line-based fallback)."""

    def test_javascript_file_uses_line_based_chunking(self, tmp_path: Path) -> None:
        """Non-Python files fall back to blank-line splitting."""
        source = "const x = 1;\nconst y = 2;\n\n\nfunction hello() {\n  return 'hi';\n}\n"
        cf = _make_classified_file(tmp_path, "app.js", source)
        chunks = chunk_file(cf)
        assert len(chunks) >= 1
        # Should have section-based names
        assert all("section:" in c.chunk_name for c in chunks)

    def test_yaml_file_chunking(self, tmp_path: Path) -> None:
        """YAML files are chunked by blank lines."""
        source = "key1: value1\nkey2: value2\n\n\nkey3: value3\nkey4: value4\n"
        cf = _make_classified_file(tmp_path, "config.yaml", source)
        chunks = chunk_file(cf)
        assert len(chunks) >= 1

    def test_non_python_empty_returns_no_chunks(self, tmp_path: Path) -> None:
        """Empty non-Python files return no chunks."""
        cf = _make_classified_file(tmp_path, "empty.js", "")
        chunks = chunk_file(cf)
        assert chunks == []

    def test_non_python_max_chunk_respected(self, tmp_path: Path) -> None:
        """Non-Python files also respect max_chunk_chars."""
        # Create a large section
        source = "a = 1\n" * 200
        config = ChunkConfig(max_chunk_chars=100)
        cf = _make_classified_file(tmp_path, "big.js", source)
        chunks = chunk_file(cf, config=config)
        for chunk in chunks:
            assert len(chunk.content) <= 100


class TestChunkFileEdgeCases:
    """Edge case tests."""

    def test_file_with_only_imports(self, tmp_path: Path) -> None:
        """A file with only imports and no definitions produces one chunk."""
        source = "import os\nimport sys\n\nX = 42\n"
        cf = _make_classified_file(tmp_path, "imports_only.py", source)
        chunks = chunk_file(cf)
        # No top-level defs, so the whole file becomes one chunk
        assert len(chunks) == 1
        assert chunks[0].chunk_name == "module"

    def test_syntax_error_falls_back_to_line_based(self, tmp_path: Path) -> None:
        """Python files with syntax errors fall back to line-based chunking."""
        source = "def broken(\n    # missing close paren\n    pass\n"
        cf = _make_classified_file(tmp_path, "broken.py", source)
        chunks = chunk_file(cf)
        # Should still produce chunks via fallback
        assert len(chunks) >= 1
        assert "section:" in chunks[0].chunk_name

    def test_async_function_handled(self, tmp_path: Path) -> None:
        """Async functions are chunked the same as regular functions."""
        source = "import asyncio\n\nasync def fetch():\n    await asyncio.sleep(1)\n"
        cf = _make_classified_file(tmp_path, "async_mod.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 1
        assert chunks[0].chunk_name == "function:fetch"
        assert "fetch" in chunks[0].functions

    def test_mixed_functions_and_classes(self, tmp_path: Path) -> None:
        """Files with both functions and classes produce correct chunks."""
        source = (
            "import os\n\n"
            "def helper():\n"
            "    pass\n\n"
            "class Worker:\n"
            "    def run(self):\n"
            "        pass\n\n"
            "def cleanup():\n"
            "    pass\n"
        )
        cf = _make_classified_file(tmp_path, "mixed.py", source)
        chunks = chunk_file(cf)
        assert len(chunks) == 3
        assert chunks[0].chunk_name == "function:helper"
        assert chunks[1].chunk_name == "class:Worker"
        assert chunks[2].chunk_name == "function:cleanup"

    def test_nonexistent_file_returns_no_chunks(self, tmp_path: Path) -> None:
        """A file that doesn't exist on disk returns no chunks."""
        cf = ClassifiedFile(
            path=tmp_path / "missing.py",
            relative_path="missing.py",
            size_bytes=0,
            primary_category=FileCategory.AGENT_LOGIC,
        )
        chunks = chunk_file(cf)
        assert chunks == []


class TestChunkFiles:
    """Tests for the batch chunk_files() function."""

    def test_chunk_files_empty_list(self) -> None:
        """Empty input list produces empty output."""
        chunks = chunk_files([])
        assert chunks == []

    def test_chunk_files_multiple_files(self, tmp_path: Path) -> None:
        """Multiple files produce chunks from all files."""
        cf1 = _make_classified_file(tmp_path, "a.py", "def a():\n    pass\n")
        cf2 = _make_classified_file(tmp_path, "b.py", "def b():\n    pass\n")
        chunks = chunk_files([cf1, cf2])
        assert len(chunks) == 2
        names = [c.chunk_name for c in chunks]
        assert "function:a" in names
        assert "function:b" in names

    def test_chunk_files_respects_config(self, tmp_path: Path) -> None:
        """Config is passed through to individual file chunking."""
        body = "    x = 1\n" * 50
        source = f"def big():\n{body}"
        cf = _make_classified_file(tmp_path, "big.py", source)
        config = ChunkConfig(max_chunk_chars=100)
        chunks = chunk_files([cf], config=config)
        assert len(chunks) == 1
        assert chunks[0].is_truncated is True
        assert len(chunks[0].content) <= 100

    def test_chunk_files_file_path_preserved(self, tmp_path: Path) -> None:
        """Each chunk has the correct file_path set."""
        cf1 = _make_classified_file(tmp_path, "x.py", "def x():\n    pass\n")
        cf2 = _make_classified_file(tmp_path, "y.py", "def y():\n    pass\n")
        chunks = chunk_files([cf1, cf2])
        assert chunks[0].file_path == "x.py"
        assert chunks[1].file_path == "y.py"
