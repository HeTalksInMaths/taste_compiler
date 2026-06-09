"""Unit tests for the file scanner module."""

from pathlib import Path

import pytest

from llm_agent_battery.models import ScanConfig
from llm_agent_battery.scanner import scan


class TestScanBasic:
    """Basic scanner functionality tests."""

    def test_scan_empty_directory(self, tmp_path: Path) -> None:
        """Scanner returns empty results for an empty directory."""
        result = scan(tmp_path)
        assert result.total_count == 0
        assert result.files == []
        assert result.warnings == []
        assert result.elapsed_seconds >= 0

    def test_scan_discovers_python_files(self, tmp_path: Path) -> None:
        """Scanner discovers Python files by default."""
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def helper(): pass")

        result = scan(tmp_path)
        assert result.total_count == 2
        rel_paths = {f.relative_path for f in result.files}
        assert "main.py" in rel_paths
        assert "utils.py" in rel_paths

    def test_scan_discovers_multiple_file_types(self, tmp_path: Path) -> None:
        """Scanner discovers various supported file types."""
        (tmp_path / "app.py").write_text("# python")
        (tmp_path / "index.ts").write_text("// typescript")
        (tmp_path / "main.js").write_text("// javascript")
        (tmp_path / "server.go").write_text("// go")
        (tmp_path / "lib.rs").write_text("// rust")
        (tmp_path / "config.yaml").write_text("key: val")
        (tmp_path / "data.json").write_text("{}")

        result = scan(tmp_path)
        assert result.total_count == 7

    def test_scan_uses_default_config_when_none(self, tmp_path: Path) -> None:
        """When config is None, scanner uses default ScanConfig."""
        (tmp_path / "test.py").write_text("x = 1")
        result = scan(tmp_path, config=None)
        assert result.total_count == 1


