"""
rag_pipeline.py — Module 4 hands-on: grounding the RCA drafter in real incidents

Implements the five RAG steps from the lecture — chunk, embed, construct the
query, retrieve, augment — against the knowledge_base/ incident write-ups, then
uses the retrieved context to draft a grounded RCA instead of letting the model
guess.

Retrieval uses real semantic dense embeddings via Gemini
by default if GEMINI_API_KEY is present, with an automatic graceful fallback to an
offline bag-of-words keyword vectorizer if offline.

Run:
    python rag_pipeline.py

HOW IT FITS TOGETHER, IN PLAIN TERMS
Think of the knowledge base as a filing cabinet of old incident reports. When a
new ticket comes in, a good NOC engineer does not re-read the whole cabinet.
They pull the two or three reports that look most like today's problem, read
those, and then write the RCA. This file does the same thing in five steps:

  1. Chunk      cut each report into paragraph-sized cards
  2. Embed      turn each card into a list of numbers that captures what it is about
  3. Query      decide what to search the cabinet with (not always the ticket text)
  4. Retrieve   score every card against the search and keep the best two reports
  5. Augment    paste those two reports into the prompt, then ask the LLM

Steps 1 and 2 run once over the whole knowledge base. Steps 3 to 5 run for every
new ticket.
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
# Why cut documents up at all? An incident report covers several things: what
# happened, the root cause, the fix, the lessons. A ticket about slow evening
# speeds matches the Summary paragraph strongly and the Lessons Learned bullets
# hardly at all. Scoring the report as one blob blurs those together, so we
# score each paragraph ("chunk") on its own. The 4 documents become 24 chunks.
#
# Why paragraphs and not, say, every 500 characters? A fixed character count
# cuts wherever it lands -- mid-sentence, or halfway through a numbered SOP
# step -- and half a step means nothing on its own. Blank lines are where the
# author already decided one idea ends and the next begins.

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

    Chunking decides what CAN be found. It does not decide what the retriever is
    asked to find -- that is step 3, build_retrieval_query.

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
        # "\n\n" is a blank line: the boundary between paragraphs and sections.
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            # Every chunk gets its document's title and site stuck on top, so the
            # Summary paragraph of incident_001 is stored as:
            #
            #   [Incident Postmortem: Localized Congestion Near a Public Event Venue — SITE-031 (CELL-031A)]
            #   ## Summary
            #   A cell adjacent to a public event venue experienced a sharp rise...
            #
            # Without that first line, the paragraph never mentions SITE-031, and a
            # search for SITE-031 could not find it.
            body = f"[{context}]\n{para}" if context else para
            chunks.append({
                "text": body,            # what gets embedded
                "excerpt": para,         # the original paragraph, for display
                "context": context,
                "source": os.path.basename(path),
            })
    return chunks


# ---------- Step 2: Embed (Semantic Vectors with Offline Fallback) ----------
# A computer cannot compare two paragraphs directly, but it can compare two lists
# of numbers. "Embedding" means turning text into such a list, called a vector.
#
# Two ways to do that live in this file:
#
#   Dense embeddings (Gemini, the default with a key). A model reads the text and
#   outputs 768 numbers that capture what it is ABOUT. Texts about similar things
#   get similar numbers even when they share no words. "Similar" is the model's
#   idea, though: same topic and same kind of wording, not necessarily the same
#   fault. Nobody can read the 768 numbers individually; only comparisons mean
#   anything.
#
#   Bag of words (offline fallback, no key). Count how often each word appears.
#   Simple and free, but it only sees spelling, not meaning -- see _vectorize.

def _tokenize(text):
    # Lowercase and keep runs of letters and digits:
    #   "PRB utilization climbed above 90%"  ->  ["prb", "utilization", "climbed", "above", "90"]
    return re.findall(r"[a-z0-9]+", text.lower())


def _vectorize(tokens, vocab):
    # One number per word in the vocabulary: how many times that word appears.
    # With vocab ["90", "above", "climbed", "looks", "normal", "prb", "utilization"]:
    #   "PRB utilization climbed above 90%"  ->  [1, 1, 1, 0, 0, 1, 1]
    #   "PRB utilization looks normal"       ->  [0, 0, 0, 1, 1, 1, 1]
    # Those two say opposite things, yet they share "prb" and "utilization" and
    # score 0.45 -- the weakness of matching on words instead of meaning.
    counts = Counter(tokens)
    return [counts.get(word, 0) for word in vocab]


def _cosine_similarity(a, b):
    # How closely two vectors point the same way; in practice between 0 and 1 here.
    # Picture two sector antennas: same azimuth scores 1.0, 90 degrees apart
    # scores 0.0. It is literally the cosine of the angle between the two vectors.
    # It compares direction, not length, so a long report and a one-line query
    # can still score high if they are about the same thing.
    #
    # Reading the numbers: bag-of-words scores 0.0 when nothing is shared. Dense
    # embeddings rarely go that low -- in this course, related telecom text scores
    # roughly 0.6 to 0.9 -- so only compare scores against each other, for the
    # same search.
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_with_gemini_api(texts, task_type="RETRIEVAL_DOCUMENT"):
    """Production dense embeddings, via llm_client like everything else.

    llm_client.embed_texts() picks the embedding model from a candidate list, the
    same way chat models are picked, so a retired model does not break the lab.

    task_type: retrieval is asymmetric. The knowledge base is embedded as
    RETRIEVAL_DOCUMENT and the question as RETRIEVAL_QUERY, because a short
    question and a long passage are not the same kind of text and the model
    encodes them differently when told which is which.
    """
    from llm_client import embed_texts  # noqa: E402
    return embed_texts(texts, task_type=task_type)


# The knowledge base does not change between queries, and gemini-embedding-*
# will not embed a batch — so embedding 24 chunks costs 24 calls. Do it once per
# process and reuse, rather than re-embedding the whole corpus on every retrieve().
_chunk_vector_cache = {}


# ---------- Step 3: Construct the Query ----------
# The retriever finds text that SOUNDS LIKE whatever you search with -- including
# how the problem was reported. So instead of searching with the ticket as
# written, search with what the network measured, in the same language the
# incident reports use. For TCK-4471 on CELL-031A:
#
#   Ticket (goes into the prompt, unchanged):
#     "A trouble ticket (TCK-4471) reports slow data speeds near SITE-031 ..."
#
#   Search text (built below from live alarms and KPIs):
#     "high prb utilization rrc drop rate high backhaul latency warning
#      cell congestion prb utilization rrc drop rate rrc setup success rate
#      CELL-031A SITE-031"
#
# It is what an experienced engineer types into the ticket search: "PRB high
# CELL-031A", not the customer's complaint.

def build_retrieval_query(question, kpis=None, alarms=None, cell_id="", site_id="",
                          style="measured+question"):
    """Decide WHAT YOU EMBED. The question is what the customer wrote; the query
    is what the retriever searches with. They are not the same thing, and the
    question still goes into the prompt unchanged -- this only changes the search.

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

    style is here so the lab can run all three and compare:
      "question"           the raw question, embedded as-is
      "measured"           alarm types + crossed KPI thresholds + identifiers
      "measured+question"  measured facts first, the question after as context
    """
    if style == "question":
        return question

    parts = []
    # Alarm names, made readable: "HIGH_PRB_UTILIZATION" -> "high prb utilization"
    for a in (alarms or []):
        if a.get("alarm_type"):
            parts.append(a["alarm_type"].replace("_", " ").lower())
    # KPIs that crossed a threshold, by name only: "rrc_drop_rate_pct" -> "rrc drop rate".
    # The values (11.4%, threshold 5%) are left out: embeddings are poor at
    # comparing numbers, and the KIND of problem is what matches past incidents.
    for t in ((kpis or {}).get("thresholds_crossed") or []):
        if t.get("metric"):
            parts.append(t["metric"].replace("_pct", "").replace("_", " "))
    # The cell and site, so incidents on this site rank higher.
    for ident in (cell_id, site_id):
        if ident:
            parts.append(str(ident))

    # No live telemetry to speak of -- an alarm-less, KPI-less call. Embedding an
    # empty string finds nothing, so fall back rather than silently retrieve junk.
    if not parts:
        return question

    measured = " ".join(dict.fromkeys(parts))       # de-duplicated, order kept
    return measured if style == "measured" else f"{measured}. {question}"


# Which engine actually ranked, set by retrieve() once it has run. Having a key is
# not the same as the embedding call working, so anything that wants to report the
# engine reads this AFTER retrieving instead of guessing from the environment.
last_engine = None


# ---------- Step 4: Retrieve ----------
# Retrieval is ranking, not lookup. There is no "match" or "no match": every one
# of the 24 chunks gets a similarity score against the search text, the list is
# sorted, and the best ones are kept. It always returns something, even when
# nothing in the knowledge base is relevant -- so the failure to watch for is
# the WRONG document coming first, not an empty result.
#
# Measured example (Gemini, 17 Sep 2026), searching with TCK-4471 as written:
#   0.789  incident_003_volte_call_drops.md          <- ranked first, wrong fault
#   0.788  incident_001_local_event_congestion.md    <- the right answer
# A 0.001 gap decided it. That is why step 3 exists.

def _top_k(scored, k, per_source):
    """Turn a full ranking into the k results to return.

    per_source=True gives k DOCUMENTS, represented by their best-scoring chunk --
    "the 2 most relevant past incidents", not two slices of one. Ranking stays
    chunk-level; only the selection changes.

    It matters more than it looks. Each incident is six chunks, so the two best
    chunks are frequently two sections of the same incident: the same postmortem
    printed twice under "top two", and an eval check like
    `must_not_retrieve: incident_002` passes without incident_002 ever having
    been in contention -- an assertion that cannot fail is not an assertion.

    per_source=False is the raw chunk ranking, kept so the lab can show both.
    """
    if not per_source:
        return [c for c, _ in scored[:k]]
    # Walk down the ranking and keep only the first (best) chunk from each report.
    # Example raw ranking:  incident_001, incident_001, incident_002, incident_003
    # k=2 returns:          incident_001, incident_002
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
    global last_engine
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

            # Score every chunk against the query and sort, highest first (the minus
            # sign flips Python's default smallest-first order).
            scored = sorted(
                zip(chunks, chunk_vectors),
                key=lambda pair: -_cosine_similarity(query_vector, pair[1]),
            )
            last_engine = "Gemini dense embeddings"
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

    # Offline Bag-of-Words fallback (runs without API keys). Same ranking idea, but
    # the vectors are word counts. The vocabulary is every word in every chunk
    # plus the query, so all vectors have the same length and can be compared.
    all_token_lists = [_tokenize(c["text"]) for c in chunks] + [_tokenize(query)]
    vocab = sorted(set(tok for toks in all_token_lists for tok in toks))
    vectors = [_vectorize(toks, vocab) for toks in all_token_lists]
    query_vector, chunk_vectors = vectors[-1], vectors[:-1]

    scored = sorted(
        zip(chunks, chunk_vectors),
        key=lambda pair: -_cosine_similarity(query_vector, pair[1]),
    )
    last_engine = "Offline keyword vectorizer"
    return _top_k(scored, k, per_source)


# ---------- Step 5: Augment ----------
# "Augment" just means adding to the prompt. The LLM still writes the RCA, but it
# now reads three things before answering:
#   - the question, exactly as the ticket put it
#   - live data: current KPI readings and active alarms for the cell
#   - the two past incident write-ups step 4 retrieved
# That is the "book open" answer: instead of guessing from general telecom
# knowledge, the model can say "this matches incident_001" and point to what
# NetOps Co. did last time.

def draft_grounded_rca(cell_id: str, question: str, trace: list | None = None,
                       query_style: str = "measured+question") -> str:
    """Draft an RCA grounded in retrieved prior incidents.

    `trace`, when given, is appended to with a record of what this function did.
    A property you want to assert on has to be recorded by the code that does it:
    run_eval's `must_retrieve` check reads this to learn which documents were used.
    """
    kpis = get_cell_kpis(cell_id)

    # Resolve the SITE from topology rather than parsing the cell ID -- alarms are
    # raised per site, and "CELL-031A" does not contain its site's ID.
    topology = lookup_topology(cell_id) or {}
    site_id = topology.get("site_id") or (cell_id if str(cell_id).startswith("SITE-") else None)
    alarms = get_active_alarms(site_id)

    chunks = load_and_chunk_knowledge_base()

    # The question is what the customer wrote. The query is what we search with.
    # Pass query_style="question" to embed the question as-is; the lab does
    # exactly that, to show the difference.
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
            # than it looks.
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
    # The ticket the whole module follows (EVAL-03). Change both lines to try your
    # own, e.g. cell_id = "CELL-022A" and a question about VoLTE call drops.
    cell_id = "CELL-031A"
    question = ("A trouble ticket (TCK-4471) reports slow data speeds near SITE-031 during "
                "evening peak hours for the past three days, with no specific alarm cited yet.")
    print(f"Question: {question}\n")

    chunks = load_and_chunk_knowledge_base()
    print(f"Loaded {len(chunks)} chunks from {KB_DIR}\n")

    # Build the query the same way draft_grounded_rca does, so the ranking printed
    # here is the ranking the RCA below is grounded in -- not the raw question's.
    kpis = get_cell_kpis(cell_id)
    site_id = (lookup_topology(cell_id) or {}).get("site_id")
    alarms = get_active_alarms(site_id)
    query = build_retrieval_query(question, kpis, alarms, cell_id, site_id)
    print("\n--- Constructed query (what actually gets embedded) ---")
    print(f"  {query}")
    print("  Built from active alarm types, crossed KPI thresholds and IDs, then the\n"
          "  question. The question itself still goes into the prompt unchanged.\n"
          "  Run lab_query_construction.py to compare the three query styles.")

    top_matches = retrieve(query, chunks, k=2)
    # Printed after retrieving, not before: this is what ranked, not what we hoped
    # would rank. With a key that failed mid-run, it says "Offline keyword vectorizer"
    # and the warning above says why.
    print(f"\nRetrieval engine used: {last_engine}")

    print("\n--- Top 2 retrieved documents (best chunk of each) ---")
    for m in top_matches:
        print(f"\n[{m['source']}]\n{m.get('excerpt', m['text'])[:200]}...")

    # Retrieval is ranking, not lookup, and that is easier to believe when you can
    # see the ranking. These are the chunks just below the cut.
    raw = retrieve(query, chunks, k=4, per_source=False)
    print("\n--- The ranking underneath (raw chunks, no per-source limit) ---")
    for i, m in enumerate(raw, 1):
        marker = "  <- returned" if m in top_matches else ""
        print(f"  {i}. {m['source']:<44}{marker}")

    sources = [m["source"] for m in raw]
    repeated = sorted({s for s in sources if sources.count(s) > 1})
    if repeated:
        print(f"\n  {', '.join(repeated)} took more than one of the top {len(raw)} slots.\n"
              "  Ranking is chunk-level; the answer you want is document-level. That\n"
              "  gap is why retrieve() returns one chunk per document by default.")
    else:
        print(f"\n  No document took more than one of the top {len(raw)} slots this time.\n"
              "  It often does: each document is several chunks. That is why retrieve()\n"
              "  returns one chunk per document by default.")

    if os.environ.get("GEMINI_API_KEY"):
        print("\n--- Grounded RCA (calls the LLM) ---\n")
        print(draft_grounded_rca(cell_id, question))
    else:
        print("\n[Set GEMINI_API_KEY to run the final augmented generation step]")
