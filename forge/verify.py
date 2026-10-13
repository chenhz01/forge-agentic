# -*- coding: utf-8 -*-
"""forge.verify — solver-side grading entry point (grading authority)."""
import json

from . import MODULES


def verdict(problem):
    v = {"id": problem.get("id", "?"), "type": problem.get("type", "?"),
         "passed": False, "reason": ""}
    m = MODULES.get(problem.get("type"))
    if m is None:
        v["reason"] = "unknown-type"
        return v
    try:
        v["passed"] = bool(m.verify(problem))
        v["reason"] = "" if v["passed"] else "verify-returned-false"
    except Exception as exc:  # grading must never crash the pipeline
        v["reason"] = "exception:%s" % exc.__class__.__name__
    return v


def grade_file(path):
    total = passed = 0
    failures = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            v = verdict(json.loads(line))
            if v["passed"]:
                passed += 1
            else:
                failures.append(v)
    return total, passed, failures
