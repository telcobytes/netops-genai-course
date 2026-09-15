"""
rag_pipeline.py — Module 4 hands-on: grounding the RCA drafter in real incidents

Implements the four RAG steps from the lecture — chunk, embed, retrieve, augment —
against the knowledge_base/ incident write-ups, then uses the retrieved context to
draft a grounded RCA instead of letting the model guess.

Retrieval uses real semantic dense embeddings via Gemini's API (text-embedding-004)
by default if GEMINI_API_KEY is present, with an automatic graceful fallback to an
offline bag-of-words keyword vectorizer if offline.

Run:
    python rag_pipeline.py
"""

import glob
import math
import os
import re
import sys
from collections import Counter

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm  # noqa: E402
from mock_tools import get_cell_kpis, get_active_alarms  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
KB_DIR = os.path.join(DATA_DIR, "knowledge_base")


# ---------- Step 1: Structure-Aware Chunk ----------
def load_and_chunk_knowledge_base():
    """Split each incident doc into section/paragraph-level chunks.
    Preserves whole runbook steps and tables intact rather than slicing mid-trace.
    """
    chunks = []
    for path in sorted(glob.glob(os.path.join(KB_DIR, "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            chunks.append({"text": para, "source": os.path.basename(path)})
    return chunks


# ---------- Step 2: Embed (Semantic Vectors with Offline Fallback) ----------
def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _vectorize(tokens, vocab):
    counts = Counter(tokens)
    return [counts.get(word, 0) for word in vocab]


def _cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_with_gemini_api(texts):
    """Production embeddings via Gemini API (text-embedding-004).
    Uses the exact same GEMINI_API_KEY already configured in your environment.
    """
    from google import genai
    client = genai.Client()
    result = client.models.embed_content(model="text-embedding-004", contents=texts)
    return [e.values for e in result.embeddings]


# ---------- Step 3: Retrieve ----------
def retrieve(query, chunks, k=2, prefer_api=True):
    """Find the top-k most relevant chunks using cosine similarity.
    Uses Gemini semantic embeddings if available; falls back to offline keyword vectors.
    """
    api_key_available = bool(os.environ.get("GEMINI_API_KEY"))

    if prefer_api and api_key_available:
        try:
            # Dense semantic retrieval (768-dimensional embeddings)
            chunk_texts = [c["text"] for c in chunks]
            chunk_vectors = embed_with_gemini_api(chunk_texts)
            query_vector = embed_with_gemini_api([query])[0]

            scored = sorted(
                zip(chunks, chunk_vectors),
                key=lambda pair: -_cosine_similarity(query_vector, pair[1]),
            )
            return [chunk for chunk, _ in scored[:k]]
        except Exception as e:
            print(f"[RAG notice: Gemini embedding API error ({e}); using offline keyword fallback]")

    # Offline Bag-of-Words fallback (runs without API keys)
    all_token_lists = [_tokenize(c["text"]) for c in chunks] + [_tokenize(query)]
    vocab = sorted(set(tok for toks in all_token_lists for tok in toks))
    vectors = [_vectorize(toks, vocab) for toks in all_token_lists]
    query_vector, chunk_vectors = vectors[-1], vectors[:-1]

    scored = sorted(
        zip(chunks, chunk_vectors),
        key=lambda pair: -_cosine_similarity(query_vector, pair[1]),
    )
    return [chunk for chunk, _ in scored[:k]]


# ---------- Step 4: Augment ----------
def draft_grounded_rca(cell_id: str, question: str) -> str:
    kpis = get_cell_kpis(cell_id)
    alarms = get_active_alarms(cell_id.split("-")[0] if "-" in cell_id else None)

    chunks = load_and_chunk_knowledge_base()
    retrieved = retrieve(question, chunks, k=2)
    retrieved_text = "\n\n".join(
        f"[From {c['source']}]\n{c['text']}" for c in retrieved
    )

    prompt = f"""You are a NOC analyst drafting a root-cause analysis (RCA).

QUESTION: {question}

LIVE DATA for {cell_id}:
KPI readings: {kpis}
Active alarms: {alarms}

RELEVANT PAST INCIDENTS (retrieved from NetOps Co.'s history):
{retrieved_text}

Draft an RCA in this exact structure:
Impact: ...
Likely cause: ...
Recommended action: ...

Ground your answer in the past incidents above where relevant, and say so
explicitly if this matches a known prior pattern.
"""
    return call_llm([{"role": "user", "content": prompt}])


if __name__ == "__main__":
    question = "Why does CELL-031A keep having congestion problems?"
    print(f"Question: {question}\n")

    chunks = load_and_chunk_knowledge_base()
    print(f"Loaded {len(chunks)} chunks from {KB_DIR}\n")

    mode = "Gemini Dense Embeddings (text-embedding-004)" if os.environ.get("GEMINI_API_KEY") else "Offline Keyword Vectorizer"
    print(f"Retrieval Engine: {mode}")

    top_matches = retrieve(question, chunks, k=2)
    print("\n--- Top retrieved chunks ---")
    for m in top_matches:
        print(f"\n[{m['source']}]\n{m['text'][:200]}...")

    if os.environ.get("GEMINI_API_KEY"):
        print("\n--- Grounded RCA (calls the LLM) ---\n")
        print(draft_grounded_rca("CELL-031A", question))
    else:
        print("\n[Set GEMINI_API_KEY to run the final augmented generation step]")
