"""
PATTERN 2 — ROUTING

A cheap classifier looks at each incoming item and sends it down exactly one
specialist path. Nothing is analysed by a generalist that a specialist would
handle better, and noise is dropped before it costs anything.

Telecom shape: this IS a NOC escalation tree. You already work this way — an
alarm arrives, someone decides "that's RAN" or "that's transport" or "that's
core", and it goes to the right desk. All we're doing is writing it down.

When to reach for it:
  Incoming work is heterogeneous and your specialists need different tools,
  different prompts, or different escalation rules.

The part people skip:
  A DROP route. Most alarm feeds are mostly noise. A router without a way to
  say "this needs nobody" just distributes the noise more efficiently.

Run:  python 02_routing.py [--mock]
"""

import json
import sys

from _common import ask, banner, GREEN, YELLOW, CYAN, RED, BOLD, RESET

sys.path.append("../data")
from mock_tools import get_active_alarms, get_cell_kpis, lookup_topology  # noqa: E402

ROUTES = {
    "RAN": "Radio-access specialist — PRB, CQI, interference, antenna geometry",
    "TRANSPORT": "Transport/backhaul specialist — link latency, jitter, flaps",
    "CORE": "Core/signalling specialist — RRC/NAS rejects, Diameter, GTP",
    "DROP": "No action — within tolerance, informational, or self-recovered",
}


def route(alarm: dict) -> str:
    """The router. Deliberately ONE cheap call — routing should never cost more
    than the work it's routing to."""
    prompt = f"""You are a NOC triage dispatcher. Route this alarm to exactly one desk.

{chr(10).join(f'{k}: {v}' for k, v in ROUTES.items())}

Route to DROP if it is MINOR and described as within tolerance, informational,
or self-recovered. Do not escalate noise.

ALARM: {json.dumps(alarm)}

Reply with one word: RAN, TRANSPORT, CORE, or DROP."""
    mock = _heuristic_route(alarm)
    answer = ask(prompt, mock=mock).strip().upper()
    return answer if answer in ROUTES else "DROP"


def _heuristic_route(alarm: dict) -> str:
    """Offline stand-in for the router — also a useful reference for what the
    model should be doing, and a reminder that some routing doesn't need an LLM
    at all. If your routes are this predictable, route in Python and save the call."""
    text = f"{alarm['alarm_type']} {alarm['description']}".lower()
    if alarm["severity"] == "MINOR" and any(
        w in text for w in ("within tolerance", "informational", "self-recovered", "auto-cleared")
    ):
        return "DROP"
    if any(w in text for w in ("backhaul", "transmission", "link", "jitter", "latency")):
        return "TRANSPORT"
    if any(w in text for w in ("rrc", "nas", "diameter", "gtp", "reject", "volte")):
        return "CORE"
    return "RAN"


# ---- The specialist desks. Each gets only the tools its domain needs. ----

def ran_desk(alarm: dict) -> str:
    kpis = get_cell_kpis(alarm.get("cell_id") or "CELL-031A")
    topo = lookup_topology(alarm.get("cell_id") or alarm["site_id"]) or {}
    crossed = ", ".join(c["metric"] for c in kpis.get("thresholds_crossed", [])) or "none"
    return (f"RAN: thresholds crossed = {crossed}; "
            f"users {kpis.get('latest', {}).get('active_users')} vs planned "
            f"{topo.get('planned_capacity_users', 'n/a')}; neighbours {topo.get('neighbors', [])}")


def transport_desk(alarm: dict) -> str:
    return (f"TRANSPORT: inspecting backhaul for {alarm['site_id']} — "
            f"'{alarm['description']}'. Check link latency, jitter and flap counters.")


def core_desk(alarm: dict) -> str:
    return (f"CORE: inspecting signalling for {alarm.get('cell_id') or alarm['site_id']} — "
            f"'{alarm['description']}'. Check reject causes and timer expiries.")


DESKS = {"RAN": ran_desk, "TRANSPORT": transport_desk, "CORE": core_desk}
COLOURS = {"RAN": CYAN, "TRANSPORT": YELLOW, "CORE": GREEN, "DROP": RED}


def run() -> None:
    banner("PATTERN 2 — ROUTING",
           "one cheap classifier, four desks, and a DROP route for the noise")

    alarms = get_active_alarms()
    tally = {k: 0 for k in ROUTES}

    for alarm in alarms:
        decision = route(alarm)
        tally[decision] += 1
        colour = COLOURS[decision]
        print(f"\n{colour}{BOLD}{alarm['alarm_id']} [{alarm['severity']:8}] -> {decision}{RESET}")
        print(f"    {alarm['alarm_type']}: {alarm['description'][:70]}")
        if decision == "DROP":
            print(f"    {RED}dropped — no specialist spends a token on this{RESET}")
        else:
            print(f"    {DESKS[decision](alarm)}")

    print(f"\n{BOLD}Routing summary:{RESET} " +
          "  ".join(f"{k}={v}" for k, v in tally.items()))
    print(f"{GREEN}{tally['DROP']} of {len(alarms)} alarms never reached a specialist.{RESET} "
          "During an alarm storm that ratio is what keeps the system usable.")


if __name__ == "__main__":
    run()
