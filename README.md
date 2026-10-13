# forge-agentic

Verifiable **agent-planning** task generators — procedurally produced
problems about tool ordering, budgets, execution loops, permissions and
schedules, where every answer is re-derived and graded by deterministic
solvers. No LLM ever grades an answer.

Sibling of [scireason-forge](https://github.com/chenhz01/scireason-forge)
and part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox)
suite.

## Why agent benchmarks need this

Public agent benchmarks are static — and increasingly contaminated: they
leak into training corpora and stop measuring anything. Every problem here
is **procedurally generated from a seed** with a difficulty knob, so a fresh
exam can be regenerated at any moment, and every answer is re-derived from
the problem statement by an exact solver (graph algorithms, dynamic
programming, policy evaluation, cycle detection) — never by another model.

## Task types (W1: 5 types, 250 problems; W2: 100k pool)

| Type | What it drills | Grading authority |
|---|---|---|
| `tool-ordering` | Dependency-valid tool call ordering | Topological validity check |
| `budget-knapsack` | Tool selection under a token budget | 0/1 knapsack DP optimum |
| `loop-detection` | Cycle detection in execution traces | First-repeat replay |
| `permission-matrix` | RBAC + clearance boundary decisions | Policy re-evaluation |
| `plan-makespan` | Parallel-plan critical path | DAG longest-path DP |

## Quickstart

```bash
git clone https://github.com/chenhz01/forge-agentic
cd forge-agentic
python cli.py generate --type all --per-type 50 --seed0 1000 --out data/w1.jsonl
python cli.py grade --file data/w1.jsonl            # SUMMARY: 250/250 passed
python self_test.py                                 # SUMMARY: PASS 162/162
# fresh exam, never seen before:
python cli.py generate --type all --per-type 50 --seed0 999999 --out data/fresh.jsonl
# run the exam harness (plug any model CLI):
python -m bench.harness --file data/w1.jsonl --backend random
python -m bench.harness --file data/w1.jsonl --backend cmd --cmd "your-model-cli" --name my-model
```

## Contamination-proof guarantees (data/contamination_proof.txt)

- 12,500 sampled problems across 5 types: **0 duplicate ids**
- same seed → byte-identical problem (regeneration is exact)
- unseen seed range → brand-new exam, on demand

## The exam harness

Models answer in free text; `bench/grader.py` extracts the JSON object and
grades it structurally against the verified ground truth (never by string
match, never by another model). Baselines included: `random` (chance level,
≈10%) and `first-option` (position bias). Plug a real model via
`CommandBackend` — any CLI that reads a prompt on stdin and prints an
answer works, e.g. a llama.cpp process. Baseline reports ship in
`data/bench_*.json`.

## Data card (datasheet)

- **Distribution**: 50 problems per type in W1; difficulties uniformly
  spread over [0,1]; W2 pool = 20,000 per type (100k total), seeds 100000+.
- **Language**: English prompts, JSON answers.
- **Intended use**: RLVR-style reward source, model evaluation, and
  solver-graded fine-tuning curricula for small agents.
- **Not intended for**: open-ended dialogue quality assessment.
- **Provenance**: fully procedural; no human- or model-written exam text.

## Verification principle

`verify(problem)` **never trusts** `problem["answer"]`. It re-derives the
answer from `problem["meta"]` (the construction truth) using exact
algorithms, then compares. Corrupt any answer field and grading fails.

## When NOT to use

- You need open-ended agentic dialogue quality scoring (these tasks are
  closed-form by design).
- You need frontier-model evaluation (scores saturate; the exam targets
  small models ≤31B).

## License & contact

MIT — © zhengming contributors. Developer tooling, not professional advice.
Contact: hcac4735@agent.qq.com
