"""
anomaly_explainer.py — Module 3 hands-on: the KPI Anomaly Explainer

Reads (mocked) KPI counters for a cell and walks the module's three techniques
in order, so the local path teaches the same thing as the Colab notebook:

    1. zero-shot      — ask loosely, three times, and watch the category drift
    2. few-shot       — give it the taxonomy and two worked examples; drift stops
    3. structured     — json_mode for valid JSON, Pydantic for CORRECT JSON

That last distinction is the one that matters. `json_mode=True` sets the
response MIME type, so the API gives you something that parses. It does not
pass a schema and it does not guarantee your keys — a model can hand you
perfectly valid JSON with entirely different fields in it. The Pydantic model
is what turns "parseable" into "correct", and `data/guardrails.py` in Module 10
is the same mechanism pointed at tool arguments.

Note what gets sent to the model: the computed numbers, but NOT the tool's own
`thresholds_crossed` verdict. Hand the model that field and it is transcribing
an answer it was given, not analysing anything — and you cannot tell from the
output, because the output is right. Held back, the same field becomes the
answer key you grade against. Tools compute. Agents reason.

Run:
    python anomaly_explainer.py CELL-031A   # a real anomaly in the sample data
    python anomaly_explainer.py CELL-022A   # healthy cell
    python anomaly_explainer.py CELL-031A --ablate   # drop the few-shot examples
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm, parse_json_response  # noqa: E402
from mock_tools import get_cell_kpis  # noqa: E402

try:
    from pydantic import BaseModel, Field, ValidationError
    from typing import List, Literal
except ImportError:  # pragma: no cover
    raise SystemExit(
        "This lab needs pydantic.\n"
        "    pip install pydantic\n"
        "It is in requirements.txt; if you are outside the venv, activate it first."
    )

# The four fault domains. This exact list is what module07-workflow-patterns/
# 01_prompt_chaining.py branches on, so do not shorten the names here.
FAULT_DOMAINS = [
    "RADIO_ACCESS_INTERFERENCE",
    "CAPACITY_PRB_EXHAUSTION",
    "TRANSPORT_BACKHAUL_JITTER",
    "CORE_SIGNALING_REJECT",
]

FEW_SHOT_EXAMPLES = """\
Example — PRB 45%, backhaul RTT 120ms above baseline -> TRANSPORT_BACKHAUL_JITTER
Example — PRB 94%, users 210 against planned capacity 150 -> CAPACITY_PRB_EXHAUSTION
"""


class AnomalyReport(BaseModel):
    """The shape the rest of a pipeline is allowed to depend on.

    `Literal` is the part that earns its keep: an invented category fails here,
    in microseconds, for free — instead of three modules later inside an agent
    loop where it looks like a tool bug.
    """

    metrics_changed: List[str]
    thresholds_crossed: List[str]
    fault_category: Literal[
        "RADIO_ACCESS_INTERFERENCE",
        "CAPACITY_PRB_EXHAUSTION",
        "TRANSPORT_BACKHAUL_JITTER",
        "CORE_SIGNALING_REJECT",
    ]
    summary: str = Field(min_length=20, max_length=300)


def _evidence(cell_id):
    """What we send the model: every computed number EXCEPT the tool's own
    `thresholds_crossed` verdict.

    `latest` has to go in — the window's rolling average smooths the spike
    (CELL-031A averages 72.8% PRB while its latest reading is 96.3%), so a model
    given only the average would be right to say nothing crossed 75%. Withhold
    the wrong field and you have not made the task harder, you have made it
    unanswerable.

    What stays out is the verdict. That leaves `thresholds_crossed` free to be
    the answer key you grade the model against, which is the whole exercise.
    """
    kpis = get_cell_kpis(cell_id)
    if not kpis:
        raise ValueError(f"No KPI data found for {cell_id} — check the cell_id.")
    return kpis, json.dumps(
        {
            "latest": kpis["latest"],
            "rolling_avg": kpis["rolling_avg"],
            "delta": kpis["delta"],
        },
        indent=2,
    )


# --- 1. zero-shot: the failure, shown rather than asserted -------------------
def zero_shot_drift(evidence, runs=3):
    """Ask loosely, several times. The answers are all reasonable and no two
    are the same string, which is exactly why code cannot branch on them."""
    prompt = f"Categorize this cell anomaly in a few words:\n{evidence}"
    return [
        call_llm([{"role": "user", "content": prompt}]).strip()
        for _ in range(runs)
    ]


# --- 2. few-shot: taxonomy enforcement ---------------------------------------
def few_shot_category(evidence, runs=3, ablate=False):
    """Same question, now with the buckets and two worked examples.

    `ablate=True` drops the examples and keeps everything else. That is the
    experiment: it turns "few-shot helps" from a claim into a number you
    measured on your own data.
    """
    prompt = (
        f"Categorize into EXACTLY ONE of: {', '.join(FAULT_DOMAINS)}\n\n"
        + ("" if ablate else FEW_SHOT_EXAMPLES + "\n")
        + f"READINGS: {evidence}\nReply with the domain name only."
    )
    return [
        call_llm([{"role": "user", "content": prompt}]).strip()
        for _ in range(runs)
    ]


# --- 3. structured output, enforced at both levels ---------------------------
PROMPT_TEMPLATE = """You are a RAN performance analyst. Below is a computed KPI
summary for a single cell — rolling averages and deltas over the window.

