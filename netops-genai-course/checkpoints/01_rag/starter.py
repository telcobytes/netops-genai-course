"""
Checkpoint 1 — Teach it a new runbook.

STEP 1: Create ../../data/knowledge_base/incident_004_backhaul_jitter.md
        Match the structure of the existing incident docs.

STEP 2: Run this file. It will show you how your document ranks.

STEP 3: Run check.py to confirm you passed.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "module04-rag"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

from rag_pipeline import load_and_chunk_knowledge_base, retrieve  # noqa: E402

# This is the query your document has to win. Note how little it gives away:
# the symptoms are shared with incident_001, so only the mechanism separates them.
QUERY = (
    "Customers near SITE-031 report slow speeds and stalling video in the evening. "
    "The cell's PRB utilization looks normal and user count is within planned capacity."
)

# TODO: nothing to change here — write the markdown document, then run this.

if __name__ == "__main__":
    chunks = load_and_chunk_knowledge_base()
    print(f"Indexed {len(chunks)} chunks from {len(set(c['source'] for c in chunks))} documents\n")
    print(f"QUERY: {QUERY}\n")
    for rank, chunk in enumerate(retrieve(QUERY, chunks, k=4), 1):
        print(f"  {rank}. {chunk['source']}")
        print(f"     {chunk['text'][:110].replace(chr(10), ' ')}...")
