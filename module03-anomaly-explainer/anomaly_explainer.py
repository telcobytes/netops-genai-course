"""
anomaly_explainer.py — Module 3 hands-on: the KPI Anomaly Explainer

Reads (mocked) KPI counters for a cell and walks a ladder of prompts, so the
local path teaches the same thing as the Colab notebook.

Three rungs, same evidence, same model. Only the prompt changes:

    RUNG 1  loose            — no taxonomy, no format constraint
    RUNG 2  taxonomy named   — the four domains listed, no worked examples
    RUNG 3  taxonomy + examples — rung 2 plus two symptom→category pairs

Then the thing that makes any of it safe to build on:

    structured output — json_mode for valid JSON, Pydantic for CORRECT JSON

The ladder exists because "few-shot fixes drift" turned out to be the wrong
attribution. Rung 1 to rung 2 and rung 2 to rung 3 are separate interventions,
and lumping them together credits the examples with work the domain list is
doing. The script runs all three and prints what each rung bought, so the
student reads a number instead of taking the claim on trust.

If rung 3 buys nothing over rung 2 on your data, that is a result. Report it.
Module 10 is where this gets done properly, with a harness — this is the first
taste of it.

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
    python anomaly_explainer.py CELL-031A            # a real anomaly in the sample data
    python anomaly_explainer.py CELL-022A            # healthy cell
    python anomaly_explainer.py CELL-031A --runs=10  # ten samples per rung, not three
    python anomaly_explainer.py CELL-031A --no-examples   # drop the examples from the
                                                          # validated report as well

    Needs GEMINI_API_KEY. Without it, the run prints how to set one and stops —
    there is no offline mode here.
"""

import json
import os
import sys
from collections import Counter

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


# --- RUNG 1: loose. The failure, shown rather than asserted -------------------
def loose_category(evidence, runs=3):
    """Ask loosely, several times. The answers are all reasonable and no two are
    the same string, which is exactly why code cannot branch on them.

    Note what this prompt does NOT do: it never says what the categories are,
    and it never says how to reply. Both of those are fixed at rung 2, and
    keeping them separate from the examples is the whole point of the ladder.
    """
    prompt = f"Categorize this cell anomaly in a few words:\n{evidence}"
    return [
        call_llm([{"role": "user", "content": prompt}]).strip()
        for _ in range(runs)
    ]


# --- RUNGS 2 and 3: the taxonomy, with and without worked examples ------------
def constrained_category(evidence, runs=3, use_examples=True):
    """Same question, now naming the four domains and pinning the reply format.

    `use_examples=True` is rung 3, `False` is rung 2. That single switch is the
    experiment, and it is deliberately the ONLY difference between them — same
    domain list, same "reply with the domain name only", same evidence.

    It is called `constrained_category` rather than `few_shot_category` because
    at rung 2 there is no few-shot in it, and a function whose name asserts the
    mechanism it is supposed to be testing is how you end up measuring the wrong
    thing.
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


def _tally(answers):
    """Conformance and self-agreement — deliberately NOT correctness.

    `in_taxonomy` counts strings the rest of the course can branch on. That is a
    statement about SHAPE. It says nothing about whether the answer is true, and
    conflating the two is the mistake this script exists to expose.

    `modal_n` is how often the rung agreed with itself. A rung can be perfectly
    stable and perfectly wrong, and on a healthy cell it is.
    """
    in_taxonomy = sum(1 for a in answers if a in FAULT_DOMAINS)
    modal, modal_n = Counter(answers).most_common(1)[0] if answers else ("", 0)
    return in_taxonomy, len(set(answers)), modal, modal_n


def _show(answers, runs, listed=False):
    """Print a rung's answers, then its conformance line."""
    if listed:
        for i, a in enumerate(answers, 1):
            print(f"      run {i:>2}: {_flat(a)}")
    else:
        for a, n in Counter(answers).most_common():
            flag = "" if a in FAULT_DOMAINS else "   <- NOT IN THE TAXONOMY"
            print(f"      {_flat(a, 46):<48} x{n}{flag}")
    in_tax, distinct, modal, modal_n = _tally(answers)
    extra = f", {distinct} distinct strings" if listed else ""
    print(f"      -> {in_tax}/{runs} in the taxonomy{extra}")
    return in_tax, modal, modal_n


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


