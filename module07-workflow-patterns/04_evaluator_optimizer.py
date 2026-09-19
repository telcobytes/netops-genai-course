"""
PATTERN 4 — EVALUATOR-OPTIMIZER

Generate, critique, revise — bounded. A second model call scores the first
one's output against explicit criteria and sends it back if it falls short.

THE RULE THAT MAKES OR BREAKS THIS PATTERN:

    A critic only helps if it knows something the generator didn't.

Self-critique with identical context mostly produces confident hedging, and
occasionally talks a correct answer into a wrong one. The critic needs an
ASYMMETRIC ADVANTAGE — a checklist, a fresh context, a tool result the drafter
never saw, or a schema it wasn't conditioned on.

Here the advantage is the course's 4-layer diagnostic order. The critic isn't
asked "is this RCA good?" — a question with no checkable answer. It's asked
"did this RCA rule out Physical/RF before blaming Core?", which is a fact.

Note this is NOT the same thing as Module 10's evaluation:
  - Module 10 = offline testing. Golden sets, regressions. Development time.
  - This      = a runtime loop that improves THIS answer. Inference time,
                2-4x the tokens, and it never tells you the agent works.
You want both, for different reasons.

Run:  python 04_evaluator_optimizer.py [--mock]
"""

import json
import sys

from _common import ask, banner, GREEN, YELLOW, RED, CYAN, BOLD, RESET

sys.path.append("../data")
from mock_tools import get_cell_kpis, get_active_alarms, lookup_topology  # noqa: E402

MAX_REVISIONS = 2  # Not optional. See the note at the bottom of this file.

# The critic's asymmetric advantage: a domain checklist the drafter never sees.
DIAGNOSTIC_LAYERS = [
    ("Physical / RF", "antenna tilt, VSWR, hardware faults — cheapest and most common"),
    ("Transport / Backhaul", "link latency, jitter, packet loss between site and core"),
    ("Control-Plane Signalling", "RRC/NAS setup failures, reject causes, timer expiries"),
    ("Core Services", "AMF/SMF/PCF — checked last, least likely and most expensive"),
]

# The first draft is SEEDED, in both modes, and it is worth knowing why.
#
# Measured: asked for this RCA cold, the live model went straight to
# capacity exhaustion — the right answer — and the critic passed it on the first
# attempt. A loop that never loops teaches nothing, so attempt 0 is a deliberately
# weak draft: the mistake a tired engineer makes at 3am, blaming the most
# expensive layer because RRC rejects are the loudest thing on the screen.
#
# Everything after that is real: the critic reads this draft, names what it
# skipped, and a live model writes the revision.
DRAFTS = [
    # Deliberately skips transport — the exact mistake the checklist catches.
    ("Impact: CELL-031A subscribers see degraded throughput and call setup failures.\n"
     "Likely cause: Core signalling congestion at the AMF is rejecting RRC setups.\n"
     "Recommended action: Escalate to the core team for AMF capacity review."),
    ("Impact: CELL-031A subscribers see degraded throughput and call setup failures.\n"
     "Likely cause: RF geometry is nominal and backhaul latency is within baseline; "
     "active users (214) exceed planned capacity (150), saturating PRB and degrading "
     "RRC setup as a downstream effect rather than a core fault.\n"
     "Recommended action: Confirm neighbour health, apply temporary handover bias, "
     "raise a capacity ticket for RF planning."),
]

CRITIQUES = [
    {"passed": False, "missing": ["Physical / RF", "Transport / Backhaul"],
     "note": "Jumps straight to Core — the most expensive layer — without ruling out the two cheapest. "
             "RRC degradation here is a symptom of saturation, not evidence of a core fault."},
    {"passed": True, "missing": [],
     "note": "Walks RF and transport before attributing cause, and correctly frames RRC degradation "
             "as downstream of capacity."},
]


