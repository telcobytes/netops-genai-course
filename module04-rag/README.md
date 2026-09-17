# Module 4 — Grounding Agents in Telecom Knowledge (RAG)

This module builds a five-step Retrieval-Augmented Generation (RAG) pipeline:
**Chunk → Embed → Construct the query → Retrieve → Augment**.

The steps happen at two different times:

```
PREPARE THE KNOWLEDGE BASE (once)        ANSWER A QUESTION (every time)
Chunk → Embed chunks ──► vectors ◄────── Embed the query ◄── Construct the query
                                           │
                                           Retrieve (top k documents) → Augment → LLM
```

---

## What `rag_pipeline.py` Does

1. **Structure-Aware Chunking:** Splits the `data/knowledge_base/*.md` incident postmortems and reference docs on blank lines, so each paragraph or section becomes a chunk. Every chunk starts with its document's title and affected site, so it can be matched on its own.
2. **Dense Vector Embeddings:** Converts chunks into 768-dimensional semantic vectors through `llm_client.embed_texts()`. That function uses the first working model from `EMBEDDING_CANDIDATES` (`gemini-embedding-2` first). Override it with `COURSE_EMBEDDING_MODEL`. Chunks are embedded as `RETRIEVAL_DOCUMENT` and the query as `RETRIEVAL_QUERY`.
3. **Query Construction:** `build_retrieval_query()` decides what gets embedded. By default (`style="measured+question"`) it uses the active alarm types, the KPI thresholds that were crossed, and the cell and site IDs first, then adds the question. Ticket wording like "a trouble ticket reports… no alarm cited" describes the report, not the fault, and it pulls up the wrong incident.
4. **Cosine Similarity Retrieval:** Ranks every chunk by cosine similarity to the query, then keeps the best chunk from each of the top `k=2` **documents**. Pass `per_source=False` to see the raw chunk ranking.
5. **Augmented Drafting:** Puts live telemetry (`get_cell_kpis`, `get_active_alarms`) and the retrieved excerpts into a structured RCA prompt (Impact / Likely cause / Recommended action).

---

## How to Run

```bash
# Ensure your environment has your API key
export GEMINI_API_KEY="..."

# Run the pipeline
python rag_pipeline.py

# Compare the three query styles on EVAL-03's ticket
python lab_query_construction.py            # needs GEMINI_API_KEY
python lab_query_construction.py --offline  # bag-of-words, no key
```

If embeddings fail, check which models your key can use:

```bash
python ../data/llm_client.py --embeddings
```

### Automatic Offline Fallback:
If `GEMINI_API_KEY` is not set, `rag_pipeline.py` falls back to an offline bag-of-words keyword vectorizer, so you can still see cosine-similarity retrieval work without a key. If a key **is** set but embeddings fail, it prints a warning before falling back.

Bag-of-words matches words, not meaning. It does **not** reproduce the query-construction failure that `lab_query_construction.py` is built around. Run that lab with a key to see it.
