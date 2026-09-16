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
    python anomaly_explainer.py CELL-031A --no-examples   # drop the few-shot examples
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm, parse_json_response  # noqa: E402
from mock_tools import THRESHOLDS, get_cell_kpis  # noqa: E402

from typing import List, Literal, get_args  # noqa: E402  (stdlib — cannot fail)

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:  # pragma: no cover
    raise SystemExit(
        "This lab needs pydantic.\n"
        "    pip install pydantic\n"
        "It is in requirements.txt; if you are outside the venv, activate it first."
    )

# The four fault domains, declared ONCE.
#
# This is the module's own "one number, one place" rule applied to itself. The
# taxonomy used to be spelled out twice — here as a list, and again inside the
# Literal below — which is exactly the two-sources-of-truth problem this lab
# warns about. Edit one and the other goes quietly out of step.
#
# `get_args` reads the members back off the type, so the list cannot disagree
# with the validator: there is only one place to edit.
#
# These exact strings are what module07-workflow-patterns/01_prompt_chaining.py
# branches on, so do not shorten the names here.
FaultDomain = Literal[
    "RADIO_ACCESS_INTERFERENCE",
    "CAPACITY_PRB_EXHAUSTION",
    "TRANSPORT_BACKHAUL_JITTER",
    "CORE_SIGNALING_REJECT",
]
FAULT_DOMAINS = list(get_args(FaultDomain))

# Two worked examples — and note what they deliberately are NOT: a near-copy of
# the cell you are about to classify.
#
# They used to be. One of them read "PRB 94%, users 210 against planned capacity
# 150 -> CAPACITY_PRB_EXHAUSTION", and CELL-031A is PRB 96.3% with 214 users
# against a planned capacity of 150. The example WAS the answer, two percent
# away. The model looked like it had learned a taxonomy when all it had done was
# match its nearest neighbour. Both examples also quoted metrics the model is
# never sent — backhaul RTT and planned capacity live nowhere in what
# `_evidence` builds.
#
# So: both examples now use only metrics that actually reach the model, and
# both show domains that are NOT the expected answer. Examples teach the SHAPE
# of the reasoning — which combination of KPIs points where — while the domain
# list in the prompt defines the space of legal answers. Form from the examples,
# bounds from the list.
FEW_SHOT_EXAMPLES = """\
Example — PRB 38%, setup success 88%, drop 6.1%, users 90 -> CORE_SIGNALING_REJECT
  (setups failing with plenty of radio headroom — look past the air interface)
Example — PRB 52%, throughput down 60%, drop 1.2%, users steady -> TRANSPORT_BACKHAUL_JITTER
  (throughput collapses while the radio KPIs stay healthy — the bottleneck is behind the cell)
"""


class AnomalyReport(BaseModel):
    """The shape the rest of a pipeline is allowed to depend on.

    `Literal` is the part that earns its keep: an invented category fails here,
    in microseconds, for free — instead of three modules later inside an agent
    loop where it looks like a tool bug.
    """

    metrics_changed: List[str]
    thresholds_crossed: List[str]
    fault_category: FaultDomain
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
def few_shot_category(evidence, runs=3, use_examples=True):
    """Same question, now with the buckets and two worked examples.

    `use_examples=False` drops the examples and keeps everything else. That is
    the experiment: it turns "few-shot helps" from a claim into a number you
    measured on your own data.

    Be clear about what it does NOT drop. The first line still names all four
    domains, so you are comparing examples against a well-specified instruction,
    not against nothing. If the count barely moves, that is a real result and
    worth saying out loud: the instruction was carrying most of the weight.
    """
    prompt = (
        f"Categorize into EXACTLY ONE of: {', '.join(FAULT_DOMAINS)}\n\n"
        + (FEW_SHOT_EXAMPLES + "\n" if use_examples else "")
        + f"READINGS: {evidence}\nReply with the domain name only."
    )
    return [
        call_llm([{"role": "user", "content": prompt}]).strip()
        for _ in range(runs)
    ]


