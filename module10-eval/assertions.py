"""
assertions.py — Module 10: TIER 1 evaluation, the cheap checks that run first

An assertion is a deterministic, machine-checkable fact about what the agent DID:
which tools it called, in what order, what severity it asked for, which documents
it retrieved. It runs in microseconds, costs nothing, and is never wrong.

The rule this file exists to teach:

    If a property can be expressed as an assertion, DO NOT use an LLM to check it.
    An LLM judge is slower, costs money, and is occasionally wrong about something
    a two-line comparison gets right every time.

Tier 2 (LLM-as-a-judge, in run_eval.py) is for what's left over: genuinely
semantic qualities like "does the recommended action follow from the stated cause".

Inputs:
    case   -- one case from data/eval_golden_set.json
    answer -- the agent's final RCA text
    trace  -- list of {"tool": str, "args": dict} in call order, from tracing.py
"""

from __future__ import annotations

SEVERITY_RANK = {"MINOR": 1, "MAJOR": 2, "CRITICAL": 3}


def _tool_names(trace: list[dict]) -> list[str]:
    return [step.get("tool", "") for step in trace]


def check_assertions(case: dict, answer: str, trace: list[dict]) -> list[dict]:
    """Return one result dict per assertion: {check, passed, detail}."""
    spec = case.get("assertions") or {}
    called = _tool_names(trace)
    lowered = (answer or "").lower()
    results: list[dict] = []

    def record(check: str, passed: bool, detail: str, skipped: bool = False) -> None:
        results.append({"check": check, "passed": passed, "detail": detail,
                        "skipped": skipped})

    for tool in spec.get("required_tools", []):
        record(f"calls {tool}", tool in called,
               "called" if tool in called else f"never called (saw: {called or 'no tools'})")

    for tool in spec.get("forbidden_tools", []):
        record(f"does not call {tool}", tool not in called,
               "not called" if tool not in called else "called, but must not be")

    for earlier, later in spec.get("tool_order", []):
        if later not in called:
            # Neither complied nor violated. Scoring this as a pass flatters an
            # agent that did nothing — which is exactly how this assertion came to
            # be green for a run with an empty trace.
            record(f"{earlier} before {later}", False,
                   f"{later} never called — nothing to order, assertion not demonstrated",
                   skipped=True)
        elif earlier not in called:
            record(f"{earlier} before {later}", False, f"{later} called without {earlier} first")
        else:
            ok = called.index(earlier) < called.index(later)
            record(f"{earlier} before {later}", ok,
                   "correct order" if ok else f"{later} came first — agent acted before checking")

    ceiling = spec.get("max_ticket_severity")
    if ceiling == "derive":
        ceiling = _derived_ceiling(case)
    if ceiling:
        # Only tickets that were actually OPENED. A proposal the guardrail refused
        # is the control working, not the agent misbehaving — it is reported below
        # rather than scored here.
        opened = [s for s in trace if s.get("tool") == "create_ticket"
                  and not str(s.get("outcome", "")).startswith(("refused", "declined"))]
        blocked = [s for s in trace if s.get("tool") == "create_ticket"
                   and str(s.get("outcome", "")).startswith(("refused", "declined"))]
        asked = [str(s.get("args", {}).get("severity", "MINOR")).upper() for s in opened]
        if not asked and blocked:
            # Nothing above the ceiling was opened because code stopped it. That is
            # the control working — a pass, and worth saying out loud.
            record(f"ticket severity <= {ceiling}", True,
                   f"no ticket opened — {len(blocked)} proposal(s) refused by a guardrail")
        elif not asked:
            record(f"ticket severity <= {ceiling}", False,
                   "no ticket opened — ceiling not demonstrated", skipped=True)
        else:
            worst = max(SEVERITY_RANK.get(s, 0) for s in asked)
            ok = worst <= SEVERITY_RANK[ceiling]
            record(f"ticket severity <= {ceiling}", ok,
                   ("requested " + ", ".join(asked)) + ("" if ok else f" — exceeds {ceiling}"))

    if spec.get("neighbours_checked_before_ticket"):
        neighbours = _neighbour_ids(case)
        idx = called.index("create_ticket") if "create_ticket" in called else None
        if idx is None:
            record("checks a neighbour before ticketing", False,
                   "no ticket proposed — nothing to check against", skipped=True)
        else:
            touched = sorted({
                str(v) for step in trace[:idx]
                for v in (step.get("args") or {}).values()
                if str(v) in neighbours})
            record("checks a neighbour before ticketing", bool(touched),
                   f"inspected {', '.join(touched)}" if touched else
                   f"blamed the cell without reading a single neighbour "
                   f"({', '.join(sorted(neighbours))})")

    retrieved = []
    for step in trace:
        retrieved.extend(step.get("retrieved", []) or [])
    retrieved_blob = " ".join(retrieved).lower()

    # RANK, not membership. `must_retrieve` asks whether a document appears
    # anywhere in the top k, which is a weaker claim than it reads as: measured
    # EVAL-03 passed it for months while dense retrieval ranked a
    # VoLTE postmortem FIRST for a congestion question. An assertion that a wrong
    # top hit can satisfy is not testing the thing it names.
    for doc in spec.get("must_rank_first", []):
        top = retrieved[0] if retrieved else ""
        ok = doc.lower() in top.lower()
        record(f"ranks {doc} first", ok,
               "top hit" if ok else f"top hit was {top or '(nothing retrieved)'}")

    for doc in spec.get("must_retrieve", []):
        ok = doc.lower() in retrieved_blob
        record(f"retrieves {doc}", ok, "retrieved" if ok else "not in retrieved set")

    for doc in spec.get("must_not_retrieve", []):
        ok = doc.lower() not in retrieved_blob
        record(f"does not retrieve {doc}", ok, "correctly ranked below" if ok else "retrieved — wrong document won")

    for phrase in spec.get("answer_must_mention", []):
        ok = phrase.lower() in lowered
        record(f"answer mentions '{phrase}'", ok, "present" if ok else "missing")

    for phrase in spec.get("answer_must_not_mention", []):
        ok = phrase.lower() not in lowered
        record(f"answer avoids '{phrase}'", ok, "absent" if ok else "present — over-escalation")

    return results


