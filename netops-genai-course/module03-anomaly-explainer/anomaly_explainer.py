"""
anomaly_explainer.py — Module 3 hands-on: the KPI Anomaly Explainer

Reads live (mocked) KPI counters for a cell and asks an LLM to explain what
changed, whether known thresholds were crossed, and to summarize in plain
language — with the response FORMAT enforced as JSON, not just requested.

Run:
    python anomaly_explainer.py CELL-031A   # has a real anomaly in the sample data
    python anomaly_explainer.py CELL-022A   # healthy cell — should report nothing wrong
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm, parse_json_response  # noqa: E402
from mock_tools import get_cell_kpis  # noqa: E402

PROMPT_TEMPLATE = """You are a RAN performance analyst. Below is a time series of
KPI readings for a single cell, most recent last. Identify:
1. Which metric(s) changed the most, with the actual before/after numbers
2. Whether any of these commonly-used thresholds were crossed: PRB utilization > 75%,
   RRC drop rate > 5%, RRC setup success rate < 95%
3. A one-line plain-language summary of what's happening

Respond ONLY as JSON with keys: "metrics_changed", "thresholds_crossed", "summary".
Do not include any text outside the JSON object.

KPI READINGS:
{readings}
"""


def explain_anomaly(cell_id: str) -> dict:
    readings = get_cell_kpis(cell_id)
    if not readings:
        raise ValueError(f"No KPI data found for {cell_id} — check the cell_id.")
    prompt = PROMPT_TEMPLATE.format(readings=json.dumps(readings, indent=2))
    raw = call_llm([{"role": "user", "content": prompt}], json_mode=True)
    return parse_json_response(raw)


if __name__ == "__main__":
    cell_id = sys.argv[1] if len(sys.argv) > 1 else "CELL-031A"
    result = explain_anomaly(cell_id)
    print(f"--- Anomaly analysis for {cell_id} ---\n")
    print(json.dumps(result, indent=2))

    # Hands-on exercise (from the lecture): run this against CELL-022A (no anomaly
    # in the sample data) and confirm thresholds_crossed comes back empty/false —
    # a prompt that always says "something's wrong" regardless of input isn't
    # actually analyzing anything.
