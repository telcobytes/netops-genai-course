"""
solution_no_fault.py — the worked answer to exercise 2

Try it yourself first. The exercise is two lines, and finding them yourself is
the whole value. This file is here so that being stuck costs you five minutes
instead of an evening.

THE PROBLEM, RESTATED

Run `anomaly_explainer.py CELL-022A --runs=10` and you get ten fault
classifications on a cell where nothing is wrong. PRB 57%, setup success 98.7%,
drops 1.3%, throughput flat. The tool's answer key is empty. And every single
model answer passes the `Literal`, would pass Pydantic, and is false.

That is not the model misbehaving. It did exactly what it was told. The prompt
said "categorize into EXACTLY ONE of" four strings, and all four are faults:

    RADIO_ACCESS_INTERFERENCE
    CAPACITY_PRB_EXHAUSTION
    TRANSPORT_BACKHAUL_JITTER
    CORE_SIGNALING_REJECT

There is no member meaning "nothing is wrong". So on a healthy cell a
schema-conformant answer is guaranteed to be wrong — not likely to be, not
usually, *guaranteed*. The constraint did not fail to help. It removed the
model's ability to say the true thing.

Notice which rung got it right. The loose, unconstrained prompt — the one the
module spends two slides criticising — said "Normal Operation, no anomaly" ten
times out of ten. It was unusable by code and it was correct. The constrained
rungs were usable by code and wrong. Those are different axes, and the whole
module turns on not confusing them.

An agent wired this way opens a ticket on every healthy cell in the network.

THE FIX

Give the taxonomy a word for "fine", and tell the prompt when to reach for it.
That is it. A classifier with no null class will always classify.

WHY THIS FILE RE-SPELLS THE FOUR STRINGS

`anomaly_explainer.py` declares the taxonomy once and derives the list with
`get_args`, which is the right pattern and you should keep it. This file spells
out five so you can see the edit you would make. In your own fix you change the
`Literal` in place and `FAULT_DOMAINS` follows on its own — that is the point of
declaring it once.

Run:
    python solution_no_fault.py              # both cells, 5 runs each
    python solution_no_fault.py --runs=10

    Needs GEMINI_API_KEY. Without it, the run prints how to set one and stops —
    there is no offline mode here.
"""

import os
import sys
from collections import Counter
from typing import List, Literal, get_args

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from anomaly_explainer import (  # noqa: E402
    FAULT_DOMAINS,
    FEW_SHOT_EXAMPLES,
    _evidence,
    _flat,
    _threshold_text,
    call_llm,
    parse_json_response,
)

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:  # pragma: no cover
    raise SystemExit("This lab needs pydantic:  pip install pydantic")


# --- the fix, line 1 of 2 ----------------------------------------------------
# One extra member. Everything else about the taxonomy is unchanged, and the
# four fault strings keep their exact spelling because module07-workflow-
# patterns/01_prompt_chaining.py still branches on them.
FaultDomainV2 = Literal[
    "RADIO_ACCESS_INTERFERENCE",
    "CAPACITY_PRB_EXHAUSTION",
    "TRANSPORT_BACKHAUL_JITTER",
    "CORE_SIGNALING_REJECT",
    "NO_FAULT_DETECTED",
]
DOMAINS_V2 = list(get_args(FaultDomainV2))

# --- the fix, line 2 of 2 ----------------------------------------------------
# A member the prompt never mentions is a member the model will not use. Adding
# it to the Literal alone would just move the failure: the model would keep
# guessing a fault and Pydantic would keep accepting it.
#
# Say when to use it, in terms of something the model can actually see. It gets
# `latest`, `rolling_avg` and `delta` — not the tool's verdict — so the rule has
# to be expressed in readings, not in "if nothing crossed".
NULL_CLASS_RULE = (
    "Use NO_FAULT_DETECTED when every reading sits inside its normal operating "
    "range and none of the limits above are breached. A healthy cell is a valid "
    "answer. Do not pick the closest-sounding fault when there is no fault."
)


class AnomalyReportV2(BaseModel):
    """Same model as the lab's, with the wider enum.

    `Literal` is still doing the same job — it still rejects an invented fifth
    category. The difference is that "healthy" is no longer an invented category.
    """

    metrics_changed: List[str]
    thresholds_crossed: List[str]
    fault_category: FaultDomainV2
    summary: str = Field(min_length=20, max_length=300)


PROMPT_V2 = """You are a RAN performance analyst. Below is a computed KPI
summary for a single cell — latest reading, rolling averages and deltas.

Identify:
1. metrics_changed - which metrics moved most
2. thresholds_crossed - which of these were crossed: {thresholds}
3. fault_category - EXACTLY ONE of: {domains}
   {null_rule}
4. summary - one plain-language sentence, at least 20 characters

{examples}
Respond ONLY as JSON with those four keys. No text outside the JSON object.

KPI SUMMARY:
{evidence}
"""