def draft_rca(cell_id: str, attempt: int, feedback: str = "") -> str:
    kpis = get_cell_kpis(cell_id)
    # The first draft is asked for three lines and nothing else. That is the point:
    # it has no idea a reviewer exists, so it writes what anyone writes under
    # pressure — the conclusion, without the ruling-out. The critic's feedback is
    # what teaches it, which is the entire pattern. Telling the drafter up front
    # what the reviewer wants makes the first draft pass and the loop never runs.
    prompt = f"""Draft an RCA for {cell_id} in three lines (Impact / Likely cause / Recommended action).

KPI SUMMARY: {json.dumps(kpis['rolling_avg'])}
THRESHOLDS CROSSED: {json.dumps(kpis['thresholds_crossed'])}
ALARMS: {json.dumps(get_active_alarms('SITE-031'))}
TOPOLOGY: {json.dumps(lookup_topology(cell_id))}
{f"""REVISE. A reviewer rejected your previous draft: {feedback}
In "Likely cause", name the cheaper layers you ruled out and why, before you name the cause.""" if feedback else ''}"""
    return ask(prompt, mock=DRAFTS[min(attempt, len(DRAFTS) - 1)])


def critique(rca: str, attempt: int) -> dict:
    """The critic runs in a FRESH context and holds the checklist. Both matter:
    fresh context means it hasn't anchored on the drafter's reasoning, and the
    checklist means it's checking a fact rather than offering an opinion."""
    layers = "\n".join(f"{i}. {name} — {hint}" for i, (name, hint) in enumerate(DIAGNOSTIC_LAYERS, 1))
    prompt = f"""You are reviewing an RCA against a fixed diagnostic order. Cheapest,
most likely causes must be ruled out BEFORE a more expensive one is blamed.

DIAGNOSTIC ORDER (cheapest first):
{layers}

RCA UNDER REVIEW:
{rca}

Decide which layer the RCA blames. Then list ONLY the layers CHEAPER than that one
which it neither ruled out nor mentioned. Layers more expensive than the cause do
not need discussing — an RCA that blames layer 1 owes you nothing about layer 4.
If no cheaper layer was skipped, it passes.

Respond ONLY as JSON: {{"passed": bool, "missing": [layer names skipped], "note": "one sentence"}}"""
    raw = ask(prompt, mock=json.dumps(CRITIQUES[min(attempt, len(CRITIQUES) - 1)]))
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def run(cell_id: str = "CELL-031A") -> None:
    banner("PATTERN 4 — EVALUATOR-OPTIMIZER",
           "draft -> critique against the 4-layer order -> revise, bounded at 2 rounds")

    feedback, best = "", None
    for attempt in range(MAX_REVISIONS + 1):
        label = "Draft" if attempt == 0 else f"Revision {attempt}"
        print(f"\n{CYAN}{BOLD}[{label}]{RESET}" +
              (f"  {YELLOW}(seeded — a live model rarely writes a draft this bad){RESET}"
               if attempt == 0 else ""))
        # Attempt 0 is the seeded weak draft; revisions are the real thing.
        rca = DRAFTS[0] if attempt == 0 else draft_rca(cell_id, attempt, feedback)
        print("    " + rca.replace("\n", "\n    "))

        verdict = critique(rca, attempt)
        best = rca
        if verdict["passed"]:
            print(f"\n{GREEN}    CRITIC: PASS — {verdict['note']}{RESET}")
            print(f"\n{GREEN}Accepted after {attempt} revision(s).{RESET}")
            break

        skipped = ", ".join(verdict["missing"])
        print(f"\n{RED}    CRITIC: REJECT — skipped {skipped}{RESET}")
        print(f"    {verdict['note']}")
        feedback = f"You skipped {skipped}. {verdict['note']}"
    else:
        print(f"\n{YELLOW}Revision budget exhausted after {MAX_REVISIONS} rounds — "
              f"accepting the best draft and flagging for human review.{RESET}")

    print(f"\n{BOLD}Why the bound matters:{RESET} unbounded critique loops oscillate. The drafter "
          "removes a caveat, the critic asks for it back, and you pay for both forever — the same "
          "failure as the unconstrained ReAct loop in Module 5. MAX_REVISIONS is the circuit breaker.")
    print(f"{BOLD}Why this critic works:{RESET} it holds a checklist the drafter never saw. "
          "Delete the checklist and the critique does not go soft — it goes GENERIC. Measured "
          "on this same draft, the checklist-less critic still rejected it, but for "
          "a missing timeline, missing preventive measures and an 'unconfirmed' cause. Plausible, "
          "professional, and not the diagnostic error. It would have sent the drafter off to add "
          "a timeline while it still blamed the AMF.")


if __name__ == "__main__":
    run()
