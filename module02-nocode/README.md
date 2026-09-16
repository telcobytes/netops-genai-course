# Module 2 — The No-Code Baseline (and Where It Runs Out)

**There is no script and no notebook in this folder, and that is the point.**

Every other module hands you code. This one hands you an hour you can use on Monday
without installing anything, without an API key, and without asking IT for
permission. If you are on a locked-down operator or vendor laptop, this is the module
that still works.

**What you need:** a browser and a Google account. Nothing else.
**Time:** about 10 minutes for both scenarios, plus 2 for the probes.

Open [notebooklm.google.com](https://notebooklm.google.com) and create a new
notebook. Anything that grounds its answers strictly in documents you supply will do
— the questions below are the lab, not the product.

---

## Scenario 1 — The NOC inbox (2 minutes)

Upload [`../data/module2_notebooklm_sample_doc.md`](../data/module2_notebooklm_sample_doc.md).

It is a stand-in for the bundle that piles up unread in a real NOC inbox: vendor
change requests, maintenance notices, incident summaries. Ask it:

1. **What in here is customer-impacting?**
2. **What needs a maintenance window, and when?**
3. **What collides with something already open?**

You should get a briefing that pulls CR-2201, CR-2214, the fiber work and the
CELL-031A congestion item into one page, and — this is the part to notice — every
claim carries a citation back to the section it came from.

This one is meant to be easy. It is the warm-up.

---

## Scenario 2 — A real 3GPP specification (8 minutes)

This is the one that changes minds. Download:

**3GPP TS 38.331 v16.1.0 — 5G NR Radio Resource Control (RRC), protocol specification**

<https://www.etsi.org/deliver/etsi_ts/138300_138399/138331/16.01.00_60/ts_138331v160100p.pdf>

Upload the PDF directly — no conversion, no splitting. Then ask:

1. **Show me the contents of system information block 1.**
2. **Which fields in SIB1 are optional, and which are conditionally present?**
3. **What does the UE do on reception of SIB1?**

Do not stop at the answer. **Open the PDF at the clause it cited and check it.**
That habit — answer, then citation, then the source — is the whole reason this
module exists, and it is the same habit Module 4 rebuilds in code.

### Two notes on the version, because they cause real confusion

- **ETSI numbering.** ETSI republishes 3GPP specifications with a `1` prefixed to
  the number, so 3GPP TS 38.331 is ETSI TS 138 331. Same document, same clause
  numbers.
- **`v16.1.0` means Release 16.** If you grab a different version you will get a
  different SIB1 — fields have been added since — and the lab will look broken when
  it is not. Pin the version you are reading. This is the norm in real work, not a
  quirk of the lab.

---

## Probe 1 — Grounded vs. ungrounded (1 minute)

Open a plain chatbot — no upload, no retrieval — and ask it the **same** first
question: *show me the contents of system information block 1.*

It will answer. Fluently. Watch for two things:

- **It may blend NR SIB1 with LTE SIB1.** If you have worked either air interface
  you will spot it in a second.
- **Ask it which release it answered from.** It cannot tell you. There is no
  document behind the answer, so there is nothing to name.

In this field "which release?" is the first question in any serious conversation.
NotebookLM, reading v16.1.0, can answer it and point at the clause. That difference
*is* grounding. Everything Module 4 builds is a way to get it without a browser tab.

## Probe 2 — Where grounding stops (1 minute)

Go back to the notebook holding Scenario 1's bundle and ask:

> **What is CELL-031A's current PRB utilisation?**

Then ask a plain chat window — nothing uploaded — the same question.

Expect two different failures. The grounded notebook will most likely tell you its
sources don't cover it, which is correct behaviour and still a dead end: you needed
the number. The chat window will give you a number. It has never seen a counter in
its life.

Grounding bounds the **sources**. It does not bound the **confidence**, and neither
interface marks the edge of what it actually knows. That is the single habit to carry
out of this module: know where your sources end, because the tool will not tell you.

---

## Then try it on your own material

The three document types from the slides, on documents you actually own:

- **3GPP clause lookup** — "which clause covers RRC re-establishment after radio
  link failure, and what are the timer values?"
- **Vendor change-request risk** — a 40-page CR: what is customer-impacting, what
  needs a window, what conflicts with something open. This is the highest-value
  hour in the module.
- **Post-incident synthesis** — a year of RCA write-ups: which failures keep
  recurring at the same sites. Nobody reads all of them, which is exactly why the
  pattern stays invisible.

Check your employer's policy before uploading anything non-public. The two lab
documents above are both public, which is deliberate.

**Limits worth knowing:** the free tier allows 50 sources per notebook and roughly
500,000 words (or 200 MB) per source. TS 38.331 fits comfortably inside one source.

## If your laptop blocks it

Some operator networks block NotebookLM outright. The lab still works:

- Do it on a personal device — there is nothing to install and no key to manage.
- Or use any assistant that lets you attach a file and restricts its answers to it,
  and run the same questions and the same two probes.
- Or read scenario 2's expected shape from the slides and skip to Module 3. Nothing
  later in the course depends on this module's output.

---

## The boundary, which is the actual lesson

A notebook-style tool grounds every answer in the text you gave it. That buys you
near-zero hallucination *from outside sources*, and traceability you can check — and
it buys you nothing at all about your live network.

It has never seen CELL-031A. It cannot query a counter, inspect neighbour topology,
or trigger an action — whether it admits that or answers anyway. Probe 2 is that
boundary, felt rather than described.

You are also in the driver's seat for every single step: you noticed the problem, you
chose the document, you typed the question, you copied the answer somewhere. Nothing
here decides anything on its own.

That is the line Module 5 crosses.
