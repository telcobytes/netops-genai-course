"""
Checkpoint 1 — Teach it a new runbook.

STEP 1: Create kb/incident_004_backhaul_jitter.md (in THIS folder).
        Match the structure of the existing incident docs.

        It goes here rather than in data/knowledge_base/ on purpose. That
        corpus is what Module 4, all three eval cases and the capstone retrieve
        against; adding a document to it changes their rankings. Your runbook is
        still retrieved alongside all four shared documents -- see CORPUS below.

STEP 2: Run this file. It will show you how your document ranks.

STEP 3: Run check.py to confirm you passed.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "module04-rag"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

from rag_pipeline import KB_DIR, load_and_chunk_knowledge_base, retrieve  # noqa: E402

# The shared corpus, read-only, PLUS this checkpoint's own folder. Same exercise,
# no contamination.
LOCAL_KB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb")
CORPUS = [KB_DIR, LOCAL_KB]

# This is the query your document has to win. Note how little it gives away:
# the symptoms are shared with incident_001, so only the mechanism separates them.
QUERY = (
    "Customers near SITE-031 report slow speeds and stalling video in the evening. "
    "The cell's PRB utilization looks normal and user count is within planned capacity."
)

# TODO: nothing to change here — write the markdown document, then run this.

if __name__ == "__main__":
    chunks = load_and_chunk_knowledge_base(CORPUS)
    print(f"Indexed {len(chunks)} chunks from {len(set(c['source'] for c in chunks))} documents\n")
    print(f"QUERY: {QUERY}\n")
    for rank, chunk in enumerate(retrieve(QUERY, chunks, k=4), 1):
        print(f"  {rank}. {chunk['source']}")
        print(f"     {chunk['text'][:110].replace(chr(10), ' ')}...")
