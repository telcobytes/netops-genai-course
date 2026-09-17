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


def load_and_chunk_knowledge_base(kb_dir=None):
    """Split each incident doc into section/paragraph-level chunks, each one
    carrying its document's title and site.

    That header is not decoration. Splitting on blank lines puts
    "**Site affected:** SITE-031" in one chunk and "customers reported slow data
    speeds" in another, so no chunk contains both the symptom and the site it
    happened at — and the retriever cannot match on a site ID that appears
    nowhere near the text describing it. Prepending the context is the standard
    fix, and it is what "structure-aware" has to mean: a chunk must carry enough
    of its document to be findable on its own.

    CORRECTION, 16 Sep 2026. This docstring used to credit that header with
    fixing EVAL-03 — a congestion query that retrieved the VoLTE incident. It
    did not. The header was already being prepended on the failing runs. The
    query was the problem: we embedded the ticket text verbatim, reporting
    framing included, and the VoLTE postmortem IS a trouble ticket with no major
    alarm that recurs by time of day. See build_retrieval_query. Chunking and
    query construction are both real and they are not the same lever; this file
    once claimed one had done the other's work.

    kb_dir: a directory, or several. Defaults to the shared corpus. Checkpoint 1
    passes [KB_DIR, its own folder] so a student's new runbook is retrievable
    without being written into the corpus every later module is graded against.
    """
    dirs = [KB_DIR] if kb_dir is None else (
        [kb_dir] if isinstance(kb_dir, str) else list(kb_dir))
    paths = sorted(q for d in dirs for q in glob.glob(os.path.join(d, "*.md")))

    chunks = []
    for path in paths:
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
def _top_k(scored, k, per_source):
    """Turn a full ranking into the k results to return.

    per_source=True gives k DOCUMENTS, represented by their best-scoring chunk.
    That is what the lecture claims -- slide 35 says "the 2 most relevant past
    incidents", and slides 39 and 40 both say the failure mode to watch is "the
    wrong DOCUMENT won". Ranking stays chunk-level, which is slide 37's mechanic
    and is correct; only the selection changes.

    It matters more than it looks. Each incident is six chunks, so the two best
    chunks are frequently two sections of the same incident: the student sees
    the same postmortem printed twice under "top two", and the eval's
    `must_not_retrieve: incident_002` passes without incident_002 ever having
    been in contention -- an assertion that cannot fail is not an assertion.

    per_source=False is the raw chunk ranking, kept so the lab can show both.
    """
    if not per_source:
        return [c for c, _ in scored[:k]]
    best, seen = [], set()
    for chunk, _ in scored:
        if chunk["source"] in seen:
            continue
        seen.add(chunk["source"])
        best.append(chunk)
        if len(best) == k:
            break
    return best