def _topo(node):
    """Topology lookup for the GRADER, not for the agent.

    mock_tools.lookup_topology now raises on an unknown node -- deliberately, so
    an agent that fat-fingers an id gets told rather than being handed a silent
    None it reads as "no neighbours". But grading walks whatever the agent
    actually passed, and a bad agent call must produce a FAILED ASSERTION, never
    a crashed harness. Strict tool, defensive grader.
    """
    if not node:
        return {}
    # imported here, like the other two call sites in this file: assertions.py
    # is importable without data/ on sys.path so the tier-1 lesson can be read
    # on its own.
    from mock_tools import lookup_topology  # noqa: E402
    try:
        return lookup_topology(node) or {}
    except ValueError:
        return {}


def _neighbour_ids(case: dict) -> set:
    """The cells this case's cell hands traffic to, plus their sites.

    `lookup_topology before create_ticket` was a PROXY for "checked the
    neighbours", and it turned out to be a bad one: an agent asked about SITE-031
    looks up SITE-031's topology as a matter of course, satisfying the assertion
    without ever reading a neighbour. Measured, the naive prompt
    scored 100% on the proxy and touched zero neighbours. Assert the rule itself.
    """
    import os
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
    from mock_tools import lookup_topology  # noqa: E402

    topo = _topo(case.get("cell_id"))
    ids = set()
    for cell in topo.get("neighbors", []):
        ids.add(cell)
        nb = _topo(cell)
        if nb.get("site_id"):
            ids.add(nb["site_id"])
    return ids


def _derived_ceiling(case: dict) -> str:
    """The ceiling is read off the alarm feed for the site this case is about —
    not hardcoded per case. A number nobody has to defend is a number nobody
    checked: EVAL-01 carried `MAJOR` for months and it had never once executed.
    """
    import os
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
    from guardrails import highest_active_alarm_severity  # noqa: E402
    from mock_tools import lookup_topology  # noqa: E402

    node = case.get("cell_id") or ""
    site = node if node.startswith("SITE-") else _topo(node).get("site_id", "")
    return highest_active_alarm_severity(site) if site else "CRITICAL"


def summarize(results: list[dict]) -> tuple[int, int]:
    """Skipped assertions count as neither pass nor total — they are reported, not
    scored. A check that could not run is not a check that passed."""
    scored = [r for r in results if not r.get("skipped")]
    return sum(1 for r in scored if r["passed"]), len(scored)


def format_results(results: list[dict], indent: str = "    ") -> str:
    if not results:
        return f"{indent}(no assertions defined for this case)"
    def label(r: dict) -> str:
        if r.get("skipped"):
            return "SKIP"
        return "PASS" if r["passed"] else "FAIL"

    return "\n".join(
        f"{indent}{label(r):4}  {r['check']:44} {r['detail']}"
        for r in results
    )
