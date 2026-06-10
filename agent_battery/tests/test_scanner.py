"""Unit tests for agentbattery.scanner module."""

import pytest
from pathlib import Path

from agentbattery.scanner import scan, DEFAULT_INCLUDE_GLOBS, DEFAULT_EXCLUDE_GLOBS
from agentbattery.exceptions import ScanError


class TestScanBasic:
    """Test basic scanning behavior."""

    def test_scan_finds_python_files(self, tmp_path: Path):
        """Scanner finds .py files in a temp directory."""
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def foo(): pass")

        result = scan(tmp_path)

        assert result.total_count == 2
        assert len(result.files) == 2
        names = {f.relative_path for f in result.files}
        assert "main.py" in names
        assert "utils.py" in names

    def test_scan_finds_various_file_types(self, tmp_path: Path):
        """Scanner discovers .py, .md, .yaml, .json, .toml files."""
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("[tool]")
        (tmp_path / "trace.jsonl").write_text('{"step": 1}')

        result = scan(tmp_path)

        assert result.total_count == 5
        extensions = {Path(f.relative_path).suffix for f in result.files}
        assert extensions == {".md", ".yaml", ".json", ".toml", ".jsonl"}

    def test_scan_recursive(self, tmp_path: Path):
        """Scanner discovers files in nested directories."""
        sub = tmp_path / "src" / "pkg"
        sub.mkdir(parents=True)
        (sub / "module.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1
        assert result.files[0].relative_path == str(Path("src/pkg/module.py"))

    def test_scan_records_size(self, tmp_path: Path):
        """Scanner records correct file sizes."""
        content = "hello world"
        (tmp_path / "file.py").write_text(content)

        result = scan(tmp_path)

        assert result.files[0].size_bytes == len(content)

    def test_scan_records_elapsed_time(self, tmp_path: Path):
        """Scanner records non-negative elapsed time."""
        (tmp_path / "file.py").write_text("pass")

        result = scan(tmp_path)

        assert result.elapsed_seconds >= 0

    def test_scan_total_count_equals_len_files(self, tmp_path: Path):
        """total_count matches len(files)."""
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.md").write_text("")

        result = scan(tmp_path)

        assert result.total_count == len(result.files)


class TestScanExclusions:
    """Test exclude glob behavior."""

    def test_excludes_git_directory(self, tmp_path: Path):
        """Scanner excludes .git directory contents."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")
        (git_dir / "HEAD").write_text("ref: refs/heads/main")
        (tmp_path / "main.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1
        assert result.files[0].relative_path == "main.py"

    def test_excludes_pycache(self, tmp_path: Path):
        """Scanner excludes __pycache__ directory contents."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-311.pyc").write_text("")
        (tmp_path / "module.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1

    def test_excludes_node_modules(self, tmp_path: Path):
        """Scanner excludes node_modules directory."""
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.json").write_text("{}")
        (tmp_path / "app.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1

    def test_excludes_venv(self, tmp_path: Path):
        """Scanner excludes .venv and venv directories."""
        venv1 = tmp_path / ".venv" / "lib"
        venv1.mkdir(parents=True)
        (venv1 / "site.py").write_text("")
        venv2 = tmp_path / "venv" / "lib"
        venv2.mkdir(parents=True)
        (venv2 / "site.py").write_text("")
        (tmp_path / "main.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1

    def test_excludes_egg_info(self, tmp_path: Path):
        """Scanner excludes *.egg-info directories."""
        egg = tmp_path / "mypackage.egg-info"
        egg.mkdir()
        (egg / "PKG-INFO").write_text("")
        (tmp_path / "setup.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1

    def test_custom_exclude_globs(self, tmp_path: Path):
        """Scanner respects custom exclude globs."""
        secret = tmp_path / "secrets"
        secret.mkdir()
        (secret / "keys.json").write_text("{}")
        (tmp_path / "main.py").write_text("pass")

        result = scan(tmp_path, exclude_globs=["secrets"])

        assert result.total_count == 1
        assert result.files[0].relative_path == "main.py"


class TestScanInclusions:
    """Test include glob behavior."""

    def test_ignores_non_matching_files(self, tmp_path: Path):
        """Scanner ignores files not matching include globs."""
        (tmp_path / "image.png").write_text("")
        (tmp_path / "binary.exe").write_text("")
        (tmp_path / "main.py").write_text("pass")

        result = scan(tmp_path)

        assert result.total_count == 1

    def test_custom_include_globs(self, tmp_path: Path):
        """Scanner respects custom include globs."""
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "style.css").write_text("body {}")

        result = scan(tmp_path, include_globs=["*.css"])

        assert result.total_count == 1
        assert result.files[0].relative_path == "style.css"


class TestScanErrors:
    """Test error handling."""

    def test_raises_scan_error_for_missing_path(self, tmp_path: Path):
        """Scanner raises ScanError for non-existent paths."""
        fake_path = tmp_path / "nonexistent"

        with pytest.raises(ScanError, match="does not exist"):
            scan(fake_path)

    def test_raises_scan_error_for_file_path(self, tmp_path: Path):
        """Scanner raises ScanError when target is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("hello")

        with pytest.raises(ScanError, match="not a directory"):
            scan(file_path)
