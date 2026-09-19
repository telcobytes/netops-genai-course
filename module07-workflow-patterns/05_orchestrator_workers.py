"""
PATTERN 5 — ORCHESTRATOR-WORKERS  (the NetOps Triage Triad)

A supervisor plans and delegates; specialist workers do the domain work with
only the tools their domain needs; the supervisor synthesizes.

    SUPERVISOR (NOC lead)      no tools of its own — it plans and decides
      |-- RAN specialist       get_cell_kpis, lookup_topology
      |-- TRANSPORT specialist get_active_alarms, backhaul views
      `-- synthesis            reconciles what they report

Why bother, when one ReAct agent could call all four tools?

  1. Tool scoping. Each worker sees a handful of tools, not a menu of twenty.
     Fewer wrong choices, shorter prompts, cheaper calls.
  2. Parallelism. Independent workers run at once (pattern 3).
  3. And the real reason: DISAGREEMENT BECOMES VISIBLE.

That third one is the whole justification. A single agent that weighs RF and
transport evidence inside one context silently picks a winner and you never see
the other hypothesis. Two workers reporting separately force the conflict into
the open, where the supervisor has to resolve it explicitly — and where YOU can
read which evidence it preferred and why.

That is exactly the CELL-031A question this course opened with: is the cell at
fault, or is something upstream of it?

Run:  python 05_orchestrator_workers.py --mock     # canned answers: the wiring, free, same every time
      python 05_orchestrator_workers.py            # the same wiring with a live model in it

      Without GEMINI_API_KEY you get --mock either way, and the banner says so.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from _common import ask, banner, step, CYAN, YELLOW, GREEN, RED, BOLD, RESET

sys.path.append("../data")
from mock_tools import get_active_alarms, get_cell_kpis, lookup_topology  # noqa: E402

SITE = "SITE-031"


# ---------------------------- SUPERVISOR: plan ----------------------------

def deduplicate(alarms: list[dict]) -> list[dict]:
    """An alarm storm is usually one incident wearing six hats. Collapse by
    (site, cell) and keep the highest severity — this is deterministic work, so
    no model is involved. Don't pay a model to do a groupby."""
    rank = {"MINOR": 1, "MAJOR": 2, "CRITICAL": 3}
    incidents: dict[tuple, dict] = {}
    for a in alarms:
        key = (a["site_id"], a.get("cell_id") or "")
        if key not in incidents or rank[a["severity"]] > rank[incidents[key]["severity"]]:
            incidents[key] = {**a, "contributing": []}
    for a in alarms:
        key = (a["site_id"], a.get("cell_id") or "")
        if incidents[key]["alarm_id"] != a["alarm_id"]:
            incidents[key]["contributing"].append(a["alarm_id"])
    return list(incidents.values())


# ---------------------------- WORKERS ----------------------------

def ran_specialist(incident: dict) -> dict:
    """Radio-access desk. Tools: get_cell_kpis, lookup_topology."""
    cell = incident.get("cell_id") or "CELL-031A"
    kpis = get_cell_kpis(cell)
    topo = lookup_topology(cell) or {}
    users = kpis["latest"].get("active_users")
    planned = topo.get("planned_capacity_users")
    neighbours = {n: bool(get_cell_kpis(n).get("thresholds_crossed")) for n in topo.get("neighbors", [])}

    finding = ask(
        f"""You are a RAN specialist. Report your finding in ONE sentence, and state
your confidence as high/medium/low.
KPIs: {json.dumps(kpis['rolling_avg'])}
Thresholds crossed: {json.dumps(kpis['thresholds_crossed'])}
Users {users} vs planned capacity {planned}. Neighbour degraded? {json.dumps(neighbours)}""",
        mock=(f"Cell is saturating under its own load: {users:.0f} active users against a planned "
              f"capacity of {planned}, with PRB at 96.3% and all three thresholds crossed; "
              "neighbours are healthy so this is not overflow. Confidence: high."))
    # Read this line carefully, because it is the one students misattribute. The
    # model wrote `finding`. The CONFIDENCE is ours — a constant — so the two desks
    # disagree on every run and the synthesis step always has something to reconcile.
    # In production this comes from the desk's own evidence (how many thresholds, how
    # sustained, how recent), and getting that right is harder than the orchestration
    # around it. Flip it to "low" and watch the supervisor's reasoning change.
    return {"desk": "RAN", "finding": finding, "confidence": "high",
            "evidence": f"{users:.0f}/{planned} users, PRB 96.3%, neighbours healthy"}


