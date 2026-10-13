# -*- coding: utf-8 -*-
"""forge.permission-matrix — agent tool-permission boundary decisions.

Domain: RBAC + minimum clearance levels. A role-based matrix says which tools
each role may call; every tool also carries a minimum clearance. A query is a
triple (role, tool, param level) plus the agent's clearance; the verdict is
decided by a fixed-priority rule chain (unknown-role > unknown-tool >
role-denied > clearance-denied > ok).

Verification re-runs the same rule chain from meta and compares both the
allowed flag and the reason code with the answer.
"""
import random

from .common import make_id, int_knob, knob, pick

TYPE = "permission-matrix"

ALL_ROLES = ("admin", "analyst", "operator", "auditor", "guest")


def _judge(role, tool, level, clearance, roles, tools, matrix, min_clearance):
    if role not in roles:
        return "unknown-role"
    if tool not in tools:
        return "unknown-tool"
    if tool not in matrix.get(role, []):
        return "role-denied"
    mc = min_clearance[tool]
    if level > mc:
        if clearance < mc:
            return "clearance-denied"
        return "ok"  # high-clearance agent may elevate the param
    return "ok"


def generate(seed, difficulty=0.5):
    rng = random.Random("permission-matrix|%d" % seed)
    n = int_knob(difficulty, 4, 7)
    tools = ["t%d" % (i + 1) for i in range(n)]
    # roles: admin always present (it is the all-allowed anchor), 3-5 total
    others = [r for r in ALL_ROLES if r != "admin"]
    k = rng.randrange(3, 6)
    roles = sorted(["admin"] + rng.sample(others, k - 1))
    # matrix: admin fully allowed; every other role gets a random subset that
    # is neither empty nor complete (so role-denied stays reachable)
    p_allow = knob(difficulty, 0.4, 0.8)
    matrix = {"admin": list(tools)}
    for r in roles:
        if r == "admin":
            continue
        allowed = [t for t in tools if rng.random() < p_allow]
        if not allowed:
            allowed = [pick(rng, tools)]
        if len(allowed) == len(tools):
            allowed.pop(rng.randrange(len(tools)))
        matrix[r] = sorted(allowed)
    # min clearance per tool; higher difficulty -> more constrained tools
    clear_prob = knob(difficulty, 0.15, 0.75)
    min_clearance = {}
    for t in tools:
        min_clearance[t] = pick(rng, (2, 3)) if rng.random() < clear_prob else 1
    # query: resample (same rng stream) until at least 3 distinct verdicts
    # have shown up, so no reason code dominates the dataset
    t_extra = "t%d" % (n + 1)
    seen = set()
    for _ in range(50):
        q_role = pick(rng, ALL_ROLES)
        q_tool = pick(rng, tools + [t_extra])
        q_level = pick(rng, (1, 2, 3))
        agent_clearance = pick(rng, (1, 2, 3))
        seen.add(_judge(q_role, q_tool, q_level, agent_clearance,
                        roles, tools, matrix, min_clearance))
        if len(seen) >= 3:
            break
    reason = _judge(q_role, q_tool, q_level, agent_clearance,
                    roles, tools, matrix, min_clearance)
    mat_txt = "\n".join("  %s: %s" % (r, ", ".join(matrix[r])) for r in roles)
    clr_txt = ", ".join("%s:%d" % (t, min_clearance[t]) for t in tools)
    problem = {
        "id": make_id(TYPE, seed),
        "type": TYPE,
        "difficulty": float(difficulty),
        "seed": int(seed),
        "prompt": ("Access-control decision for an agent tool call. "
                   "Role -> allowed tools:\n%s\nMinimum clearance per tool: %s.\n"
                   "Rules (first match wins): role outside the role list -> "
                   "unknown-role; tool outside the tool list -> unknown-tool; "
                   "tool not allowed for the role -> role-denied; param level "
                   "above the tool minimum while the agent clearance is below "
                   "it -> clearance-denied; param level above the minimum with "
                   "clearance >= minimum -> ok (elevation allowed); otherwise "
                   "-> ok.\nQuery: role '%s' with clearance %d calls tool '%s' "
                   "with param level %d. Reply with {\"allowed\": bool, "
                   "\"reason_code\": str}."
                   % (mat_txt, clr_txt, q_role, agent_clearance, q_tool, q_level)),
        "answer": {"allowed": reason == "ok", "reason_code": reason},
        "solution": ("Applying the priority rules to (role=%s, tool=%s, "
                     "level=%d, clearance=%d) yields reason_code '%s', hence "
                     "allowed=%s."
                     % (q_role, q_tool, q_level, agent_clearance, reason,
                        str(reason == "ok").lower())),
        "meta": {"roles": roles,
                 "tools": tools,
                 "matrix": matrix,
                 "min_clearance": min_clearance,
                 "query": {"role": q_role, "tool": q_tool, "level": q_level},
                 "agent_clearance": agent_clearance},
    }
    return problem


def verify(problem):
    try:
        meta = problem["meta"]
        q = meta["query"]
        reason = _judge(q["role"], q["tool"], q["level"],
                        meta["agent_clearance"], meta["roles"],
                        meta["tools"], meta["matrix"], meta["min_clearance"])
        allowed = reason == "ok"
        return (problem["answer"]["allowed"] == allowed
                and problem["answer"]["reason_code"] == reason)
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
    p["answer"]["allowed"] = not base["answer"]["allowed"]
    cases.append(("verify-false-flipped-allowed", lambda p=p: verify(p) is False))
    p = copy.deepcopy(base)
    p["answer"]["reason_code"] = "renamed-code"
    cases.append(("verify-false-renamed-reason", lambda p=p: verify(p) is False))

    def _level_tamper():
        # find a seed where changing query.level flips the verdict
        for sd in range(11, 40):
            b = generate(sd, 0.6)
            meta = b["meta"]
            q = meta["query"]
            old = _judge(q["role"], q["tool"], q["level"],
                         meta["agent_clearance"], meta["roles"],
                         meta["tools"], meta["matrix"], meta["min_clearance"])
            for lvl in (1, 2, 3):
                if lvl == q["level"]:
                    continue
                new = _judge(q["role"], q["tool"], lvl,
                             meta["agent_clearance"], meta["roles"],
                             meta["tools"], meta["matrix"], meta["min_clearance"])
                if new != old:
                    p2 = copy.deepcopy(b)
                    p2["meta"]["query"]["level"] = lvl
                    return verify(p2) is False
        return False
    cases.append(("verify-false-tampered-level", _level_tamper))
    cases.append(("structure-admin-all-allowed",
                  lambda: "admin" in base["meta"]["roles"]
                          and base["meta"]["matrix"]["admin"]
                          == base["meta"]["tools"]))
    from .common import schema_ok
    cases.append(("schema-ok", lambda: schema_ok(generate(42, 0.3))))
    cases.append(("judge-helper",
                  lambda: _judge("ghost", "t1", 1, 1, ["admin"], ["t1"],
                                 {"admin": ["t1"]}, {"t1": 1}) == "unknown-role"
                          and _judge("admin", "t9", 1, 1, ["admin"], ["t1"],
                                     {"admin": ["t1"]}, {"t1": 1}) == "unknown-tool"))
    return cases
