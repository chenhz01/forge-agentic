# -*- coding: utf-8 -*-
"""bench.harness — run a backend over a problems JSONL, produce a report.

    python -m bench.harness --file data/agentic_w1_250.jsonl --backend random
    python -m bench.harness --file data/agentic_w1_250.jsonl --backend first
    python -m bench.harness --file data/agentic_w1_250.jsonl --backend cmd --cmd "llama -m m.gguf" --name llama-qwen3-4b
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.backends import RandomBaseline, FirstOption, CommandBackend  # noqa: E402
from bench.grader import grade  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def run(backend, path):
    per_type = {}
    rows = []
    for p in load(path):
        g = grade(p, backend.answer(p))
        acc = per_type.setdefault(p["type"], [0, 0])
        acc[1] += 1
        acc[0] += 1 if g["passed"] else 0
        rows.append({"id": p["id"], "type": p["type"], "passed": g["passed"]})
    total = sum(v[1] for v in per_type.values())
    passed = sum(v[0] for v in per_type.values())
    return {"backend": backend.name, "file": path, "total": total,
            "passed": passed,
            "accuracy": round(passed / max(total, 1), 4),
            "per_type": {t: {"passed": v[0], "total": v[1],
                             "acc": round(v[0] / max(v[1], 1), 4)}
                         for t, v in sorted(per_type.items())},
            "rows": rows}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bench")
    ap.add_argument("--file", required=True)
    ap.add_argument("--backend", required=True,
                    choices=["random", "first", "cmd"])
    ap.add_argument("--cmd")
    ap.add_argument("--name")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.backend == "random":
        backend = RandomBaseline(seed=7)
    elif args.backend == "first":
        backend = FirstOption()
    else:
        if not args.cmd:
            ap.error("--cmd required for cmd backend")
        backend = CommandBackend(args.cmd, name=args.name)
    rep = run(backend, args.file)
    print("BACKEND %s  ACC %.2f%% (%d/%d)" % (rep["backend"], rep["accuracy"] * 100,
                                              rep["passed"], rep["total"]))
    for t, v in rep["per_type"].items():
        print("  %-20s %6.2f%% (%d/%d)" % (t, v["acc"] * 100, v["passed"], v["total"]))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        json.dump(rep, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("report -> %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
