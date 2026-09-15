# Module 4 — Grounding Agents in Telecom Knowledge (RAG)

This module implements the complete 4-step Retrieval-Augmented Generation (RAG) pipeline:
**Chunk → Embed → Retrieve → Augment**.

---

## What `rag_pipeline.py` Does

1. **Structure-Aware Chunking:** Parses `data/knowledge_base/*.md` incident post-mortems and vendor runbooks along section/paragraph boundaries, preserving whole call flows and troubleshooting steps intact.
2. **Dense Vector Embeddings:** Uses Google's `text-embedding-004` model to convert chunks into 768-dimensional semantic vectors.
3. **Cosine Similarity Retrieval:** Computes dot-product similarity between the incoming inquiry and the chunk vectors to select the $k=2$ most relevant historical runbooks.
4. **Augmented Drafting:** Stuffs live telemetry (`get_cell_kpis`, `get_active_alarms`) alongside the retrieved runbooks into a structured RCA prompt.

---

## How to Run

```bash
# Ensure your environment has your API key
export GEMINI_API_KEY="..."

# Run the pipeline
python rag_pipeline.py
```

### Automatic Offline Fallback:
If `GEMINI_API_KEY` is not detected in your shell, `rag_pipeline.py` will automatically fall back to an offline bag-of-words keyword vectorizer so the mathematical cosine-similarity retrieval remains demonstrable without external dependencies.
