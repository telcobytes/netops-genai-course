# Checkpoint 1 — Teach it a new runbook

**After Module 4 (RAG) · ~20 minutes**

Your retriever currently knows three incidents. NetOps Co. has just resolved a
fourth — a **backhaul jitter** problem that looked, from the customer's side,
exactly like the evening congestion in `incident_001`.

That resemblance is the point. Retrieval doesn't match topics, it matches text.
Two incidents with near-identical symptoms and completely different causes are
where a retriever earns its keep or quietly fails.

## Task

1. Write `kb/incident_004_backhaul_jitter.md` **in this folder** — same shape as
   the existing three (Summary / Root Cause / Resolution / Prevention).

   It goes here, not in `data/knowledge_base/`, on purpose. That corpus is what
   Module 4, all three eval cases and the capstone retrieve against, so adding a
   document to it silently changes their results. Your runbook is still ranked
   against all four shared documents — the checkpoint reads both folders.
2. Re-run chunking and query with the symptom description in `starter.py`.
3. Make the retriever rank **your new document above `incident_001`**.

## Pass condition

```bash
python check.py
```

Passes when the top-ranked chunk for the given query comes from
`incident_004_backhaul_jitter.md`, and `incident_001_local_event_congestion.md`
does not outrank it.

## Why the folder matters

This is the lesson underneath the exercise, and it cost this course real time.
An evaluation corpus has to be **frozen and attributable**. The moment a lab step
can write into the corpus a later step is graded against, a passing test can go
red for a reason that has nothing to do with the code under test — and you will
look for the bug in the wrong file.

The same thing happened twice while this course was being built: this checkpoint
wrote into the shared knowledge base, and Module 10's tracing demo wrote a trace
log that the eval then graded as if it were evidence. Neither is visible reading
any single file. Both only appear when the labs run in order.

## If it won't rank

That's the exercise, not a bug. Read your document against the query and ask
which words actually overlap. Symptoms alone won't separate the two incidents —
both have slow speeds in the evening. What separates them is the *mechanism*:
jitter, packet delay variation, transport, link, the fact that PRB stayed
normal. Put the distinguishing mechanism in the same paragraph as the symptoms,
because the chunker splits on blank lines and each paragraph is retrieved on
its own.
