# -*- coding: utf-8 -*-
"""forge.plan-makespan — parallel task-plan makespan (DAG critical path).

Problem: N tasks with durations and precedence constraints (an edge [a, b]
means task a can only start after task b finishes). Machines are unlimited
and every task runs in parallel as soon as its predecessors are done, so the
minimum total completion time (makespan) equals the weight of the longest
(weighted) path through the DAG.

Verification re-derives the longest path from meta["durations"]/meta["edges"]
and accepts ANY critical path whose adjacent pairs (later, earlier) are real
edges, whose durations sum to the recomputed makespan, and whose tasks are
unique.
"""
import random

from .common import make_id, int_knob, knob

TYPE = "plan-makespan"


def _longest_path(tasks, durations, edges):
    """Longest weighted path in the DAG. edges: (a, b) -> a depends on b.

    Returns (makespan, path) with path in execution order: each adjacent
    pair (path[i + 1], path[i]) is an edge (path[i + 1] depends on path[i]).
    """
    pred = {}
    for a, b in edges:
        pred.setdefault(a, []).append(b)
    memo = {}
    best_pred = {}

    def dist(t):
        if t not in memo:
            best, bp = 0, None
            for b in pred.get(t, []):
                d = dist(b)
                if d > best:
                    best, bp = d, b
            memo[t] = best + int(durations[t])
            best_pred[t] = bp
        return memo[t]

    makespan = max(dist(t) for t in tasks)
    sink = next(t for t in tasks if dist(t) == makespan)
    chain = []
    cur = sink
    while cur is not None:
        chain.append(cur)
        cur = best_pred[cur]
    chain.reverse()
    return makespan, chain


def generate(seed, difficulty=0.5):
    rng = random.Random("plan-makespan|%d" % seed)
    n = int_knob(difficulty, 4, 9)
    tasks = ["j%d" % (i + 1) for i in range(n)]
    durations = {t: rng.randint(1, 9) for t in tasks}
    density = knob(difficulty, 0.3, 0.7)
    # task i may depend on any earlier-indexed task -> guaranteed DAG
    edges = []
    for i in range(1, n):
        cand = list(range(i))
        rng.shuffle(cand)
        chosen = set()
        for b in cand:
            if rng.random() < density:
                chosen.add(b)
        if not chosen:  # keep the graph connected: force one incoming edge
            chosen.add(rng.randrange(i))
        for b in sorted(chosen):
            edges.append((tasks[i], tasks[b]))
    edges = sorted(set(edges))

    makespan, path = _longest_path(tasks, durations, edges)

    dur_txt = ", ".join("%s=%d" % (t, durations[t]) for t in tasks)
    dep_txt = "; ".join("%s must start after %s finishes" % (a, b)
                        for a, b in edges)
    problem = {
        "id": make_id(TYPE, seed),
        "type": TYPE,
        "difficulty": float(difficulty),
        "seed": int(seed),
        "prompt": ("Tasks with durations: %s. Dependencies: %s. Machines are "
                   "unlimited and every task starts as soon as its "
                   "dependencies finish. What is the minimum total completion "
                   "time (makespan), and give one critical path (tasks in "
                   "execution order)?"
                   % (dur_txt, dep_txt)),
        "answer": {"makespan": makespan, "critical_path": list(path)},
        "solution": ("The longest chain %s sums to %d, so no schedule can "
                     "finish earlier: the makespan is %d."
                     % (" -> ".join(path), makespan, makespan)),
        "meta": {"tasks": tasks,
                 "durations": {t: durations[t] for t in tasks},
                 "edges": [[a, b] for a, b in edges]},
    }
    return problem


def verify(problem):
    try:
        meta = problem["meta"]
        tasks = list(meta["tasks"])
        durations = dict(meta["durations"])
        edges = [(a, b) for a, b in meta["edges"]]
        makespan, _ = _longest_path(tasks, durations, edges)
        if problem["answer"]["makespan"] != makespan:
            return False
        path = list(problem["answer"]["critical_path"])
        if not path or len(set(path)) != len(path):
            return False
        if any(t not in durations for t in path):
            return False
        if sum(int(durations[t]) for t in path) != makespan:
            return False
        eset = set(edges)
        return all((path[i + 1], path[i]) in eset
                   for i in range(len(path) - 1))
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def self_cases():
    import copy
    cases = []
    for sd in range(5):
        cases.append(("gen-deterministic-%d" % sd,
                      lambda sd=sd: generate(sd, 0.5) == generate(sd, 0.5)))
    for d in (0.0, 0.25, 0.5, 0.75, 1.0):
        cases.append(("verify-true-d%.2f" % d,
                      lambda d=d: verify(generate(321 + int(d * 100), d))))
    base = generate(11, 0.5)
    p = copy.deepcopy(base)
    p["answer"]["makespan"] += 1
    cases.append(("verify-false-makespan-plus1", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["makespan"] -= 1
    cases.append(("verify-false-makespan-minus1", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["critical_path"][0] = "jX"
    cases.append(("verify-false-illegal-task", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    crit = base["answer"]["critical_path"]
    p["meta"]["durations"][crit[0]] += 1
    cases.append(("verify-false-duration-tampered", lambda p=p: verify(p) is False))
    from .common import schema_ok
    cases.append(("schema-ok", lambda: schema_ok(generate(42, 0.3))))
    cases.append(("validity-helper-chain",
                  lambda: _longest_path(
                      ["j1", "j2", "j3", "j4"],
                      {"j1": 2, "j2": 3, "j3": 4, "j4": 5},
                      [("j2", "j1"), ("j3", "j2"), ("j4", "j3")])
                  == (14, ["j1", "j2", "j3", "j4"])))
    return cases
