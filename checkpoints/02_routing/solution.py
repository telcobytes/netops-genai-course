"""Checkpoint 2 — one working answer (deterministic). Try it yourself first.

Why deterministic here: five alarm types from a controlled vocabulary. An LLM
router would also pass, and would cost five calls to do what a few lines of
matching do for nothing. Reach for the model when the input vocabulary is
genuinely open — not to look modern.

A GOTCHA WORTH YOUR TIME
------------------------
The obvious first attempt puts "link" in the transport keywords. It routes four
alarms correctly and sends ALM-7105 to the wrong desk, because:

    "UPLINK_INTERFERENCE_HIGH"  contains  "link"

Naive substring matching finds "link" inside "uplink" and confidently files a
radio interference problem with the transport team. Nothing errors. The router
just quietly gets it wrong, and in production you'd find out when transport
replied that their hop is clean.

The fix is word boundaries — match whole tokens, not substrings. This is the
single most common bug in hand-written routers, and it is exactly the kind of
silent failure an LLM router would not have made. That trade-off is the lesson:
deterministic is cheaper and faster, and its failure modes are yours to find.
"""

import re

NOISE_MARKERS = ("informational", "auto-cleared", "self-cleared", "within tolerance", "briefly")
TRANSPORT_WORDS = ("backhaul", "jitter", "packet delay", "transmission", "microwave", "latency")
CORE_WORDS = ("nas", "rrc", "diameter", "gtp", "attach", "reject", "s6a", "signalling", "signaling")
RAN_WORDS = ("prb", "interference", "cqi", "antenna", "tilt", "capacity",
             "congestion", "uplink", "downlink", "noise floor")


def _mentions(text: str, words) -> bool:
    """Whole-token match. `\\b` is what stops 'uplink' registering as 'link'."""
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def route(alarm: dict) -> str:
    text = f"{alarm['alarm_type']} {alarm['description']}".lower().replace("_", " ")

    # DROP first — noise is noise regardless of which domain's words it contains.
    if alarm["severity"] == "MINOR" and any(m in text for m in NOISE_MARKERS):
        return "DROP"
    # RAN before TRANSPORT: "uplink"/"downlink" are radio terms that share a
    # token with transport vocabulary. Order the checks so the specific wins.
    if _mentions(text, RAN_WORDS):
        return "RAN"
    if _mentions(text, TRANSPORT_WORDS):
        return "TRANSPORT"
    if _mentions(text, CORE_WORDS):
        return "CORE"
    return "DROP"