Identify:
1. metrics_changed - which metrics moved most
2. thresholds_crossed - which of these were crossed: PRB utilization > 75%,
   RRC drop rate > 5%, RRC setup success rate < 95%
3. fault_category - EXACTLY ONE of: {domains}
4. summary - one plain-language sentence, at least 20 characters

{examples}
Respond ONLY as JSON with those four keys. No text outside the JSON object.

KPI SUMMARY:
{evidence}
"""


def explain_anomaly(cell_id: str, ablate: bool = False) -> AnomalyReport:
    """The function the rest of the course would call. Returns a validated
    model, not a dict — so a caller cannot be handed a surprise."""
    _, evidence = _evidence(cell_id)
    prompt = PROMPT_TEMPLATE.format(
        domains=", ".join(FAULT_DOMAINS),
        examples="" if ablate else FEW_SHOT_EXAMPLES,
        evidence=evidence,
    )
    raw = call_llm([{"role": "user", "content": prompt}], json_mode=True)
    # json_mode got us something that parses. Pydantic decides whether it means
    # what we asked for. Both steps, every time.
    return AnomalyReport(**parse_json_response(raw))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ablate = "--ablate" in sys.argv
    cell_id = args[0] if args else "CELL-031A"

    kpis, evidence = _evidence(cell_id)
    print(f"--- {cell_id} ---")
    print("ANSWER KEY — the tool computed this and the model is not shown it:")
    for c in kpis["thresholds_crossed"]:
        print(f"    CROSSED  {c['metric']} = {c['value']} "
              f"({c['comparison']} {c['threshold']})")
    if not kpis["thresholds_crossed"]:
        print("    (nothing crossed — this cell is healthy)")

    print("\n1. ZERO-SHOT, three runs — watch the wording move")
    for i, answer in enumerate(zero_shot_drift(evidence), 1):
        print(f"    run {i}: {answer[:90]}")

    label = "few-shot examples REMOVED" if ablate else "with two examples"
    print(f"\n2. FEW-SHOT, three runs ({label})")
    for i, answer in enumerate(few_shot_category(evidence, ablate=ablate), 1):
        ok = "  ok" if answer in FAULT_DOMAINS else "  <- NOT IN THE TAXONOMY"
        print(f"    run {i}: {answer[:60]}{ok}")

    print("\n3. STRUCTURED OUTPUT, validated")
    try:
        report = explain_anomaly(cell_id, ablate=ablate)
        print(json.dumps(report.model_dump(), indent=2))
    except ValidationError as e:
        # This is a success, not a crash: the guard caught a malformed answer
        # before anything downstream could act on it.
        print("Pydantic REJECTED the model's answer — which is the point:")
        print(e)

    print(
        "\nYour turn:\n"
        f"  1. python {os.path.basename(__file__)} CELL-022A\n"
        "     A healthy cell. Note that the tool already knows nothing crossed,\n"
        "     so the interesting question is whether the MODEL agrees.\n"
        f"  2. python {os.path.basename(__file__)} {cell_id} --ablate\n"
        "     Drops the few-shot examples. Run it a few times and count how\n"
        "     often the category still validates. That number is the argument\n"
        "     for few-shot, measured on your own data instead of asserted.\n"
        "  3. Add `confidence: float = Field(ge=0, le=1)` to AnomalyReport and\n"
        "     update the prompt. Watch what happens when you forget the prompt."
    )
