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

## First real-model results (independent, CPU-only, reproducible)

Qwen2.5-Instruct family (Q4_K_M, llama.cpp b6100, 4 CPU threads, temperature 0,
same 250-problem exam, same oracle grading). Full per-problem reports in
`data/bench_qwen*.json`.

| Model | Overall | tool-ordering | permission-matrix | loop-detection | budget-knapsack | plan-makespan |
|---|---|---|---|---|---|---|
| 0.5B  | 4.4%  | 22% | 0%  | 0%  | 0%  | 0% |
| 1.5B  | 8.0%  | 34% | 6%  | 0%  | 0%  | 0% |
| 3B    | 18.0% | 56% | 32% | 2%  | 0%  | 0% |
| 7B    | 36.4% | 98% | 60% | 22% | 2%  | 0% |
| 14B   | 39.2% | 98% | 68% | 12% | 10% | 8% |
| random (chance) | 9.6% | 30% | 18% | — | 0% | — |

Findings (all reproducible with the commands below):

1. **Dependency understanding saturates at 7B**: tool-ordering climbs
   22% → 34% → 56% → 98% → 98% with scale — saturated from 7B onward.
2. **Numerical optimization only opens up at 14B**: budget-knapsack and
   plan-makespan stay at ≤2% through 7B, then jump to 10% / 8% at 14B —
   the "capability opening" point for exact-DP-style planning sits
   between 7B and 14B in the Qwen2.5 family.
3. **Format compliance is 100% for 1.5B+** (with the JSON schema hint in
   the system prompt): every error is a clean reasoning error,
   not a formatting artifact.

Reproduce:

```bash
./llama-server.exe -m qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf \
    -c 2048 --port 8081 --threads 4
python run_eval.py --file data/agentic_w1_250.jsonl \
    --name qwen2.5-7b-instruct-q4k_m-cpu --out eval_qwen7b.json
python -m bench.harness --file data/agentic_w1_250.jsonl --backend random
```

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