def transport_specialist(incident: dict) -> dict:
    """Transport/backhaul desk. Tools: get_active_alarms and transport views."""
    alarms = get_active_alarms(incident["site_id"])
    transport = [a for a in alarms if any(
        w in a["alarm_type"].lower() or w in a["description"].lower()
        for w in ("backhaul", "transmission", "latency", "jitter"))]

    finding = ask(
        f"""You are a transport specialist. Report your finding in ONE sentence and state
confidence as high/medium/low. Note whether any signal is informational or self-cleared.
Transport-related alarms: {json.dumps(transport)}""",
        mock=("Backhaul latency was flagged above baseline during the window, but the alarm is "
              "MINOR and marked informational/auto-cleared, so there is no sustained transport "
              "fault. Confidence: low."))
    return {"desk": "TRANSPORT", "finding": finding, "confidence": "low",
            "evidence": f"{len(transport)} transport alarm(s), all MINOR/auto-cleared"}


WORKERS = [ran_specialist, transport_specialist]


# ---------------------------- SUPERVISOR: synthesize ----------------------------

def synthesize(incident: dict, reports: list[dict]) -> str:
    """The step that earns the pattern. Two desks have reported different
    stories; the supervisor has to say which evidence it trusted and why.

    Note it does NOT take a majority vote. Counting votes is the wrong way to
    reconcile evidence of different quality — one high-confidence finding backed
    by sustained threshold crossings beats one low-confidence finding backed by
    an auto-cleared informational alarm.
    """
    joined = "\n".join(
        f"- {r['desk']} (confidence {r['confidence']}): {r['finding']}\n  evidence: {r['evidence']}"
        for r in reports)
    return ask(
        f"""You are the NOC lead. Two specialist desks disagree about the cause.
Do NOT take a majority vote — weigh the QUALITY of the evidence, and say explicitly
which report you relied on and which you set aside.

INCIDENT: {json.dumps({k: incident[k] for k in ('alarm_id', 'site_id', 'cell_id', 'alarm_type', 'severity')})}
REPORTS:
{joined}

Answer in three lines: Impact / Likely cause / Recommended action.""",
        mock=("Impact: Subscribers on CELL-031A see degraded throughput and elevated setup failures.\n"
              "Likely cause: Local capacity exhaustion — I relied on the RAN desk (high confidence, "
              "sustained threshold crossings, healthy neighbours) and set aside the transport finding, "
              "whose only signal was a MINOR auto-cleared latency warning that did not persist.\n"
              "Recommended action: Apply temporary handover bias to CELL-014A/022A and raise a MAJOR "
              "capacity ticket for RF planning — no transport escalation."))


def run() -> None:
    banner("PATTERN 5 — ORCHESTRATOR-WORKERS (the NetOps Triage Triad)",
           "supervisor plans and delegates; specialists report; supervisor reconciles")

    step(1, "Supervisor: ingest and deduplicate the alarm stream")
    alarms = get_active_alarms(SITE)
    incidents = deduplicate(alarms)
    print(f"    {len(alarms)} raw alarms -> {BOLD}{len(incidents)} distinct incident(s){RESET}")
    for inc in incidents:
        print(f"      {inc['alarm_id']} [{inc['severity']}] {inc['alarm_type']}"
              f"{'  (+' + ', '.join(inc['contributing']) + ')' if inc['contributing'] else ''}")

    incident = max(incidents, key=lambda i: {"MINOR": 1, "MAJOR": 2, "CRITICAL": 3}[i["severity"]])

    step(2, "Supervisor: dispatch to specialists", "workers run concurrently, each with its own tools")
    with ThreadPoolExecutor(max_workers=len(WORKERS)) as pool:
        reports = [f.result() for f in [pool.submit(w, incident) for w in WORKERS]]

    colour = {"RAN": CYAN, "TRANSPORT": YELLOW}
    for r in reports:
        print(f"\n    {colour[r['desk']]}{BOLD}{r['desk']} desk{RESET} "
              f"(confidence: {r['confidence']})")
        print(f"      {r['finding']}")

    disagree = len({r["confidence"] for r in reports}) > 1
    print(f"\n    {RED if disagree else GREEN}{BOLD}"
          f"{'DESKS DISAGREE — supervisor must reconcile' if disagree else 'Desks agree'}{RESET}")

    step(3, "Supervisor: synthesize")
    print("    " + synthesize(incident, reports).replace("\n", "\n    "))

    print(f"\n{BOLD}The teaching moment is step 3, not step 2.{RESET} Parallel workers are a "
          "performance trick. Making two desks report separately so their disagreement has to be "
          "resolved in the open — and reading which evidence the supervisor trusted — is the reason "
          "multi-agent is worth the extra complexity.")


if __name__ == "__main__":
    run()