class TestScanExcludeGlobs:
    """Tests for exclude glob filtering."""

    def test_scan_excludes_git_directory(self, tmp_path: Path) -> None:
        """Scanner skips .git directories."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("gitconfig")
        (tmp_path / "app.py").write_text("# code")

        result = scan(tmp_path)
        assert result.total_count == 1
        assert all(".git" not in f.relative_path for f in result.files)

    def test_scan_excludes_node_modules(self, tmp_path: Path) -> None:
        """Scanner skips node_modules directories."""
        nm_dir = tmp_path / "node_modules" / "pkg"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.js").write_text("module.exports = {}")
        (tmp_path / "app.js").write_text("// app")

        result = scan(tmp_path)
        assert result.total_count == 1
        assert result.files[0].relative_path == "app.js"

    def test_scan_excludes_pycache(self, tmp_path: Path) -> None:
        """Scanner skips __pycache__ directories."""
        cache_dir = tmp_path / "src" / "__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "module.cpython-311.pyc").write_text("")
        (tmp_path / "src" / "module.py").write_text("# module")

        result = scan(tmp_path)
        assert result.total_count == 1
        assert result.files[0].relative_path == "src/module.py"

    def test_scan_excludes_venv(self, tmp_path: Path) -> None:
        """Scanner skips .venv and venv directories."""
        venv_dir = tmp_path / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "site.py").write_text("")
        venv2_dir = tmp_path / "venv" / "lib"
        venv2_dir.mkdir(parents=True)
        (venv2_dir / "site.py").write_text("")
        (tmp_path / "app.py").write_text("# app")

        result = scan(tmp_path)
        assert result.total_count == 1

    def test_scan_excludes_agentbattery(self, tmp_path: Path) -> None:
        """Scanner skips .agentbattery directories."""
        ab_dir = tmp_path / ".agentbattery"
        ab_dir.mkdir()
        (ab_dir / "report.json").write_text("{}")
        (tmp_path / "main.py").write_text("# main")

        result = scan(tmp_path)
        assert result.total_count == 1

    def test_scan_custom_exclude_globs(self, tmp_path: Path) -> None:
        """Scanner respects custom exclude globs."""
        (tmp_path / "keep.py").write_text("# keep")
        (tmp_path / "skip.py").write_text("# skip")

        config = ScanConfig(exclude_globs=["skip.*"])
        result = scan(tmp_path, config=config)
        assert result.total_count == 1
        assert result.files[0].relative_path == "keep.py"


class TestScanIncludeGlobs:
    """Tests for include glob filtering."""

    def test_scan_only_includes_matching_files(self, tmp_path: Path) -> None:
        """Scanner only returns files matching include globs."""
        (tmp_path / "code.py").write_text("# python")
        (tmp_path / "readme.md").write_text("# readme")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")

        result = scan(tmp_path)
        rel_paths = {f.relative_path for f in result.files}
        assert "code.py" in rel_paths
        assert "readme.md" not in rel_paths
        assert "image.png" not in rel_paths

    def test_scan_custom_include_globs(self, tmp_path: Path) -> None:
        """Scanner respects custom include globs."""
        (tmp_path / "app.py").write_text("# python")
        (tmp_path / "readme.md").write_text("# readme")

        config = ScanConfig(include_globs=["*.md"])
        result = scan(tmp_path, config=config)
        assert result.total_count == 1
        assert result.files[0].relative_path == "readme.md"


class TestScanOversizedFiles:
    """Tests for oversized file handling."""

    def test_scan_skips_oversized_files_with_warning(self, tmp_path: Path) -> None:
        """Scanner skips files exceeding max size and records a warning."""
        small_file = tmp_path / "small.py"
        small_file.write_text("x = 1")

        big_file = tmp_path / "big.py"
        big_file.write_bytes(b"x" * (500 * 1024 + 1))

        result = scan(tmp_path)
        assert result.total_count == 1
        assert result.files[0].relative_path == "small.py"
        assert len(result.warnings) == 1
        assert "big.py" in result.warnings[0].file_path
        assert "exceeds max size" in result.warnings[0].reason

    def test_scan_file_at_exact_max_size_is_included(self, tmp_path: Path) -> None:
        """Scanner includes files at exactly the max size limit."""
        exact_file = tmp_path / "exact.py"
        exact_file.write_bytes(b"x" * (500 * 1024))

        result = scan(tmp_path)
        assert result.total_count == 1
        assert len(result.warnings) == 0

    def test_scan_custom_max_size(self, tmp_path: Path) -> None:
        """Scanner respects custom max_file_size_bytes."""
        (tmp_path / "small.py").write_text("x = 1")
        (tmp_path / "medium.py").write_bytes(b"x" * 200)

        config = ScanConfig(max_file_size_bytes=100)
        result = scan(tmp_path, config=config)
        assert result.total_count == 1
        assert result.files[0].relative_path == "small.py"
        assert len(result.warnings) == 1


class TestScanRecursive:
    """Tests for recursive directory traversal."""

    def test_scan_discovers_nested_files(self, tmp_path: Path) -> None:
        """Scanner discovers files in nested directories."""
        nested = tmp_path / "src" / "lib"
        nested.mkdir(parents=True)
        (nested / "utils.py").write_text("# utils")
        (tmp_path / "main.py").write_text("# main")

        result = scan(tmp_path)
        assert result.total_count == 2
        rel_paths = {f.relative_path for f in result.files}
        assert "main.py" in rel_paths
        assert "src/lib/utils.py" in rel_paths

    def test_scan_relative_paths_are_relative_to_target(self, tmp_path: Path) -> None:
        """Relative paths are relative to the target directory."""
        sub = tmp_path / "project" / "src"
        sub.mkdir(parents=True)
        (sub / "app.py").write_text("# app")

        result = scan(tmp_path / "project")
        assert result.files[0].relative_path == "src/app.py"


class TestScanErrors:
    """Tests for error handling."""

    def test_scan_nonexistent_directory_raises(self, tmp_path: Path) -> None:
        """Scanner raises FileNotFoundError for non-existent target."""
        with pytest.raises(FileNotFoundError):
            scan(tmp_path / "nonexistent")

    def test_scan_file_as_target_raises(self, tmp_path: Path) -> None:
        """Scanner raises NotADirectoryError when target is a file."""
        f = tmp_path / "file.txt"
        f.write_text("text")
        with pytest.raises(NotADirectoryError):
            scan(f)


class TestScanTiming:
    """Tests for elapsed time tracking."""

    def test_scan_reports_positive_elapsed_seconds(self, tmp_path: Path) -> None:
        """Scanner reports non-negative elapsed_seconds."""
        (tmp_path / "a.py").write_text("# a")
        result = scan(tmp_path)
        assert result.elapsed_seconds >= 0
