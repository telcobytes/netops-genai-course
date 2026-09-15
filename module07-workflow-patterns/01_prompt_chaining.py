"""
PATTERN 1 — PROMPT CHAINING

One task, broken into a fixed sequence of smaller steps. Each step's output is
the next step's input, and you validate BETWEEN steps rather than hoping one
enormous prompt gets everything right at once.

Telecom shape: raw alarm -> classify fault domain -> draft RCA -> format ticket.

When to reach for it:
  The steps are always the same and always in the same order. If the order
  depends on what you find, you want ReAct (Module 5) or Routing (pattern 2).

Why it beats one big prompt:
  A single "read this alarm and produce a ticket" prompt fails opaquely — you
  get a bad ticket and no idea which part of the reasoning went wrong. Chained,
  you can see exactly which link broke, and you can put a cheap deterministic
  check between any two links.

Run:  python 01_prompt_chaining.py [--mock]
"""

import json
import sys

from _common import ask, banner, step, GREEN, RED, RESET

sys.path.append("../data")
from mock_tools import get_active_alarms, get_cell_kpis  # noqa: E402
from guardrails import validate_tool_args, GuardrailError  # noqa: E402

FAULT_DOMAINS = ["RADIO_ACCESS_INTERFERENCE", "CAPACITY_PRB_EXHAUSTION",
                 "TRANSPORT_BACKHAUL_JITTER", "CORE_SIGNALING_REJECT"]


def link_1_classify(alarm: dict, kpis: dict) -> str:
    """Link 1: put the alarm in exactly one 3GPP fault bucket."""
    prompt = f"""Classify this alarm into EXACTLY ONE of these fault domains:
{', '.join(FAULT_DOMAINS)}

ALARM: {json.dumps(alarm)}
KPI SUMMARY: {json.dumps({k: kpis[k] for k in ('rolling_avg', 'delta', 'thresholds_crossed')})}

Reply with the domain name only, nothing else."""
    return ask(prompt, mock="CAPACITY_PRB_EXHAUSTION")


def link_2_draft_rca(alarm: dict, kpis: dict, domain: str) -> str:
    """Link 2: write the RCA, now that the domain is fixed."""
    prompt = f"""You are an L3 NOC engineer. The fault domain is already
established as {domain} — do not re-litigate it.

ALARM: {json.dumps(alarm)}
KPI SUMMARY: {json.dumps(kpis['rolling_avg'])}
THRESHOLDS CROSSED: {json.dumps(kpis['thresholds_crossed'])}

Write exactly three lines:
Impact: ...
Likely cause: ...
Recommended action: ..."""
    return ask(prompt, mock=(
        "Impact: Subscribers on CELL-031A see degraded throughput and elevated call setup failures.\n"
        "Likely cause: Active users (214) exceed the cell's planned capacity of 150, saturating PRB.\n"
        "Recommended action: Verify neighbour health, then apply a temporary handover bias."))


def link_3_format_ticket(rca: str, domain: str) -> dict:
    """Link 3: turn prose into the structured arguments a tool can take."""
    prompt = f"""Convert this RCA into ticket arguments.
Respond ONLY as JSON with keys: summary, site_id, category, severity.
severity must be one of MINOR, MAJOR, CRITICAL and must match the evidence.

RCA:
{rca}
DOMAIN: {domain}"""
    raw = ask(prompt, mock=json.dumps({
        "summary": "CELL-031A capacity exhaustion: 214 users against planned 150",
        "site_id": "SITE-031", "category": domain, "severity": "MAJOR"}))
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def run(cell_id: str = "CELL-031A") -> None:
    banner("PATTERN 1 — PROMPT CHAINING",
           "alarm -> classify -> draft RCA -> format ticket, validated between links")

    alarms = [a for a in get_active_alarms("SITE-031") if a["severity"] in ("MAJOR", "CRITICAL")]
    alarm = alarms[0]
    kpis = get_cell_kpis(cell_id)

    step(1, "Classify fault domain")
    domain = link_1_classify(alarm, kpis)
    print(f"    -> {domain}")

    # The validation BETWEEN links is the point of the pattern. A cheap
    # membership test here stops a hallucinated domain poisoning links 2 and 3.
    if domain not in FAULT_DOMAINS:
        print(f"{RED}    CHAIN BROKEN: '{domain}' is not a known fault domain. Stopping.{RESET}")
        return
    print(f"{GREEN}    validated: known 3GPP domain{RESET}")

    step(2, "Draft the RCA")
    rca = link_2_draft_rca(alarm, kpis, domain)
    print("    " + rca.replace("\n", "\n    "))

    step(3, "Format ticket arguments")
    args = link_3_format_ticket(rca, domain)
    try:
        clean = validate_tool_args("create_ticket", args)
        print(f"{GREEN}    validated: {json.dumps(clean)}{RESET}")
    except GuardrailError as err:
        print(f"{RED}    CHAIN BROKEN at the last link: {err}{RESET}")
        return

    print(f"\n{GREEN}Chain complete.{RESET} Each link was checked before the next one ran — "
          "so a failure names its own step instead of producing a mysteriously bad ticket.")


if __name__ == "__main__":
    run()
