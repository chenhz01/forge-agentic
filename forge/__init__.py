# -*- coding: utf-8 -*-
"""forge-agentic: verifiable agent-planning task generators.

Domain: agentic AI planning & governance (tool ordering, budgets, loops,
permissions, schedules). Solver-graded, contamination-proof by construction.
"""
MODULES = {}
for _name in ("tool_ordering", "budget_knapsack", "loop_detection",
              "permission_matrix", "plan_makespan"):
    try:
        _m = __import__("forge." + _name, fromlist=["x"])
        MODULES[_m.TYPE] = _m
    except ImportError:
        pass