def retrieve(query, chunks, k=2, prefer_api=True, per_source=True):
    """Find the k most relevant past incidents, using cosine similarity.

    Ranking is over chunks; selection is one chunk per source document, so k=2
    means two different incidents rather than two sections of one. Pass
    per_source=False for the raw chunk ranking.

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
            return _top_k(scored, k, per_source)
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
    return _top_k(scored, k, per_source)


# ---------- Step 4: Augment ----------
def build_retrieval_query(question, kpis=None, alarms=None, cell_id="", site_id="",
                          style="measured+question"):
    """Step 3 of five: decide WHAT YOU EMBED. This is the step the lecture used
    to skip, and it decided the outcome.

    Measured 16 Sep 2026 against the shipped knowledge base, EVAL-03, dense
    embeddings. The scenario reads:

        "A trouble ticket (TCK-4471) reports slow data speeds near SITE-031
         during evening peak hours for the past three days, with no specific
         alarm cited yet."

    Embed that whole string and the top hit is incident_003 -- a VoLTE
    postmortem, for a congestion question. Not a bug: three of its four phrases
    describe the SHAPE OF THE REPORT (a trouble ticket, reported by field, no
    alarm cited, recurring by time of day) and incident_003 IS a trouble ticket
    with no major alarm that recurs by time of day. Delete those eleven words
    and incident_001 takes the top three slots. Same model, same chunks, same
    code.

    The rule this file follows, and the one worth carrying to your own systems:

        RETRIEVE ON WHAT YOU MEASURED AND HOW IT BEHAVES,
        NOT ON HOW IT WAS REPORTED.

    Ticket numbers, who raised it, and whether an alarm was cited are routing
    metadata. They belong in the ticket. They do not belong in a vector.

    style is here so the lab can run all three rungs and compare:
      "question"           the raw question -- what this pipeline used to embed
      "measured"           alarm types + crossed KPI thresholds + identifiers
      "measured+question"  measured facts first, the question after as context
    """
    if style == "question":
        return question

    parts = []
    for a in (alarms or []):
        if a.get("alarm_type"):
            parts.append(a["alarm_type"].replace("_", " ").lower())
    for t in ((kpis or {}).get("thresholds_crossed") or []):
        if t.get("metric"):
            parts.append(t["metric"].replace("_pct", "").replace("_", " "))
    for ident in (cell_id, site_id):
        if ident:
            parts.append(str(ident))

    # No live telemetry to speak of -- an alarm-less, KPI-less call. Embedding an
    # empty string finds nothing, so fall back rather than silently retrieve junk.
    if not parts:
        return question

    measured = " ".join(dict.fromkeys(parts))       # de-duplicated, order kept
    return measured if style == "measured" else f"{measured}. {question}"


def draft_grounded_rca(cell_id: str, question: str, trace: list | None = None,
                       query_style: str = "measured+question") -> str:
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

    # The question is what the customer wrote. The query is what we embed, and
    # they are not the same thing -- see build_retrieval_query for the measurement
    # that made this a separate step. Pass query_style="question" to get the old
    # behaviour back; the lab does exactly that, to show the difference.
    query = build_retrieval_query(question, kpis, alarms, cell_id, site_id,
                                  style=query_style)
    retrieved = retrieve(query, chunks, k=2)
    if trace is not None:
        trace.append({
            "tool": "retrieve",
            "args": {"query": query, "question": question,
                     "style": query_style, "k": 2},
            # ORDER MATTERS and is asserted on: retrieved[0] is the document the
            # retriever ranked first. "Appears in the top two" is a weaker claim
            # than it looks -- it passed for months while the top hit was wrong.
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
    cell_id = "CELL-031A"
    question = "Why does CELL-031A keep having congestion problems?"
    print(f"Question: {question}\n")

    chunks = load_and_chunk_knowledge_base()
    print(f"Loaded {len(chunks)} chunks from {KB_DIR}\n")

    mode = "Gemini dense embeddings" if os.environ.get("GEMINI_API_KEY") else "Offline keyword vectorizer"
    print(f"Retrieval Engine: {mode}")

    # Build the query the same way draft_grounded_rca does, so the ranking printed
    # here is the ranking the RCA below is grounded in -- not the raw question's.
    kpis = get_cell_kpis(cell_id)
    site_id = (lookup_topology(cell_id) or {}).get("site_id")
    alarms = get_active_alarms(site_id)
    query = build_retrieval_query(question, kpis, alarms, cell_id, site_id)
    print("\n--- Constructed query (what actually gets embedded) ---")
    print(f"  {query}")
    print("  Built from active alarm types, crossed KPI thresholds and IDs, then the\n"
          "  question. Pass style=\"question\" to build_retrieval_query to embed the\n"
          "  question alone, or run lab_query_construction.py to compare all three.")

    top_matches = retrieve(query, chunks, k=2)
    print("\n--- Top 2 retrieved incidents (best chunk of each) ---")
    for m in top_matches:
        print(f"\n[{m['source']}]\n{m.get('excerpt', m['text'])[:200]}...")

    # "Retrieval is ranking, not lookup" is the line on slide 40, and it is worth
    # more when you can see the ranking. These are the chunks that LOST: same
    # question, same knowledge base, just below the cut.
    raw = retrieve(query, chunks, k=4, per_source=False)
    print("\n--- The ranking underneath (raw chunks, no per-source limit) ---")
    for i, m in enumerate(raw, 1):
        marker = "  <- returned" if m in top_matches else ""
        print(f"  {i}. {m['source']:<44}{marker}")
    print("\n  Note how often one incident takes several of the top slots. Ranking is\n"
          "  chunk-level; the answer you want is document-level. That gap is why\n"
          "  retrieve() returns one chunk per source -- pass per_source=False to see\n"
          "  the raw ranking, and ask yourself which document never got considered.")

    if os.environ.get("GEMINI_API_KEY"):
        print("\n--- Grounded RCA (calls the LLM) ---\n")
        print(draft_grounded_rca(cell_id, question))
    else:
        print("\n[Set GEMINI_API_KEY to run the final augmented generation step]")
