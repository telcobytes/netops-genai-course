from __future__ import annotations
"""
mock_tools.py — Mock NOC data-access tools for "NetOps Co." course labs.

These functions simulate the OSS/BSS-style APIs a real agent would call, backed by
the flat files in this folder instead of a live network. Use them as the "tools" an
agent calls in Modules 5 (ReAct from scratch), 6 (tool calling), 7 (packaging into a
Skill), 8 (exposing via an MCP server), 9 (tracing/eval), and 10 (capstone).

No external dependencies beyond the Python standard library, so this drops into any
lab notebook or script without extra setup.
"""

import csv
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_csv(filename: str) -> list[dict]:
    path = os.path.join(_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_json(filename: str) -> dict:
    path = os.path.join(_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Operational thresholds used by the course. Kept here, in the TOOL layer, rather
# than in a prompt: the tool computes whether a threshold was crossed; the agent
# reasons about what that means. ("Tools compute; agents reason.")
THRESHOLDS = {
    "prb_utilization_pct": (">", 75.0),
    "rrc_drop_rate_pct": (">", 5.0),
    "rrc_setup_success_rate_pct": ("<", 95.0),
}

_NUMERIC_FIELDS = [
    "prb_utilization_pct",
    "rrc_setup_success_rate_pct",
    "rrc_drop_rate_pct",
    "avg_throughput_mbps",
    "active_users",
]


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_cell_kpis(cell_id: str, window_minutes: int = 60) -> dict:
    """Return a COMPUTED KPI summary for `cell_id` over the last `window_minutes`.

    This is deliberately not a raw dump of counter rows. A real performance-
    management API returns far more data than you want to put in a prompt, and
    LLMs are unreliable at arithmetic over long tables. So the tool does the
    maths -- rolling averages, deltas, threshold crossings -- and hands the agent
    a small, already-correct summary to reason about.

    That is the principle this course keeps coming back to:
        Tools compute. Agents reason.

    Note on the window: the sample data is a fixed historical snapshot, so the
    window is anchored to the LATEST timestamp present for this cell rather than
    to wall-clock "now". Against a live PM API you would anchor to now instead.

    Returns a dict with:
        cell_id, window_minutes, window_start, window_end, sample_count
        latest        -- the most recent reading, values coerced to numbers
        rolling_avg   -- mean of each numeric metric across the window
        delta         -- latest minus oldest, per metric (direction of travel)
        thresholds_crossed -- list of {metric, value, threshold, comparison}
        readings      -- the underlying rows, so students can still see raw data
    """
    rows = [r for r in _load_csv("kpis.csv") if r["cell_id"] == cell_id]
    if not rows:
        return {}

    rows.sort(key=lambda r: r["timestamp"])
    window_end = _parse_ts(rows[-1]["timestamp"])
    window_start = window_end - timedelta(minutes=window_minutes)
    windowed = [r for r in rows if _parse_ts(r["timestamp"]) >= window_start]
    if not windowed:
        windowed = rows[-1:]

    def _num(row: dict) -> dict:
        out = {}
        for field in _NUMERIC_FIELDS:
            try:
                out[field] = float(row[field])
            except (KeyError, TypeError, ValueError):
                continue
        return out

    numeric = [_num(r) for r in windowed]
    latest, oldest = numeric[-1], numeric[0]

    rolling_avg = {
        field: round(sum(n[field] for n in numeric if field in n) / len(numeric), 2)
        for field in _NUMERIC_FIELDS
        if any(field in n for n in numeric)
    }
    delta = {
        field: round(latest[field] - oldest[field], 2)
        for field in _NUMERIC_FIELDS
        if field in latest and field in oldest
    }

    crossed = []
    for field, (comparison, limit) in THRESHOLDS.items():
        value = latest.get(field)
        if value is None:
            continue
        if (comparison == ">" and value > limit) or (comparison == "<" and value < limit):
            crossed.append(
                {"metric": field, "value": value, "threshold": limit, "comparison": comparison}
            )

    return {
        "cell_id": cell_id,
        "window_minutes": window_minutes,
        "window_start": windowed[0]["timestamp"],
        "window_end": windowed[-1]["timestamp"],
        "sample_count": len(windowed),
        "latest": {**latest, "timestamp": windowed[-1]["timestamp"]},
        "rolling_avg": rolling_avg,
        "delta": delta,
        "thresholds_crossed": crossed,
        "readings": windowed,
    }


def get_active_alarms(site_id: Optional[str] = None) -> list[dict]:
    """Return active alarms, optionally filtered to a single site_id. Mirrors a
    fault-management API's "current alarms" endpoint.
    """
    rows = _load_csv("alarms.csv")
    if site_id:
        # An unknown site used to return [] — indistinguishable from "this site is
        # healthy". That is how a caller passing the wrong identifier got a
        # confident all-clear instead of an error. Say so instead.
        known = {r["site_id"] for r in rows} | {s["site_id"] for s in _load_json("topology.json")["sites"]}
        if site_id not in known:
            raise ValueError(
                f"unknown site_id {site_id!r} — known sites: {', '.join(sorted(known))}")
        rows = [r for r in rows if r["site_id"] == site_id]
    return rows


def lookup_topology(node_id: str) -> Optional[dict]:
    """Return topology info for a site_id or cell_id: neighbors, vendor, planned
    capacity, etc. Mirrors an inventory/topology API.
    """
    topo = _load_json("topology.json")
    for site in topo["sites"]:
        if site["site_id"] == node_id:
            return site
        for cell in site["cells"]:
            if cell["cell_id"] == node_id:
                return {**cell, "site_id": site["site_id"], "vendor": site["vendor"], "region": site["region"]}
    return None


VALID_SEVERITIES = ("MINOR", "MAJOR", "CRITICAL")


# Every ticket used to come back as TCK-MOCK-0001. The capstone opened three in a
# row and printed the same id three times, which made three tickets look like one
# -- the opposite of the mistake it was actually making.
_ticket_counter = 0


def create_ticket(
    summary: str,
    site_id: str = "",
    category: str = "Uncategorized",
    severity: str = "MINOR",
) -> dict:
    """Simulate opening a trouble ticket. In the real world this would POST to a
    ticketing system; here it just returns a mock confirmation so students can see
    the "action" step of an agent without needing a live ticketing API.

    `severity` must be one of MINOR / MAJOR / CRITICAL -- the same vocabulary the
    alarm feed uses. It is validated HERE, in Python, rather than trusted from the
    model: an agent that panics during an alarm storm and asks for CRITICAL on a
    within-tolerance signal is a real failure mode, and Module 10's EVAL-02 case
    asserts against exactly that.

    In the course labs, treat this as the one tool that should ALWAYS require a
    human-in-the-loop confirmation before it's actually called (Module 10's
    guardrails discussion) -- it's the one function here with a real side effect.
    """
    severity = (severity or "MINOR").upper()
    if severity not in VALID_SEVERITIES:
        raise ValueError(
            f"severity must be one of {', '.join(VALID_SEVERITIES)} -- got {severity!r}"
        )

    global _ticket_counter
    _ticket_counter += 1

    return {
        "ticket_id": f"TCK-MOCK-{_ticket_counter:04d}",
        "status": "Open",
        "summary": summary,
        "site_id": site_id,
        "category": category,
        "severity": severity,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "note": "MOCK ticket — not actually written anywhere. Replace with a real API call in production.",
    }


# ---------------------------------------------------------------------------
# Beyond the four: state-mutating tools used only in the guardrails lesson.
#
# The four tools above are what the agent uses to DIAGNOSE. These two CHANGE the
# network, and they exist here so Module 10 has something real to bound. Never
# wire them into an autonomous loop — see guardrails.py.
# ---------------------------------------------------------------------------

def set_tx_power(cell_id: str, tx_power_dbm: float) -> dict:
    """Simulate setting a cell's transmit power. MOCK — changes nothing.

    Bounds are NOT enforced here on purpose: guardrails.SetTxPowerArgs enforces
    10-46 dBm before the call is ever dispatched. That separation is the lesson —
    validation belongs in a schema the model cannot talk its way around, not in
    a polite sentence in the prompt.
    """
    return {
        "cell_id": cell_id,
        "tx_power_dbm": tx_power_dbm,
        "status": "APPLIED (mock)",
        "note": "MOCK — no radio was harmed. Replace with a real CM/provisioning API call.",
    }


def adjust_antenna_tilt(cell_id: str, tilt_degrees: float) -> dict:
    """Simulate an electrical downtilt change. MOCK — changes nothing."""
    return {
        "cell_id": cell_id,
        "tilt_degrees": tilt_degrees,
        "status": "APPLIED (mock)",
        "note": "MOCK — replace with a real CM/provisioning API call.",
    }


if __name__ == "__main__":
    # Quick smoke test / demo of all four tools against the sample data.
    # Runs on the standard library alone — no API key, no pip install.
    print("Computed KPI summary for CELL-031A (last 60 min):")
    summary = get_cell_kpis("CELL-031A")
    for key in ("window_start", "window_end", "sample_count", "rolling_avg", "delta"):
        print(f"  {key}: {summary[key]}")
    print("  thresholds_crossed:")
    for item in summary["thresholds_crossed"]:
        print(f"    {item['metric']} = {item['value']} ({item['comparison']} {item['threshold']})")

    print("\nActive alarms for SITE-031:")
    for row in get_active_alarms("SITE-031"):
        print(" ", row["alarm_id"], row["severity"], row["alarm_type"])

    print("\nTopology for CELL-031A:")
    print(" ", lookup_topology("CELL-031A"))

    print("\nSample ticket creation:")
    print(" ", create_ticket("Congestion at CELL-031A", site_id="SITE-031",
                             category="Congestion", severity="MAJOR"))
