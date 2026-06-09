"""
Namespace-isolated scorer execution and pipeline orchestration.

NOTE: This module uses exec() for namespace isolation — keeping scorer code
separated from the host process namespace. This is NOT a security sandbox.
Scorer code runs with full Python capabilities within the isolated namespace.
The isolation prevents scorers from accidentally polluting each other's state.
"""

import re
import math
import statistics

# ─────────────────────────────────────────────────────────────────────
# NAMESPACE ISOLATION
# ─────────────────────────────────────────────────────────────────────

_py_ns = {}
exec("import re,math,collections,string,statistics,unicodedata", _py_ns)
_py_ns["_clamp"] = lambda x: float(max(0.0, min(1.0, float(x or 0))))


def _clamp(x):
    """Clamp a value to [0.0, 1.0]."""
    try:
        return float(max(0.0, min(1.0, float(x or 0))))
    except (TypeError, ValueError):
        return 0.0


def py_exec(code, label=""):
    """Execute code in the isolated namespace. Returns {ok, error?}."""
    try:
        exec(compile(code, f"<{label}>", "exec"), _py_ns)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def py_run_scorer(code, text, anchor):
    """
    Run a scorer function in the isolated namespace.
    Returns {ok, value, error?}.
    Value is clamped to [0.0, 1.0]; defaults to 0.5 on exception.
    """
    try:
        ns = {**_py_ns, "_text": text, "_anchor": anchor}
        wrapped = code + "\n_r = _clamp(scorer(_text,_anchor,{}))"
        exec(compile(wrapped, "<scorer>", "exec"), ns)
        return {"ok": True, "value": float(ns["_r"])}
    except Exception as e:
        return {"ok": False, "value": 0.5, "error": str(e)}


def get_namespace():
    """Return a reference to the shared namespace (for probe injection)."""
    return _py_ns
