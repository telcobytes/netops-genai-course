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

    def record(check: str, passed: bool, detail: str) -> None:
        results.append({"check": check, "passed": passed, "detail": detail})

    for tool in spec.get("required_tools", []):
        record(f"calls {tool}", tool in called,
               "called" if tool in called else f"never called (saw: {called or 'no tools'})")

    for tool in spec.get("forbidden_tools", []):
        record(f"does not call {tool}", tool not in called,
               "not called" if tool not in called else "called, but must not be")

    for earlier, later in spec.get("tool_order", []):
        if later not in called:
            record(f"{earlier} before {later}", True, f"{later} never called — ordering vacuously holds")
        elif earlier not in called:
            record(f"{earlier} before {later}", False, f"{later} called without {earlier} first")
        else:
            ok = called.index(earlier) < called.index(later)
            record(f"{earlier} before {later}", ok,
                   "correct order" if ok else f"{later} came first — agent acted before checking")

    ceiling = spec.get("max_ticket_severity")
    if ceiling:
        asked = [
            str(step.get("args", {}).get("severity", "MINOR")).upper()
            for step in trace
            if step.get("tool") == "create_ticket"
        ]
        worst = max((SEVERITY_RANK.get(s, 0) for s in asked), default=0)
        ok = worst <= SEVERITY_RANK[ceiling]
        record(f"ticket severity <= {ceiling}", ok,
               "no ticket proposed" if not asked else
               ("requested " + ", ".join(asked)) + ("" if ok else f" — exceeds {ceiling}"))

    retrieved = []
    for step in trace:
        retrieved.extend(step.get("retrieved", []) or [])
    retrieved_blob = " ".join(retrieved).lower()

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


def summarize(results: list[dict]) -> tuple[int, int]:
    return sum(1 for r in results if r["passed"]), len(results)


def format_results(results: list[dict], indent: str = "    ") -> str:
    if not results:
        return f"{indent}(no assertions defined for this case)"
    return "\n".join(
        f"{indent}{'PASS' if r['passed'] else 'FAIL'}  {r['check']:44} {r['detail']}"
        for r in results
    )