# --- 3. structured output, enforced at both levels ---------------------------
def _threshold_text():
    """Render mock_tools.THRESHOLDS as prompt text.

    The numbers live in exactly ONE place — the tool — and the prompt asks for
    them. They used to be typed out here as well, which is two sources of truth
    for the same fact: raise the PRB limit in mock_tools and this prompt would
    have gone on confidently asking about 75%, and the model would have gone on
    confidently answering. Nothing would have errored.

    Anything a prompt states about your network belongs in code first and gets
    interpolated in. A number you retype into a prompt is a number that can
    drift away from the system it describes.
    """
    return ", ".join(
        f"{metric} {op} {limit:g}" for metric, (op, limit) in THRESHOLDS.items()
    )


PROMPT_TEMPLATE = """You are a RAN performance analyst. Below is a computed KPI
summary for a single cell — latest reading, rolling averages and deltas.

Identify:
1. metrics_changed - which metrics moved most
2. thresholds_crossed - which of these were crossed: {thresholds}
3. fault_category - EXACTLY ONE of: {domains}
4. summary - one plain-language sentence, at least 20 characters

{examples}
Respond ONLY as JSON with those four keys. No text outside the JSON object.

KPI SUMMARY:
{evidence}
"""


def explain_anomaly(cell_id: str, use_examples: bool = True) -> AnomalyReport:
    """The function the rest of the course would call. Returns a validated
    model, not a dict — so a caller cannot be handed a surprise."""
    _, evidence = _evidence(cell_id)
    prompt = PROMPT_TEMPLATE.format(
        thresholds=_threshold_text(),
        domains=", ".join(FAULT_DOMAINS),
        examples=FEW_SHOT_EXAMPLES if use_examples else "",
        evidence=evidence,
    )
    raw = call_llm([{"role": "user", "content": prompt}], json_mode=True)
    # json_mode got us something that parses. Pydantic decides whether it means
    # what we asked for. Both steps, every time.
    return AnomalyReport(**parse_json_response(raw))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_examples = "--no-examples" not in sys.argv
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

    label = "with two examples" if use_examples else "examples REMOVED"
    print(f"\n2. FEW-SHOT, three runs ({label})")
    for i, answer in enumerate(
            few_shot_category(evidence, use_examples=use_examples), 1):
        ok = "  ok" if answer in FAULT_DOMAINS else "  <- NOT IN THE TAXONOMY"
        print(f"    run {i}: {answer[:60]}{ok}")

    print("\n3. STRUCTURED OUTPUT, validated")
    try:
        report = explain_anomaly(cell_id, use_examples=use_examples)
        print(json.dumps(report.model_dump(), indent=2))
    except ValidationError as e:
        # This is a success, not a crash: the guard caught a malformed answer
        # before anything downstream could act on it.
        print("Pydantic REJECTED the model's answer — which is the point:")
        print(e)

    print(
        "\nYour turn:\n"
        f"  1. python {os.path.basename(__file__)} {cell_id} --no-examples\n"
        "     Drops the two worked examples and changes NOTHING else. Run it\n"
        "     four or five times and count how often the category still\n"
        "     validates. That number is what the examples bought you, measured\n"
        "     on your own data instead of asserted on a slide.\n"
        "     Note what it does not drop: the prompt still lists all four\n"
        "     domains. So you are measuring examples against a well-written\n"
        "     instruction, not against nothing — and 'barely any difference'\n"
        "     is a real, reportable result.\n"
        f"  2. python {os.path.basename(__file__)} CELL-022A\n"
        "     A healthy cell. The answer key is empty, so the question is\n"
        "     whether the MODEL agrees.\n"
        "  3. Add `confidence: float = Field(ge=0, le=1)` to AnomalyReport and\n"
        "     update the prompt. Watch what happens when you forget the prompt."
    )
