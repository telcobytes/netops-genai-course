# Module 3 — Prompt Engineering: The KPI Anomaly Explainer

This module moves from plain prose generation to **Structured JSON Output**, the critical software bridge between prompts and autonomous code execution.

---

## What `anomaly_explainer.py` Does

1. Pulls time-series KPI counters for a given cell (`CELL-031A` or `CELL-022A`) from `mock_tools.py`.
2. Asks the model to identify which metric changed the most, which operational thresholds were breached (PRB > 75%, RRC Drop > 5%), and summarize the event.
3. Enforces that the model responds **strictly in valid JSON** conforming to defined keys: `"metrics_changed"`, `"thresholds_crossed"`, and `"summary"`.

---

## How to Run

```bash
export GEMINI_API_KEY="..."

# Test on the congested cell:
python anomaly_explainer.py CELL-031A

# Test on a healthy cell (negative telemetry verification):
python anomaly_explainer.py CELL-022A
```
Confirm that `CELL-022A` returns an empty `thresholds_crossed` list — verifying that your prompt does not hallucinate false alarms on healthy sites.
