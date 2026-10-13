# -*- coding: utf-8 -*-
"""forge.budget-knapsack — budget-constrained tool selection (0/1 knapsack).

Problem: an agent has a compute/cost budget B and n candidate tools, each
with a cost and a value. Choose the subset of tools whose total cost stays
within budget and whose total value is maximal (classic 0/1 knapsack).

Verification re-derives the optimum via DP from meta["items"]/meta["budget"]
and accepts ANY subset that is optimal and internally consistent with the
answer fields (no duplicates, ascending, cost <= budget, values match).
"""
import random

from .common import make_id, int_knob, knob, schema_ok

TYPE = "budget-knapsack"


def _optimum(costs, values, budget):
    """DP over the standard 0/1 knapsack; returns the best achievable value."""
    dp = [0] * (budget + 1)
    for c, v in zip(costs, values):
        for b in range(budget, c - 1, -1):
            cand = dp[b - c] + v
            if cand > dp[b]:
                dp[b] = cand
    return dp[budget]


def _solve(costs, values, budget, rng):
    """Return (optimum, one optimal subset as an ascending index list).

    Ties inside the DP backtrace are broken deterministically via rng.
    """
    n = len(costs)
    dp = [[0] * (budget + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        c, v = costs[i - 1], values[i - 1]
        prev, cur = dp[i - 1], dp[i]
        for b in range(budget + 1):
            cur[b] = prev[b]
            if b >= c and prev[b - c] + v > cur[b]:
                cur[b] = prev[b - c] + v
    optimum = dp[n][budget]
    selected = []
    b = budget
    for i in range(n, 0, -1):
        if dp[i][b] == dp[i - 1][b]:
            continue  # item i-1 not needed here
        take = True
        c, v = costs[i - 1], values[i - 1]
        if not (b >= c and dp[i - 1][b - c] + v == dp[i][b]):
            take = False  # pragma: no cover
        elif dp[i - 1][b] == dp[i][b] and rng.random() < 0.5:
            take = False  # tie: deterministically skip via rng
        if take:
            selected.append(i - 1)
            b -= c
    selected.reverse()
    return optimum, selected


def generate(seed, difficulty=0.5):
    rng = random.Random("budget-knapsack|%d" % seed)
    n = int_knob(difficulty, 4, 8)
    # re-draw the whole instance until the budget genuinely binds:
    # not everything fits, and at least one tool fits.
    for _ in range(50):
        costs = [rng.randrange(1, 21) for _ in range(n)]
        values = [rng.randrange(1, 51) for _ in range(n)]
        budget = int(sum(costs) * knob(difficulty, 0.35, 0.6))
        if sum(costs) > budget and min(costs) <= budget:
            break
    optimum, selected = _solve(costs, values, budget, rng)
    total_cost = sum(costs[i] for i in selected)
    items_txt = "\n".join("  tool %d: cost=%d, value=%d" % (i, costs[i], values[i])
                          for i in range(n))
    sel_txt = ", ".join("tool %d (cost=%d, value=%d)" % (i, costs[i], values[i])
                        for i in selected)
    problem = {
        "id": make_id(TYPE, seed),
        "type": TYPE,
        "difficulty": float(difficulty),
        "seed": int(seed),
        "prompt": ("An agent has a budget of %d and %d candidate tools:\n%s\n"
                   "Which tools should it select so the total cost stays within "
                   "budget and the total value is maximized? Reply with the "
                   "maximum total value and the ascending list of selected tool "
                   "indices." % (budget, n, items_txt)),
        "answer": {"max_value": optimum,
                   "selected": selected,
                   "total_cost": total_cost},
        "solution": ("Running a 0/1 knapsack DP over the %d tools with budget %d "
                     "gives a maximum total value of %d, e.g. by selecting: %s "
                     "(total cost %d)." % (n, budget, optimum, sel_txt, total_cost)),
        "meta": {"items": [[costs[i], values[i]] for i in range(n)],
                 "budget": budget},
    }
    return problem


def verify(problem):
    try:
        items = problem["meta"]["items"]
        budget = problem["meta"]["budget"]
        if not isinstance(budget, int) or budget < 0:
            return False
        costs = [int(c) for c, _ in items]
        values = [int(v) for _, v in items]
        optimum = _optimum(costs, values, budget)
        ans = problem["answer"]
        selected = ans["selected"]
        # subset must be a strict ascending list of distinct valid indices
        if not isinstance(selected, list) or len(selected) == 0:
            return False
        if any(not isinstance(i, int) for i in selected):
            return False
        if any(a >= b for a, b in zip(selected, selected[1:])):
            return False
        if selected[0] < 0 or selected[-1] >= len(items):
            return False
        total_cost = sum(costs[i] for i in selected)
        total_value = sum(values[i] for i in selected)
        return (total_cost <= budget
                and total_value == optimum
                and ans["max_value"] == optimum
                and ans["total_cost"] == total_cost)
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
                      lambda d=d: verify(generate(123 + int(d * 100), d))))
    base = generate(7, 0.5)
    p = copy.deepcopy(base)
    p["answer"]["max_value"] += 1
    cases.append(("verify-false-inflated-value", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["selected"] = sorted(p["answer"]["selected"] + [p["answer"]["selected"][0]])
    cases.append(("verify-false-duplicate-index", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["total_cost"] += 1
    cases.append(("verify-false-wrong-total-cost", lambda p=p: verify(p) is False))
    cases.append(("schema-ok", lambda: schema_ok(generate(42, 0.3))))
    cases.append(("structure-budget-binds",
                  lambda: sum(c for c, _ in base["meta"]["items"]) > base["meta"]["budget"]
                  and min(c for c, _ in base["meta"]["items"]) <= base["meta"]["budget"]))
    return cases
