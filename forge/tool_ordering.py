# -*- coding: utf-8 -*-
"""forge.tool-ordering — reference implementation.

Problem: an agent must call tools respecting dependency constraints (a tool
may only run after the tools it depends on). Four candidate execution orders
are given; exactly one is dependency-valid.

Verification re-derives validity of every option from meta["deps"] and
confirms exactly one option is valid and it matches the answer.
"""
import random

from .common import make_id, int_knob

TYPE = "tool-ordering"


def _valid(order, deps):
    pos = {t: i for i, t in enumerate(order)}
    return all(pos[b] < pos[a] for a, b in deps)


def generate(seed, difficulty=0.5):
    rng = random.Random("tool-ordering|%d" % seed)
    n = int_knob(difficulty, 4, 8)
    tools = ["t%d" % (i + 1) for i in range(n)]
    # deps: tool i may depend on any earlier-indexed tool -> guaranteed DAG
    m = int_knob(difficulty, 1, n - 1)
    deps = []
    for i in range(1, n):
        if rng.random() < 0.55 or i <= m:
            b = rng.randrange(i)
            deps.append((tools[i], tools[b]))
    deps = sorted(set(deps))
    # one valid order: the identity order (works because deps go late->early)
    valid_order = list(tools)
    # three GUARANTEED-invalid orders, built from an actual dependency:
    # deps[i] = (a, b) means a must run AFTER b (pos[b] < pos[a]).
    # any order violating that is invalid, so:
    #   v1: move b to just after a   -> pos[b] > pos[a]  (violates)
    #   v2: move a to just before b  -> pos[a] < pos[b]  (violates)
    #   v3: full reversal            -> every dep violated
    a0, b0 = deps[0]
    v1 = [t for t in valid_order if t != b0]
    v1.insert(v1.index(a0) + 1, b0)
    v2 = [t for t in valid_order if t != a0]
    v2.insert(v2.index(b0), a0)
    v3 = list(reversed(valid_order))
    invalid = []
    seen = {tuple(valid_order)}
    for cand in (v1, v2, v3):
        if tuple(cand) not in seen and not _valid(cand, deps):
            invalid.append(cand)
            seen.add(tuple(cand))
    attempts = 0
    while len(invalid) < 3 and attempts < 500:
        attempts += 1
        cand = list(valid_order)
        rng.shuffle(cand)
        if tuple(cand) not in seen and not _valid(cand, deps):
            invalid.append(cand)
            seen.add(tuple(cand))
    if len(invalid) < 3:  # pragma: no cover
        raise RuntimeError("could not build 3 invalid orders for seed %d" % seed)
    options = [valid_order] + invalid
    labels = ["A", "B", "C", "D"]
    perm = list(range(4))
    rng.shuffle(perm)
    shuffled = {labels[i]: options[perm[i]] for i in range(4)}
    correct = [lab for lab, o in shuffled.items() if _valid(o, deps)]
    if len(correct) != 1:  # pragma: no cover
        raise RuntimeError("shuffle produced %d valid options" % len(correct))

    dep_txt = "; ".join("%s must run after %s" % (a, b) for a, b in deps)
    opt_txt = "\n".join("%s: %s" % (lab, " -> ".join(o)) for lab, o in sorted(shuffled.items()))
    problem = {
        "id": make_id(TYPE, seed),
        "type": TYPE,
        "difficulty": float(difficulty),
        "seed": int(seed),
        "prompt": ("An agent plans tool calls with dependencies: %s. Which of "
                   "the four execution orders is dependency-valid?\n%s"
                   % (dep_txt, opt_txt)),
        "answer": {"valid_option": correct[0]},
        "solution": ("Checking every option against the dependency list, only "
                     "%s satisfies all %d constraints." % (correct[0], len(deps))),
        "meta": {"tools": tools,
                 "deps": [[a, b] for a, b in deps],
                 "options": shuffled},
    }
    return problem


def verify(problem):
    try:
        deps = [(a, b) for a, b in problem["meta"]["deps"]]
        opts = problem["meta"]["options"]
        valid = sorted(lab for lab, o in opts.items() if _valid(list(o), deps))
        return (len(valid) == 1
                and problem["answer"]["valid_option"] == valid[0])
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
    base = generate(7, 0.5)
    p = copy.deepcopy(base)
    p["answer"]["valid_option"] = next(l for l in "ABCD" if l != base["answer"]["valid_option"])
    cases.append(("verify-false-wrong-option", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"].pop("valid_option")
    cases.append(("verify-false-missing-answer", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["meta"]["deps"].append([p["meta"]["tools"][0], p["meta"]["tools"][-1]])
    cases.append(("verify-false-tampered-deps", lambda p=p: verify(p) is False))
    cases.append(("structure-exactly-one-valid",
                  lambda: len({l for l, o in base["meta"]["options"].items()
                               if _valid(list(o), [tuple(d) for d in base["meta"]["deps"]])}) == 1))
    from .common import schema_ok
    cases.append(("schema-ok", lambda: schema_ok(generate(42, 0.3))))
    cases.append(("validity-helper", lambda: _valid(["a", "b"], []) and not _valid(["b", "a"], [("b", "a")])))
    return cases