def categorize(evidence, domains, runs, null_rule=""):
    """The rung-3 prompt, parameterised by which taxonomy it is given."""
    prompt = (
        f"Categorize into EXACTLY ONE of: {', '.join(domains)}\n"
        + (f"{null_rule}\n" if null_rule else "")
        + "\n" + FEW_SHOT_EXAMPLES + "\n"
        + f"READINGS: {evidence}\nReply with the domain name only."
    )
    return [
        call_llm([{"role": "user", "content": prompt}]).strip()
        for _ in range(runs)
    ]


def score(answers, domains, healthy):
    """Correct is derivable from the answer key, with no prose matching.

    If nothing crossed, the only correct answer is the null class. If something
    crossed, any real fault domain is defensible and the null class is not — we
    do not assert WHICH fault, because that is a judgement the tool has not made
    and a substring check is how this course got burned before.
    """
    in_tax = sum(1 for a in answers if a in domains)
    if healthy:
        correct = sum(1 for a in answers if a == "NO_FAULT_DETECTED")
    else:
        correct = sum(1 for a in answers
                      if a in domains and a != "NO_FAULT_DETECTED")
    return in_tax, correct


def run_cell(cell_id, runs):
    kpis, evidence = _evidence(cell_id)
    healthy = not kpis["thresholds_crossed"]

    print(f"\n{'=' * 72}")
    print(f"{cell_id}  —  answer key: "
          + ("EMPTY, nothing crossed" if healthy
             else f"{len(kpis['thresholds_crossed'])} thresholds crossed"))
    for c in kpis["thresholds_crossed"]:
        print(f"    CROSSED  {c['metric']} = {c['value']} "
              f"({c['comparison']} {c['threshold']})")

    for label, domains, rule in (
        ("BEFORE  four fault domains, no null class", FAULT_DOMAINS, ""),
        ("AFTER   five domains, NO_FAULT_DETECTED added",
         DOMAINS_V2, NULL_CLASS_RULE),
    ):
        print(f"\n  {label}")
        answers = categorize(evidence, domains, runs, rule)
        for a, n in Counter(answers).most_common():
            flag = "" if a in domains else "   <- NOT IN THE TAXONOMY"
            print(f"      {_flat(a, 46):<48} x{n}{flag}")
        in_tax, correct = score(answers, domains, healthy)
        print(f"      -> in the taxonomy {in_tax}/{runs}"
              f"      actually correct {correct}/{runs}")

    print("\n  VALIDATED REPORT, with the null class")
    prompt = PROMPT_V2.format(
        thresholds=_threshold_text(),
        domains=", ".join(DOMAINS_V2),
        null_rule=NULL_CLASS_RULE,
        examples=FEW_SHOT_EXAMPLES,
        evidence=evidence,
    )
    raw = call_llm([{"role": "user", "content": prompt}], json_mode=True)
    try:
        report = AnomalyReportV2(**parse_json_response(raw))
        print(f"      fault_category     : {report.fault_category}")
        print(f"      thresholds_crossed : {report.thresholds_crossed}")
        print(f"      summary            : {_flat(report.summary, 60)}")
        agrees = bool(report.thresholds_crossed) != (
            report.fault_category == "NO_FAULT_DETECTED")
        print(f"      internally consistent? "
              f"{'yes' if agrees else 'NO — category contradicts the crossings'}")
    except ValidationError as e:
        print("      Pydantic REJECTED it, which is the guard working:")
        print(f"      {e}")


if __name__ == "__main__":
    runs = next((int(a.split("=", 1)[1]) for a in sys.argv[1:]
                 if a.startswith("--runs=")), 5)

    print("SOLUTION — exercise 2: give the taxonomy a word for \"fine\"")
    print(f"\nSame prompt, same model, same evidence. The only variable is "
          f"whether\nthe taxonomy contains NO_FAULT_DETECTED. {runs} runs each.")

    for cell_id in ("CELL-022A", "CELL-031A"):
        run_cell(cell_id, runs)

    print(f"\n{'=' * 72}")
    print("""
WHAT TO TAKE FROM THIS

CELL-022A is the cell the fix is for: before, every conformant answer was
false; after, the model can say what is true and the validator still guards
the field.

CELL-031A is the regression check, and it is the half people skip. A fix that
repairs the healthy cell by making the model timid on the broken one has not
fixed anything — it has moved the failure somewhere you were not looking.

The general rule is worth more than the patch: a classifier with no null class
will always classify. Before you constrain a model to a fixed set, ask what it
should say when none of them apply — and if the honest answer is "none of
these", that has to be a member too.

And notice what `Literal` did and did not do for you. It still rejects an
invented fifth category, which is exactly what you want. It never had an
opinion about whether the category was TRUE. json_mode buys parseable,
Pydantic buys well-formed, and neither one buys correct. Deciding whether an
answer is right is a different job, it needs a golden set and a harness, and
it is what Module 10 is for.
""".strip())
