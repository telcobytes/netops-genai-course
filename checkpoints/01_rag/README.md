# Checkpoint 1 — Teach it a new runbook

**After Module 4 (RAG) · ~20 minutes**

Your retriever currently knows three incidents and one reference note. NetOps Co. has just resolved a
fourth — a **backhaul jitter** problem that looked, from the customer's side,
exactly like the evening congestion in `incident_001`.

That resemblance is the point. The retriever ranks by how similar the text is,
not by what the incident was actually about.
Two incidents with near-identical symptoms and completely different causes are
where a retriever earns its keep or quietly fails.

## Task

1. Create a `kb/` folder here and write `kb/incident_004_backhaul_jitter.md` in
   it — same shape as the existing incidents in `data/knowledge_base/`: a
   `# Incident Postmortem: …` title, a `**Site affected:**` line, then
   Summary / Root Cause / Resolution / Lessons Learned.

   It goes here, not in `data/knowledge_base/`, on purpose. That corpus is what
   Module 4, all three eval cases and the capstone retrieve against, so adding a
   document to it silently changes their results. Your runbook is still ranked
   against all four shared documents — the checkpoint reads both folders.
2. Run `python starter.py` to see where your document ranks for its query.
3. Make the retriever rank **your new document above `incident_001`**.

## Pass condition

```bash
python check.py
```

Passes when the top-ranked document for the query in `starter.py` is
`incident_004_backhaul_jitter.md`, and `incident_001_local_event_congestion.md`
does not outrank it.

`check.py` grades with whichever engine you have: Gemini embeddings when
`GEMINI_API_KEY` is set, offline bag-of-words when it isn't. The two can rank
differently, so if you pass offline, run it again with a key before you call it
done.

## Why the folder matters

An evaluation corpus has to be **frozen**. If a lab step can write into the
corpus a later step is graded against, a passing test can go red for a reason
that has nothing to do with the code under test — and you will look for the bug
in the wrong file.

## If it won't rank

That's the exercise, not a bug. Symptoms alone won't separate the two
incidents — both have slow speeds in the evening. What separates them is the
*mechanism*: jitter, packet delay variation on the transport link, and the fact
that PRB utilization and user count stayed normal. The query says exactly that,
and `incident_001` says the opposite (PRB above 90%, users over capacity).

Two things usually fix it:

- **Put the mechanism next to the symptoms.** The chunker splits on blank lines
  and each paragraph is ranked on its own, so a Summary that says "slow evening
  speeds" with the jitter explanation three paragraphs later loses.
- **Describe the evidence, not just the conclusion.** "PRB utilization stayed
  around 40% and user count was within planned capacity" matches the query far
  better than "not a capacity issue".

Don't keyword-stuff. It can pass offline and still fail with a key, because
Gemini embeddings rank by meaning, not by counting shared words.
