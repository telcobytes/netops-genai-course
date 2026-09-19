"""
Checkpoint 2 — Build the dispatcher.

Implement route() so all five alarms land on the right desk.
Then run: python check.py
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "module07-workflow-patterns"))

ROUTES = {
    "RAN": "Radio access — PRB, interference, CQI, antenna geometry, capacity",
    "TRANSPORT": "Transport/backhaul — link latency, jitter, packet delay variation, flaps",
    "CORE": "Core/signalling — RRC/NAS rejects, Diameter, GTP, attach failures",
    "DROP": "Nobody — MINOR and informational, within tolerance, or self-cleared",
}


def route(alarm: dict) -> str:
    """Return one of: RAN, TRANSPORT, CORE, DROP.

    TODO: implement this.

    Hints:
      - Look at alarm['alarm_type'], alarm['description'], alarm['severity'].
      - Check the DROP condition FIRST. A self-cleared informational alarm is
        noise whatever domain its words belong to — and 'TEMPERATURE_WARNING'
        contains no domain keyword at all, which is a trap worth noticing.
      - Deterministic rules are a legitimate answer. So is one ask() call.
        See ../../module07-workflow-patterns/02_routing.py for both.
    """
    raise NotImplementedError("Implement route() — see README.md")


def load_alarms() -> list:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alarms_sample.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    for alarm in load_alarms():
        try:
            print(f"{alarm['alarm_id']} [{alarm['severity']:8}] -> {route(alarm)}")
        except NotImplementedError:
            # The exercise itself, not a broken lab. Say so plainly rather than
            # dumping a stack trace at somebody on their first checkpoint.
            print("\n  route() is not implemented yet — that is the exercise.")
            print("  Open starter.py, implement route(), then run: python check.py\n")
            break
