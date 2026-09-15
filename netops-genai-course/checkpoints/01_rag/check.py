"""Checkpoint 1 — pass/fail. Run: python check.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "..", "module04-rag"))
sys.path.append(os.path.join(HERE, "..", "..", "data"))

from rag_pipeline import load_and_chunk_knowledge_base, retrieve  # noqa: E402
from starter import QUERY  # noqa: E402

TARGET = "incident_004_backhaul_jitter.md"
RIVAL = "incident_001_local_event_congestion.md"
KB = os.path.join(HERE, "..", "..", "data", "knowledge_base")


def main() -> int:
    checks = []

    exists = os.path.exists(os.path.join(KB, TARGET))
    checks.append((f"{TARGET} exists", exists,
                   "found" if exists else "not found — create it in data/knowledge_base/"))
    if not exists:
        return report(checks)

    body = open(os.path.join(KB, TARGET), encoding="utf-8").read()
    substantial = len(body.split()) >= 80
    checks.append(("document has real content (>=80 words)", substantial, f"{len(body.split())} words"))

    ranked = [c["source"] for c in retrieve(QUERY, load_and_chunk_knowledge_base(), k=5)]
    top_is_target = bool(ranked) and ranked[0] == TARGET
    checks.append(("your document ranks first", top_is_target,
                   f"top result: {ranked[0] if ranked else 'nothing'}"))

    t = ranked.index(TARGET) if TARGET in ranked else 99
    r = ranked.index(RIVAL) if RIVAL in ranked else 99
    beats_rival = t < r
    checks.append((f"outranks {RIVAL}", beats_rival,
                   f"positions — yours {t + 1 if t < 99 else 'unranked'}, rival {r + 1 if r < 99 else 'unranked'}"))

    return report(checks)


def report(checks) -> int:
    print("\nCheckpoint 1 — Teach it a new runbook\n" + "-" * 52)
    for label, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label:38} {detail}")
    passed = all(ok for _, ok, _ in checks)
    print("-" * 52)
    print("  PASS — the retriever learned to tell the two apart." if passed
          else "  FAIL — see README.md, 'If it won't rank'.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
