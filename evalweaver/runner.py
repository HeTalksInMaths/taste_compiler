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
    Returns {ok, raw_value, value, out_of_range, error}.

    - raw_value: the actual float before clamping (None on exception)
    - value: clamped to [0.0, 1.0] (0.5 on exception)
    - out_of_range: True if raw_value < -0.01 or raw_value > 1.01
    - error: None on success, str on exception
    """
    try:
        ns = {**_py_ns, "_text": text, "_anchor": anchor}
        # Execute scorer and capture raw value before clamping
        wrapped = code + "\n_raw_r = scorer(_text,_anchor,{})\n_r = _clamp(_raw_r)"
        exec(compile(wrapped, "<scorer>", "exec"), ns)
        raw_value = float(ns["_raw_r"])
        clamped_value = float(ns["_r"])
        out_of_range = raw_value < -0.01 or raw_value > 1.01
        return {
            "ok": True,
            "raw_value": raw_value,
            "value": clamped_value,
            "out_of_range": out_of_range,
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "raw_value": None,
            "value": 0.5,
            "out_of_range": False,
            "error": str(e),
        }


def get_namespace():
    """Return a reference to the shared namespace (for probe injection)."""
    return _py_ns
