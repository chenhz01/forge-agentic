# -*- coding: utf-8 -*-
"""bench.grader — parse a model's free-text output and grade it against truth.

Protocol: the model must answer with a single JSON object using the same
keys as problem["answer"]. Grading = structural comparison with float
tolerance. The grader never re-runs generation; truth comes from the
already-verified dataset line.
"""
import json
import math


def _eq(a, b, tol=1e-6):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b if isinstance(a, bool) and isinstance(b, bool) else False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq(a[k], b[k], tol) for k in a)
    return a == b


def extract_json(text):
    """Extract the first JSON object from model output text."""
    if not isinstance(text, str):
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def grade(problem, model_output):
    """Returns dict(passed, reason). model_output: free text or dict."""
    got = model_output if isinstance(model_output, dict) else extract_json(model_output)
    if got is None:
        return {"passed": False, "reason": "no-json"}
    truth = problem["answer"]
    if got.keys() != truth.keys():
        return {"passed": False, "reason": "key-mismatch"}
    if _eq(got, truth):
        return {"passed": True, "reason": ""}
    return {"passed": False, "reason": "value-mismatch"}
