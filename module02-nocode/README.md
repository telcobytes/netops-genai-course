# Module 2 — AI in Your Daily Telecom Workflow (No-Code)

**There is no script and no notebook in this folder, and that is the point.**

Every other module hands you code. This one hands you an hour you can use on Monday
without installing anything, without an API key, and without asking IT for
permission. If you are on a locked-down operator or vendor laptop, this is the module
that still works.

## What you do

Upload [`../data/module2_notebooklm_sample_doc.md`](../data/module2_notebooklm_sample_doc.md)
into a notebook-style AI tool — NotebookLM, or any assistant that grounds its answers
in documents you supply — and ask it to produce a one-page briefing.

The file is a stand-in for the dense bundle that piles up unread in a real NOC inbox:
vendor change requests, maintenance notices, incident summaries.

Three questions worth asking it:

1. **What in here is customer-impacting?**
2. **What needs a maintenance window, and when?**
3. **What collides with something already open?**

Then try the three document types the module covers on your own material: a 3GPP
clause lookup against a spec PDF, a vendor change-request risk read, and a
post-incident synthesis across a year of RCA write-ups.

## The boundary, which is the actual lesson

A notebook-style tool grounds every answer in the text you gave it. That buys you
near-zero hallucination *from outside sources* — and buys you nothing at all about
your live network.

It has never seen CELL-031A. It cannot query a counter, inspect neighbour topology,
or trigger an action. Ask it anyway and it will produce a confident answer built from
nothing.

You are also in the driver's seat for every single step: you noticed the problem, you
chose the document, you typed the question, you copied the answer somewhere. Nothing
here decides anything on its own.

That is the line Module 5 crosses.
