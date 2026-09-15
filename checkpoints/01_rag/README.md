# Checkpoint 1 — Teach it a new runbook

**After Module 4 (RAG) · ~20 minutes**

Your retriever currently knows three incidents. NetOps Co. has just resolved a
fourth — a **backhaul jitter** problem that looked, from the customer's side,
exactly like the evening congestion in `incident_001`.

That resemblance is the point. Retrieval doesn't match topics, it matches text.
Two incidents with near-identical symptoms and completely different causes are
where a retriever earns its keep or quietly fails.

## Task

1. Write `../../data/knowledge_base/incident_004_backhaul_jitter.md` in the same
   shape as the existing three (Summary / Root Cause / Resolution / Prevention).
2. Re-run chunking and query with the symptom description in `starter.py`.
3. Make the retriever rank **your new document above `incident_001`**.

## Pass condition

```bash
python check.py
```

Passes when the top-ranked chunk for the given query comes from
`incident_004_backhaul_jitter.md`, and `incident_001_local_event_congestion.md`
does not outrank it.

## If it won't rank

That's the exercise, not a bug. Read your document against the query and ask
which words actually overlap. Symptoms alone won't separate the two incidents —
both have slow speeds in the evening. What separates them is the *mechanism*:
jitter, packet delay variation, transport, link, the fact that PRB stayed
normal. Put the distinguishing mechanism in the same paragraph as the symptoms,
because the chunker splits on blank lines and each paragraph is retrieved on
its own.
