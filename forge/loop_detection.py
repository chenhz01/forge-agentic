# -*- coding: utf-8 -*-
"""forge.loop-detection — agent execution-trace loop detection.

Problem: an agent's execution trace over a finite state space is given.
Scanning left to right, the FIRST time a state repeats an earlier state
marks the loop: first_repeat_state is that state and loop_length is the
gap between the repeat and its first occurrence. No repeat means no loop.

Verification re-derives all three fields from meta["trace"] with the same
detection rule and compares them against the answer field by field.
"""
import random

from .common import make_id, int_knob, knob

TYPE = "loop-detection"


def _detect(trace):
    """First-repeat scan: left to right, first state seen before."""
    seen = {}
    for i, s in enumerate(trace):
        if s in seen:
            return {"has_loop": True,
                    "first_repeat_state": s,
                    "loop_length": i - seen[s]}
        seen[s] = i
    return {"has_loop": False, "first_repeat_state": None, "loop_length": 0}


def generate(seed, difficulty=0.5):
    rng = random.Random("loop-detection|%d" % seed)
    S = int_knob(difficulty, 3, 8)
    L = int_knob(difficulty, 6, 24)
    states = ["s%d" % (i + 1) for i in range(S)]
    trace = [states[rng.randrange(S)] for _ in range(L)]
    # force a repeated position with probability knob(difficulty, 0.3, 0.8):
    # pick i < j and overwrite trace[j] with trace[i]
    if rng.random() < knob(difficulty, 0.3, 0.8) and L >= 2:
        i = rng.randrange(L - 1)
        j = rng.randrange(i + 1, L)
        trace[j] = trace[i]
    answer = _detect(trace)

    problem = {
        "id": make_id(TYPE, seed),
        "type": TYPE,
        "difficulty": float(difficulty),
        "seed": int(seed),
        "prompt": ("An agent walks through a state space and its execution "
                   "trace is:\n%s\nScan left to right and report: has_loop "
                   "(bool), first_repeat_state (the state or null), and "
                   "loop_length (current index minus first-occurrence index, "
                   "0 if no loop)."
                   % (" -> ".join(trace))),
        "answer": {"has_loop": answer["has_loop"],
                   "first_repeat_state": answer["first_repeat_state"],
                   "loop_length": answer["loop_length"]},
        "solution": ("Scanning left to right, the first state that repeats an "
                     "earlier occurrence determines the answer: %s"
                     % ("state %s repeats after %d steps."
                        % (answer["first_repeat_state"], answer["loop_length"])
                        if answer["has_loop"]
                        else "no state ever repeats, so has_loop is false and "
                             "loop_length is 0.")),
        "meta": {"trace": list(trace), "n_states": S},
    }
    return problem


def _state_eq(a, b):
    if a is None or b is None:
        return a is None and b is None
    return a == b


def verify(problem):
    try:
        expected = _detect(list(problem["meta"]["trace"]))
        got = problem["answer"]
        return (got["has_loop"] == expected["has_loop"]
                and _state_eq(got["first_repeat_state"],
                              expected["first_repeat_state"])
                and got["loop_length"] == expected["loop_length"])
    except (KeyError, TypeError, ValueError):
        return False


def self_cases():
    import copy
    cases = []
    for sd in range(5):
        cases.append(("gen-deterministic-%d" % sd,
                      lambda sd=sd: generate(sd, 0.5) == generate(sd, 0.5)))
    for d in (0.0, 0.25, 0.5, 0.75, 1.0):
        cases.append(("verify-true-d%.2f" % d,
                      lambda d=d: verify(generate(123 + int(d * 100), d))))
    seed_loop = next(s for s in range(100) if generate(s, 0.5)["answer"]["has_loop"])
    base = generate(seed_loop, 0.5)
    p = copy.deepcopy(base)
    p["answer"]["has_loop"] = not base["answer"]["has_loop"]
    cases.append(("verify-false-flip-has-loop", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["loop_length"] = base["answer"]["loop_length"] + 1
    cases.append(("verify-false-loop-length-plus", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["loop_length"] = max(0, base["answer"]["loop_length"] - 1)
    cases.append(("verify-false-loop-length-minus", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["first_repeat_state"] = "sX"
    cases.append(("verify-false-renamed-state", lambda p=p: verify(p) is False))
    from .common import schema_ok
    cases.append(("schema-ok", lambda: schema_ok(generate(42, 0.3))))
    cases.append(("helper-acyclic-trace",
                  lambda: _detect(["s1", "s2", "s3"]) == {"has_loop": False,
                                                          "first_repeat_state": None,
                                                          "loop_length": 0}))
    cases.append(("helper-adjacent-repeat",
                  lambda: _detect(["s1", "s1"]) == {"has_loop": True,
                                                    "first_repeat_state": "s1",
                                                    "loop_length": 1}))
    return cases
