"""
rag_pipeline.py — Module 4 hands-on: grounding the RCA drafter in real incidents

Implements the four RAG steps from the lecture — chunk, embed, retrieve, augment —
against the knowledge_base/ incident write-ups, then uses the retrieved context to
draft a grounded RCA instead of letting the model guess.

Retrieval uses real semantic dense embeddings via Gemini
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
from mock_tools import get_cell_kpis, get_active_alarms, lookup_topology  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
KB_DIR = os.path.join(DATA_DIR, "knowledge_base")


# ---------- Step 1: Structure-Aware Chunk ----------
def _document_context(text):
    """The title line and the site this document is about — the two facts that
    identify every chunk in it."""
    title, site = "", ""
    for line in text.splitlines():
        line = line.strip()
        if not title and line.startswith("# "):
            title = line[2:].strip()
        if not site and line.lower().startswith("**site affected:**"):
            site = line.split(":**", 1)[1].strip()
        if title and site:
            break
    return " — ".join(p for p in (title, site) if p)


def load_and_chunk_knowledge_base():
    """Split each incident doc into section/paragraph-level chunks, each one
    carrying its document's title and site.

    That header is not decoration. Splitting on blank lines puts
    "**Site affected:** SITE-031" in one chunk and "customers reported slow data
    speeds" in another, so no chunk contains both the symptom and the site it
    happened at — and the retriever cannot match on a site ID that appears
    nowhere near the text describing it. Module 10's EVAL-03 failed on exactly
    this: a query about slow data speeds at SITE-031 during evening peak
    retrieved the VoLTE incident instead, because it matched the *framing* of
    the question ("a trouble ticket reports… no alarm cited") while the document
    that actually described the symptoms had been cut away from its own name.

    Prepending the context is the standard fix, and it is what "structure-aware"
    has to mean: a chunk must carry enough of its document to be findable on its
    own.
    """
    chunks = []
    for path in sorted(glob.glob(os.path.join(KB_DIR, "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        context = _document_context(text)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            body = f"[{context}]\n{para}" if context else para
            chunks.append({
                "text": body,            # what gets embedded
                "excerpt": para,         # the original paragraph, for display
                "context": context,
                "source": os.path.basename(path),
            })
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


def embed_with_gemini_api(texts, task_type="RETRIEVAL_DOCUMENT"):
    """Production dense embeddings, via llm_client like everything else.

    This used to reach for the SDK directly and pin `text-embedding-004`, which
    Google retired — and because the caller below swallows embedding errors, the
    lab kept "working" on keyword vectors while claiming semantic retrieval.
    Embeddings now go through llm_client.embed_texts(), which walks a candidate
    list the same way chat models do.

    task_type: retrieval is asymmetric. The knowledge base is embedded as
    RETRIEVAL_DOCUMENT and the question as RETRIEVAL_QUERY, because a short
    question and a long passage are not the same kind of text and the model
    encodes them differently when told which is which.
    """
    from llm_client import embed_texts  # noqa: E402
    return embed_texts(texts, task_type=task_type)


# The knowledge base does not change between queries, and gemini-embedding-*
# will not embed a batch — so embedding 24 chunks costs 24 calls. Do it once per
# process and reuse. Without this, every retrieve() re-embeds the whole corpus,
# which is the same shape of bug that made notebook 04 spend 29 calls on one query.
_chunk_vector_cache = {}


# ---------- Step 3: Retrieve ----------
def retrieve(query, chunks, k=2, prefer_api=True):
    """Find the top-k most relevant chunks using cosine similarity.
    Uses Gemini semantic embeddings if available; falls back to offline keyword vectors.
    """
    api_key_available = bool(os.environ.get("GEMINI_API_KEY"))

    if prefer_api and api_key_available:
        try:
            # Dense semantic retrieval — dimensionality pinned in llm_client.EMBEDDING_DIMENSIONS
            chunk_texts = [c["text"] for c in chunks]
            cache_key = hash(tuple(chunk_texts))
            if cache_key not in _chunk_vector_cache:
                _chunk_vector_cache[cache_key] = embed_with_gemini_api(
                    chunk_texts, "RETRIEVAL_DOCUMENT")
            chunk_vectors = _chunk_vector_cache[cache_key]
            query_vector = embed_with_gemini_api([query], "RETRIEVAL_QUERY")[0]

            # zip() below truncates to the shorter list without saying so. If the
            # embedding call ever returns fewer vectors than chunks, ranking would
            # quietly happen over a handful of chunks — or one — and still return
            # a plausible document. Refuse to rank rather than rank a subset.
            if len(chunk_vectors) != len(chunks):
                raise RuntimeError(
                    f"embedded {len(chunk_vectors)} vectors for {len(chunks)} chunks")

            scored = sorted(
                zip(chunks, chunk_vectors),
                key=lambda pair: -_cosine_similarity(query_vector, pair[1]),
            )
            return [chunk for chunk, _ in scored[:k]]
        except Exception as e:
            # Falling back to keyword vectors is right when there is no key.
            # It is NOT right when a key is present and embeddings broke — this
            # lab's whole point is dense semantic retrieval, so say so loudly
            # rather than quietly doing something else and looking fine.
            print("\n" + "!" * 70)
            print("[RAG WARNING] Dense embeddings FAILED and this run fell back to")
            print("              offline keyword matching. Retrieval below is BAG OF")
            print("              WORDS, not semantic — results will differ from the")
            print("              lecture.")
            print(f"              Reason: {e}")
            print("              Fix:    python data/llm_client.py --embeddings")
            print("!" * 70 + "\n")

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
def draft_grounded_rca(cell_id: str, question: str, trace: list | None = None) -> str:
    """Draft an RCA grounded in retrieved prior incidents.

    `trace`, when given, is appended to with a record of what this function did.
    A property you want to assert on has to be recorded by the code that does it:
    run_eval's `must_retrieve` check reads this, and before it existed the check
    could only ever fail, because nothing told it which documents had been used.
    """
    kpis = get_cell_kpis(cell_id)

    # Resolve the SITE from topology rather than splitting the cell ID. The old
    # `cell_id.split("-")[0]` produced the literal string "CELL" for CELL-031A —
    # an unknown site, which returned [] — so this drafter had never once been
    # shown an alarm, and said so in its RCAs while three alarms were active.
    topology = lookup_topology(cell_id) or {}
    site_id = topology.get("site_id") or (cell_id if str(cell_id).startswith("SITE-") else None)
    alarms = get_active_alarms(site_id)

    chunks = load_and_chunk_knowledge_base()
    retrieved = retrieve(question, chunks, k=2)
    if trace is not None:
        trace.append({
            "tool": "retrieve",
            "args": {"query": question, "k": 2},
            "retrieved": [c["source"] for c in retrieved],
        })
    retrieved_text = "\n\n".join(
        f"[From {c['source']} — {c.get('context', '')}]\n{c.get('excerpt', c['text'])}"
        for c in retrieved
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

    mode = "Gemini dense embeddings" if os.environ.get("GEMINI_API_KEY") else "Offline keyword vectorizer"
    print(f"Retrieval Engine: {mode}")

    top_matches = retrieve(question, chunks, k=2)
    print("\n--- Top retrieved chunks ---")
    for m in top_matches:
        print(f"\n[{m['source']}]\n{m.get('excerpt', m['text'])[:200]}...")

    if os.environ.get("GEMINI_API_KEY"):
        print("\n--- Grounded RCA (calls the LLM) ---\n")
        print(draft_grounded_rca("CELL-031A", question))
    else:
        print("\n[Set GEMINI_API_KEY to run the final augmented generation step]")
