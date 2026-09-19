# Module 1 — Generative AI Foundations: The Incident Summarizer

Your first tool, built on day one: five raw trouble tickets in, one shift-handoff
briefing out. Two scripts, in the order you should run them.

---

## How to run

There is **no offline mode in this module** — every script here calls a model, because
what the model does *is* the lesson. Without a key each one prints how to set one and
stops.

```bash
export GEMINI_API_KEY="..."       # free, no credit card: aistudio.google.com
cd module01-summarizer

python gemini_quickstart.py       # the raw 3-line API call
python summarizer.py              # the actual lab
```

Or open [`01_incident_summarizer.ipynb`](01_incident_summarizer.ipynb) in Colab, which
covers the same ground plus a rendered ticket table and the ungrounded-question probe.

---

## 1. `gemini_quickstart.py` — the pattern with nothing around it

Initialize a client, call the model, read the text. That is the whole API.

This is the **only file in the course that imports the Gemini SDK directly** instead of
going through `data/llm_client.py`, and that is deliberate: see the raw call once, so
that when the wrapper shows up on the next script you know it is not hiding anything
surprising.

One line is worth reading twice:

```python
model=resolve_model()      # not model="gemini-3.6-flash"
```

Google retires model ids on its own schedule, and this course has already had two die
mid-lecture. The candidate list lives in `data/llm_client.py` and nowhere else, so a
retirement is one edit rather than fourteen. **A model id typed into a lab is a 404
waiting for a student.**

## 2. `summarizer.py` — the lab

1. Loads five trouble tickets from `data/tickets.csv`.
2. Flattens the rows into **plain prose** before prompting — models handle prose better
   than raw CSV.
3. Asks for a NOC shift-handoff briefing: grouped by site, urgent or recurring items
   called out, under 150 words.

**What you should see:** `Loaded 5 tickets.`, then a briefing organised by site rather
than by ticket. Two of the five tickets are SITE-031 congestion and two are SITE-022
(one voice, one hardware), so a good answer groups those rather than listing all five
in a row — that grouping is the judgement call you asked the prompt to make for you.

The wording will differ every run. That is not a defect yet, and Module 3 is where it
becomes one.

### The prompt is the whole lab

```
You are helping a NOC shift-handoff.                        <- ROLE
Below are open and recently closed trouble tickets.         <- THE DATA
Write a short shift-handoff briefing:                       <- TASK
group by site, call out anything urgent or recurring,       <- CONSTRAINTS
and keep it under 150 words.                                <- BUDGET
```

Five parts, and the one to linger on is **CONSTRAINTS** — "group by site, flag anything
recurring" are the judgement calls a NOC engineer would otherwise redo by hand every
shift. The model cannot ask you what you meant. Every ambiguity you leave in, it
resolves on its own, confidently.

---

## Your turn

Change **one thing at a time** and compare. The point is to feel how much of the output
shape the prompt actually controls:

1. Bullet points only, no introductory prose.
2. Flag only the `CRITICAL`-sounding categories.
3. Enforce a harder budget: under 50 words.

Then the one that is actually interesting: **remove `group by site` and see whether it
groups anyway.** It probably will, some of the time. "Some of the time" is the property
this whole course is about — Module 3 is where you stop asking nicely and start
enforcing.

---

**Next:** Module 2 needs no code at all — it is the no-code baseline, and where it runs
out. Then Module 3, where the output stops being prose a human reads and becomes JSON
your code can act on.
