# -*- coding: utf-8 -*-
"""bench.backends — pluggable model backends for the exam harness.

Every backend implements answer(problem) -> str (free text containing one
JSON object; bench.grader extracts and grades it).

RandomBaseline : shape-valid random guesses — measures chance level.
FirstOption    : always the first valid-looking key ("A"/first index) —
                 measures position bias.
CommandBackend : shells out to any local model CLI (e.g. llama.cpp compiled
                 with a JSON-instruction prompt). Reads prompt on stdin,
                 prints answer text on stdout. This is the hook for real
                 small-model evals without any GPU cloud account.
"""
import json
import random
import subprocess


class RandomBaseline:
    name = "random-baseline"

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def answer(self, p):
        t = p["type"]
        if t == "tool-ordering":
            return json.dumps({"valid_option": self.rng.choice("ABCD")})
        if t == "budget-knapsack":
            idx = list(range(len(p["meta"]["items"])))
            sel = sorted(self.rng.sample(idx, self.rng.randrange(1, len(idx) + 1)))
            return json.dumps({"max_value": self.rng.randrange(1, 60),
                               "selected": sel,
                               "total_cost": self.rng.randrange(1, 40)})
        if t == "loop-detection":
            loop = self.rng.random() < 0.5
            return json.dumps({"has_loop": loop,
                               "first_repeat_state": self.rng.choice(p["meta"]["trace"]) if loop else None,
                               "loop_length": self.rng.randrange(1, 6) if loop else 0})
        if t == "permission-matrix":
            allowed = self.rng.random() < 0.5
            return json.dumps({"allowed": allowed,
                               "reason_code": "ok" if allowed else "role-denied"})
        if t == "plan-makespan":
            return json.dumps({"makespan": self.rng.randrange(2, 40),
                               "critical_path": self.rng.sample(p["meta"]["tasks"], 2)})
        return json.dumps({})


class FirstOption:
    name = "first-option"

    def answer(self, p):
        t = p["type"]
        if t == "tool-ordering":
            return json.dumps({"valid_option": "A"})
        if t == "budget-knapsack":
            return json.dumps({"max_value": 1, "selected": [0], "total_cost": p["meta"]["items"][0][0]})
        if t == "loop-detection":
            return json.dumps({"has_loop": False, "first_repeat_state": None, "loop_length": 0})
        if t == "permission-matrix":
            return json.dumps({"allowed": True, "reason_code": "ok"})
        if t == "plan-makespan":
            return json.dumps({"makespan": p["meta"]["durations"]["j1"], "critical_path": ["j1"]})
        return json.dumps({})


class CommandBackend:
    name = "command"

    def __init__(self, cmd, name=None, timeout=120):
        self.cmd = cmd
        self.timeout = timeout
        if name:
            self.name = name

    def answer(self, p):
        r = subprocess.run(self.cmd, input=json.dumps(p["prompt"]),
                           capture_output=True, text=True, timeout=self.timeout)
        return r.stdout
