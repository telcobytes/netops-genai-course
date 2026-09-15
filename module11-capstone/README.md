# Module 11 — Capstone: The Autonomous NOC Copilot

The culmination of the course: chaining every prior module into a single autonomous triage pipeline for `CELL-031A`.

---

## The End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DETECT: Ingest batch alarms and filter to MAJOR/CRITICAL │
│ 2. RETRIEVE: Pull prior SOPs and incident runbooks (RAG)    │
│ 3. DIAGNOSE: ReAct reasoning loop calling live PM/FM tools   │
│ 4. DRAFT: Produce structured RCA & gate ticket with human   │
└─────────────────────────────────────────────────────────────┘
```

---

## How to Run

```bash
export GEMINI_API_KEY="..."
python noc_copilot.py
```
