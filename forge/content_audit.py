# -*- coding: utf-8 -*-
"""forge.content_audit — content-level duplicate audit for generated problem sets.

Why: problem IDs are derived from (task_type, seed), so "0 duplicate ids" only
proves regeneration determinism. It does NOT establish that task *content* is
free of duplication (two different seeds can yield near-identical prompts, and
published benchmark items can leak in). This auditor inspects the prompts
themselves:

  1. exact duplicates  — sha1 of whitespace/punctuation-normalized prompt
  2. near duplicates   — 5-token shingle Jaccard >= threshold (pure stdlib)

It is an *intra-dataset* audit; cross-benchmark contamination needs an
external reference set (future work, see README note).

Run:  python -m forge.content_audit --file data/agentic_w1_250.jsonl [--jaccard 0.8]
Exit code 0 = no exact dups and no near-dups at threshold; 1 = findings.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

_norm_re = re.compile(r"[^a-z0-9 ]+")

def normalize(text):
    return _norm_re.sub(" ", " ".join(str(text).lower().split()))

def shingles(text, k=5):
    toks = normalize(text).split()
    if len(toks) < k:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)}

def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)

def load_problems(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)

def audit(path, jaccard_threshold=0.8, shingle_k=5):
    rows = list(load_problems(path))
    exact = defaultdict(list)
    sigs = []
    for p in rows:
        n = normalize(p["prompt"])
        exact[hashlib.sha1(n.encode("utf-8")).hexdigest()].append(p["id"])
        sigs.append((p["id"], p["type"], shingles(p["prompt"], shingle_k)))

    exact_dups = {h: ids for h, ids in exact.items() if len(ids) > 1}

    near = []
    for i in range(len(sigs)):
        id_i, t_i, s_i = sigs[i]
        for j in range(i + 1, len(sigs)):
            id_j, t_j, s_j = sigs[j]
            # cross-type shingle overlap is expected noise; only flag same-type pairs
            if t_i != t_j:
                continue
            d = jaccard(s_i, s_j)
            if d >= jaccard_threshold:
                near.append((round(d, 4), id_i, id_j))

    hist = {}
    for th in (0.6, 0.7, 0.8, 0.9):
        hist[th] = sum(1 for i in range(len(sigs)) for j in range(i + 1, len(sigs))
                       if sigs[i][1] == sigs[j][1] and jaccard(sigs[i][2], sigs[j][2]) >= th)

    return {"file": path, "problems": len(rows), "exact_dup_groups": exact_dups,
            "near_dups": sorted(near, reverse=True), "pair_histogram": hist,
            "threshold": jaccard_threshold}

def main(argv=None):
    ap = argparse.ArgumentParser(prog="content-audit")
    ap.add_argument("--file", required=True)
    ap.add_argument("--jaccard", type=float, default=0.8)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    rep = audit(args.file, args.jaccard)
    print("content audit: %s" % rep["file"])
    print("problems=%d  exact_dup_groups=%d  near_dups(>=%.2f)=%d"
          % (rep["problems"], len(rep["exact_dup_groups"]), rep["threshold"], len(rep["near_dups"])))
    print("same-type pair histogram (Jaccard >= t): " +
          ", ".join(">=%.1f: %d" % (t, c) for t, c in sorted(rep["pair_histogram"].items(), reverse=True)))
    for h, ids in rep["exact_dup_groups"].items():
        print("EXACT-DUP %s: %s" % (h[:10], ", ".join(ids)))
    for d, a, b in rep["near_dups"][:20]:
        print("NEAR-DUP %.4f: %s ~ %s" % (d, a, b))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=1)
    return 1 if (rep["exact_dup_groups"] or rep["near_dups"]) else 0

if __name__ == "__main__":
    sys.exit(main())
