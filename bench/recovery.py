# -*- coding: utf-8 -*-
"""bench.recovery — interruption-and-recovery harness (three arms, same budget).

Measures what planning files buy across the transition the exam harness never
exercises: stop an episode halfway, discard the conversation, start a fresh
session, and compare whether the planning file helps phase 2.

Arms (same model/task by construction; call budget: B and C make the same
number of phase-2 calls per problem — C's extra phase-1 ledger calls mirror
A's pre-interruption calls, so no arm gets extra answering compute):
  A  uninterrupted baseline: one session answers the whole episode.
  B  interruption, fresh session WITHOUT planning files answers phase 2.
  C  interruption, fresh session WITH planning files (phase-1 ledger written
     by the interrupted session) answers phase 2.

Recovery gain = acc(C) - acc(B) on phase 2. For content-blind backends
(random / first) the expected result is parity — that is the harness sanity
check; the signal case is a CommandBackend (LLM) run, where B and C can
diverge because the planning text reaches the model via the prompt.

Planning files: written by the *interrupted* session from its own answers
(what it did, not the ground truth — an agent never sees truth at runtime).
Injection: phase-2 problems are passed with the planning text prepended to
`prompt`; content-blind backends ignore prompt text, CommandBackend reads it
on stdin, so the same runner serves both without special-casing.

Run:
  python -m bench.recovery --file data/agentic_w1_250.jsonl --backend random \
      --episodes 25 --per-episode 8 [--out recovery_report.json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.backends import RandomBaseline, FirstOption, CommandBackend  # noqa: E402
from bench.grader import grade  # noqa: E402

PLANNING_HEADER = (
    "## Planning notes from your previous session (conversation was lost)\n"
    "Below is what you did and concluded before the interruption. "
    "Use it to resume the remaining tasks.\n"
)

def load(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)

def make_backend(kind, cmd, name, seed):
    if kind == "random":
        return RandomBaseline(seed=seed)
    if kind == "first":
        return FirstOption()
    return CommandBackend(cmd, name=name)

def planning_file(rows):
    """Phase-1 ledger from the interrupted session's own answers (no truth)."""
    lines = [PLANNING_HEADER]
    for p, ans in rows:
        lines.append("- [%s] %s\n  answered: %s" % (p["type"], p["id"], ans))
    return "\n".join(lines)

def run_arm(backend_factory, episode, with_planning, planning_text=""):
    """Answer every problem in the episode; grade; return per-problem rows."""
    rows, ledger = [], []
    for p in episode:
        q = p
        if with_planning:
            q = dict(p)
            q["prompt"] = planning_text + "\n\n" + p["prompt"]
        ans = backend_factory().answer(q)  # fresh call = fresh context, no memory
        g = grade(p, ans)
        rows.append({"id": p["id"], "type": p["type"], "passed": g["passed"]})
        ledger.append((p, ans))
    return rows, ledger

def run_episode(backend_kind, cmd, name, seed, episode):
    half = len(episode) // 2
    phase1, phase2 = episode[:half], episode[half:]

    # Arm A — uninterrupted: same backend session answers phase1+phase2.
    a_rows, _ = run_arm(lambda: make_backend(backend_kind, cmd, name, seed), episode, False)

    # Arm B — interruption, fresh session, NO planning files.
    b_rows, _ = run_arm(lambda: make_backend(backend_kind, cmd, name, seed), phase2, False)

    # Arm C — interruption, fresh session, WITH planning files from phase 1.
    _, p1_ledger = run_arm(lambda: make_backend(backend_kind, cmd, name, seed), phase1, False)
    plan = planning_file(p1_ledger)
    c_rows, _ = run_arm(lambda: make_backend(backend_kind, cmd, name, seed), phase2, True, plan)

    def acc(rows):
        return round(sum(1 for r in rows if r["passed"]) / max(len(rows), 1), 4)

    return {"arm_a_acc": acc(a_rows), "arm_b_acc": acc(b_rows), "arm_c_acc": acc(c_rows),
            "phase2_n": len(phase2), "recovery_gain": round(acc(c_rows) - acc(b_rows), 4),
            "planning_chars": len(plan), "rows": {"A": a_rows, "B": b_rows, "C": c_rows}}

def main(argv=None):
    ap = argparse.ArgumentParser(prog="recovery")
    ap.add_argument("--file", required=True)
    ap.add_argument("--backend", required=True, choices=["random", "first", "cmd"])
    ap.add_argument("--cmd")
    ap.add_argument("--name")
    ap.add_argument("--episodes", type=int, default=25)
    ap.add_argument("--per-episode", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    problems = list(load(args.file))
    need = args.episodes * args.per_episode
    if len(problems) < need:
        print("need %d problems, file has %d" % (need, len(problems)))
        return 2
    episodes = [problems[i * args.per_episode:(i + 1) * args.per_episode]
                for i in range(args.episodes)]

    eps, calls = [], 0
    for i, ep in enumerate(episodes):
        r = run_episode(args.backend, args.cmd, args.name, args.seed, ep)
        calls += len(ep) + len(r["rows"]["B"]) + len(r["rows"]["C"]) * 2  # A + B + (C含phase1台账轮)
        eps.append(r)
        print("episode %02d: A=%.4f B=%.4f C=%.4f gain=%+.4f"
              % (i, r["arm_a_acc"], r["arm_b_acc"], r["arm_c_acc"], r["recovery_gain"]))

    def mean(key):
        return round(sum(e[key] for e in eps) / len(eps), 4)

    report = {"backend": args.name or args.backend, "file": args.file,
              "episodes": len(eps), "per_episode": args.per_episode,
              "arm_a_acc": mean("arm_a_acc"), "arm_b_acc": mean("arm_b_acc"),
              "arm_c_acc": mean("arm_c_acc"),
              "recovery_gain_mean": mean("recovery_gain"),
              "backend_calls": calls,
              "budget_note": "B and C make the same number of phase-2 calls per "
                             "problem; C's phase-1 ledger calls mirror A's "
                             "pre-interruption calls",
              "sanity_note": "content-blind backends must show B==C parity; "
                             "divergence requires a prompt-sensitive (cmd/LLM) backend",
              "episode_details": eps}
    print("=== recovery summary: A=%.4f B=%.4f C=%.4f  recovery_gain=%+.4f  (%d backend calls)"
          % (report["arm_a_acc"], report["arm_b_acc"], report["arm_c_acc"],
             report["recovery_gain_mean"], calls))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
