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
### Where the question comes from

Three things start a run, and they arrive with different material — which decides the query style:

| Trigger | What you have | Style |
|---|---|---|
| An alarm or KPI breach fires | No written text at all, all the telemetry | `measured` |
| A ticket arrives (tool or human) | Structured fields, plus a description of how it was reported | `measured+question` |
| An engineer asks something | Written text, and maybe no telemetry at all | `question` |

The last row is why `build_retrieval_query` falls back to the question when there are no alarms and no crossed thresholds: "what is our SOP for backhaul jitter?" has nothing measured to search with.

A step this module skips: a typed question does not arrive with IDs. The ticket gave us SITE-031; "why does this cell keep congesting?" would not, so a real system resolves the cell and site from the text first. `draft_grounded_rca` sidesteps it by taking `cell_id` as an argument.

---

4. **Cosine Similarity Retrieval:** Ranks every chunk by cosine similarity to the query, then keeps the best chunk from each of the top `k=2` **documents**. Pass `per_source=False` to see the raw chunk ranking.
5. **Augmented Drafting:** Puts live telemetry (`get_cell_kpis`, `get_active_alarms`) and the retrieved excerpts into a structured RCA prompt (Impact / Likely cause / Recommended action).

---

## Two ways to run each lab

| Lab | Offline | Live |
|---|---|---|
| `rag_pipeline.py` | `python rag_pipeline.py` with no key — retrieval runs on word counts | `export GEMINI_API_KEY=...` then the same command — Gemini embeddings, and the final RCA step runs |
| `lab_query_construction.py` | `python lab_query_construction.py --offline` | `python lab_query_construction.py` |
| `04_rag.ipynb` | — | Colab or Jupyter, key required |

Both scripts tell you which engine ranked, on the line that starts `Retrieval engine`.

**Offline is not a lesser version of the same thing, and this module is where that
matters most.** Word counts match spelling; embeddings match meaning. The
query-construction failure this module is built around *does not reproduce offline*,
because bag-of-words never had the meaning to be misled by. Study the mechanics
without a key by all means, then run it live before you believe any ranking.

If embeddings fail with a key set, the run says so loudly rather than quietly
falling back. Check which models your key can use:

```bash
python ../data/llm_client.py --embeddings
```

Bag-of-words matches words, not meaning. It does **not** reproduce the query-construction failure that `lab_query_construction.py` is built around. Run that lab with a key to see it.