def _flat(s, width=72):
    """One line, please. Loose answers sometimes come back with newlines and a
    bulleted explanation, which wrecks the column alignment the ladder needs."""
    s = " ".join(s.split())
    return s if len(s) <= width else s[:width - 1] + "…"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_examples = "--no-examples" not in sys.argv
    runs = next((int(a.split("=", 1)[1]) for a in sys.argv[1:]
                 if a.startswith("--runs=")), 3)
    cell_id = args[0] if args else "CELL-031A"

    kpis, evidence = _evidence(cell_id)
    print(f"--- {cell_id} ---")
    print("ANSWER KEY — the tool computed this and the model is not shown it:")
    for c in kpis["thresholds_crossed"]:
        print(f"    CROSSED  {c['metric']} = {c['value']} "
              f"({c['comparison']} {c['threshold']})")
    if not kpis["thresholds_crossed"]:
        print("    (nothing crossed — this cell is healthy)")

    print(f"\nTHE LADDER — same evidence, same model, {runs} runs per rung.")
    print("Only the prompt changes.")
    if runs * 3 > 20:
        print(f"({runs * 3} model calls. The free tier is rate-limited, so give "
              f"it a minute.)")

    print("\n  RUNG 1  loose  ·  no taxonomy named, no format asked for")
    rung1 = loose_category(evidence, runs=runs)
    v1, _, _ = _show(rung1, runs, listed=True)

    print("\n  RUNG 2  taxonomy named  ·  no worked examples")
    rung2 = constrained_category(evidence, runs=runs, use_examples=False)
    v2, modal2, n2 = _show(rung2, runs)

    print("\n  RUNG 3  taxonomy + two worked examples")
    rung3 = constrained_category(evidence, runs=runs, use_examples=True)
    v3, modal3, n3 = _show(rung3, runs)

    print("\n  WHAT EACH RUNG BOUGHT  (conformance — shape, not truth)")
    print(f"      naming the taxonomy :  {v1}/{runs} -> {v2}/{runs}"
          f"   ({v2 - v1:+d})")
    print(f"      adding the examples : {v2:>2}/{runs} -> {v3}/{runs}"
          f"   ({v3 - v2:+d})")
    print("\n  SELF-AGREEMENT  (a rung can be perfectly stable and perfectly wrong)")
    print(f"      rung 2: {n2}/{runs} on {modal2}")
    print(f"      rung 3: {n3}/{runs} on {modal3}")
    if modal2 != modal3:
        print("      ^ the examples did not change how OFTEN it agreed with")
        print("        itself. They changed WHAT it agreed on. Those are very")
        print("        different interventions and only one of them is progress.")

    healthy = not kpis["thresholds_crossed"]
    if healthy:
        print(f"\n  CORRECTNESS — read this before you celebrate a "
              f"{runs}/{runs}")
        print(f"      The answer key for {cell_id} is EMPTY. Nothing crossed.")
        print("      So the correct answer is \"no fault\" — and NO member of")
        print("      the taxonomy says that. All four are faults.")
        print(f"\n      in the taxonomy : {v3}/{runs}")
        print(f"      actually correct : 0/{runs}    <- by construction")
        print("\n      Every schema-conformant answer above is false, the Literal")
        print("      passed all of them, and Pydantic would too. The constraint")
        print("      did not merely fail to help: it removed the model's ability")
        print("      to say the true thing. Rung 1 could say \"nothing is wrong\".")
        print("      Rungs 2 and 3 were forbidden from saying it.")
        print("\n      json_mode buys parseable. Pydantic buys WELL-FORMED.")
        print("      Neither one buys true. A validator cannot save you from a")
        print("      taxonomy with no word for \"fine\" — and an agent wired this")
        print("      way opens a ticket on every healthy cell in the network.")
        print("\n      The fix is your exercise. See solution_no_fault.py once")
        print("      you have tried it.")
    elif v3 - v2 <= 0 < v2 - v1:
        print(f"\n      On {cell_id}, naming the four domains did the work and the")
        print("      worked examples added nothing measurable. That is a result,")
        print("      not a failure, and it is one you could only get by measuring.")
        print("      You would otherwise have paid for those examples in every")
        print("      prompt, forever, and never known.")
        print(f"\n      Before you generalise: {runs} runs is a small sample, and")
        print("      this cell has one obvious bucket. Run CELL-022A — the")
        print("      healthy one — before you decide what you believe.")

    label = "with examples" if use_examples else "examples REMOVED"
    print(f"\nSTRUCTURED OUTPUT, validated ({label})")
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
        f"  1. python {os.path.basename(__file__)} CELL-022A --runs=10\n"
        "     The healthy cell. Watch ten validated, schema-conformant, wrong\n"
        "     answers go past. Run this one before anything else.\n"
        "\n"
        "  2. THE FIX — give the taxonomy a word for \"fine\":\n"
        "       a) add \"NO_FAULT_DETECTED\" to the FaultDomain Literal\n"
        "       b) tell the prompt when to use it\n"
        "     Re-run CELL-022A. Then re-run CELL-031A to check you have not\n"
        "     broken the case that already worked. Two lines of code.\n"
        "     Stuck, or want to compare? python solution_no_fault.py\n"
        "\n"
        f"  3. python {os.path.basename(__file__)} CELL-031A --runs=10\n"
        "     The broken cell, ten runs. Three samples per rung is a demo;\n"
        "     ten is closer to evidence.\n"
        "     Write down what each rung bought — Module 10 asks the same\n"
        "     question with a proper harness and you will want the comparison.\n"
        "\n"
        "  4. Add `confidence: float = Field(ge=0, le=1)` to AnomalyReport and\n"
        "     update the prompt. Watch what happens when you forget the prompt."
    )
