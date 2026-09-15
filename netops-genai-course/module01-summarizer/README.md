# Module 1 — Generative AI Foundations: The Incident Summarizer

This hands-on lab introduces the fundamentals of interacting with Large Language Models programmatically using telecom operational data.

---

## What `summarizer.py` Does

1. Loads 5 raw trouble tickets from `data/tickets.csv`.
2. Formats the structured rows into a plain-text prompt buffer.
3. Calls the LLM to synthesize a morning shift-handoff briefing grouped by site, highlighting recurring congestion on `SITE-031` and correlated hardware issues on `SITE-022`.

---

## How to Run

```bash
export GEMINI_API_KEY="..."
python summarizer.py
```

### Try Tweaking the Prompt:
Open `summarizer.py` and modify `prompt`:
1. Ask for bullet points only (no introductory prose).
2. Instruct the model to flag only `CRITICAL` categories.
3. Enforce a hard length constraint: "under 50 words".
Notice how specific instructions directly shape the output.
