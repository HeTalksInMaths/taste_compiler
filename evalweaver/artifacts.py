"""Logging, JSON artifact persistence, and ZIP archive building."""

import json
import os
import tempfile
import time
import zipfile
from pathlib import Path

TRACE: list[dict] = []


def log(stage: str, msg: str, status: str = "info"):
    """Log a pipeline event to trace and stdout."""
    ts = time.strftime("%H:%M:%S")
    TRACE.append({"ts": ts, "stage": stage, "status": status, "msg": msg})
    sym = {"ok": "✓", "warn": "⚠", "error": "✗"}.get(status, "·")
    print(f"[{ts}] [{stage}] {sym} {msg}")


def resolve_output_directory() -> str:
    """
    Resolve output directory with graceful fallback.
    Priority: EVALWEAVER_OUTPUT_DIR env var → ./ew_v51_outputs → tempdir.
    """
    env_dir = os.environ.get("EVALWEAVER_OUTPUT_DIR")
    if env_dir:
        try:
            os.makedirs(env_dir, exist_ok=True)
            return env_dir
        except OSError:
            log("artifacts", f"Cannot create EVALWEAVER_OUTPUT_DIR={env_dir}, falling back", "warn")

    local_dir = os.path.join(os.getcwd(), "ew_v51_outputs")
    try:
        os.makedirs(local_dir, exist_ok=True)
        return local_dir
    except OSError:
        log("artifacts", f"Cannot create {local_dir}, falling back to tempdir", "warn")

    tmp = tempfile.mkdtemp(prefix="evalweaver_")
    log("artifacts", f"Using temp directory: {tmp}", "warn")
    return tmp


def save(name: str, obj, out_dir=None):
    """Save a pipeline artifact as JSON."""
    if out_dir is None:
        out_dir = resolve_output_directory()
    path = os.path.join(out_dir, f"{name}.json")
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    return path


def build_zip_archive(out_dir: str):
    """Bundle all JSON artifacts into a ZIP archive."""
    zip_path = os.path.join(out_dir, "evalweaver_v51_outputs.zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in sorted(os.listdir(out_dir)):
                if fname.endswith(".json"):
                    zf.write(os.path.join(out_dir, fname), fname)
            # Include source script only when __file__ is defined
            try:
                import evalweaver
                src = getattr(evalweaver, "__file__", None)
                if src and os.path.exists(src):
                    zf.write(src, "evalweaver/__init__.py")
            except Exception:
                pass
        log("artifacts", f"ZIP archive: {zip_path}", "ok")
        return zip_path
    except Exception as e:
        log("artifacts", f"ZIP creation failed: {e}", "error")
        return None


def reset_trace():
    """Clear the trace log (for testing)."""
    TRACE.clear()
