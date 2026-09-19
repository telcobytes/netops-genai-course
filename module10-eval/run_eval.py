"""
run_eval.py — Module 10 hands-on: tiered golden-set evaluation for telecom agents

Tests the RAG-grounded RCA drafter against eval_golden_set.json in two tiers,
cheapest first:

  TIER 1 — Deterministic assertions (assertions.py). What did the agent DO?
           Which tools, in what order, what severity, which documents. Runs in
           microseconds, costs nothing, never wrong. Defined as DATA in
           eval_golden_set.json, not hardcoded here, so adding a case means
           editing JSON rather than Python.

  TIER 2 — LLM-as-a-judge (1-5 rubric). Only for what tier 1 cannot express:
           does the recommended action actually follow from the stated cause.

The ordering is the lesson. A property you can assert should never be sent to a
model to judge — the model is slower, costs money, and is occasionally wrong
about something a two-line comparison gets right every time.

Run tier 1 only (no API key needed):
    python run_eval.py            # live agents; without a key it says so and uses --mock

Run both tiers:
    python run_eval.py --judge
"""

import copy
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "module04-rag"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "module06-noc-assistant"))
from llm_client import call_llm  # noqa: E402
from rag_pipeline import draft_grounded_rca  # noqa: E402
from assertions import check_assertions, format_results, summarize  # noqa: E402
from tracing import collect, traced  # noqa: E402

GOLDEN_SET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "eval_golden_set.json"
)


def _run_agent(case: dict, trace: list) -> str:
    """Grade the Module 6 agent.

    Its tool dispatcher is wrapped so every call the agent makes lands in the
    trace — including a ticket it PROPOSES and a human then declines, which is
    what the severity assertion is actually about.
    """
    import noc_assistant

    original = noc_assistant._dispatch_tool
    prior = os.environ.get("AUTO_APPROVE")
    # The eval measures the agent's decisions, not the human's. Leaving the gate
    # interactive would stall a non-interactive run; the proposal is recorded
    # either way, so approving does not change any tier-1 verdict.
    os.environ["AUTO_APPROVE"] = "1"

    def _dispatch(name, args):
        entry = {"tool": name, "args": args}
        trace.append(entry)
        result = original(name, args)
        # Record the OUTCOME, so an assertion can tell a ticket that was opened from
        # one a guardrail refused. Without this the two look identical in the trace.
        if isinstance(result, dict) and result.get("status"):
            entry["outcome"] = result["status"]
        return result

    noc_assistant._dispatch_tool = _dispatch
    try:
        return noc_assistant.run_noc_assistant(
            f"{case['scenario']} What is going on, and what should we do?",
            scope=_case_scope(case))
    finally:
        noc_assistant._dispatch_tool = original
        if prior is None:
            os.environ.pop("AUTO_APPROVE", None)
        else:
            os.environ["AUTO_APPROVE"] = prior


def _replay_guardrails(case: dict, trace: list) -> list:
    """Run the REAL guardrails over a recorded trace's ticket proposals.

    Offline, the model is mocked but the code under test must not be. Each
    create_ticket in the trace goes through the same two checks the live agent
    hits in noc_assistant._dispatch_tool — the schema, then the policy — and the
    outcome is stamped onto the entry exactly as a live run would stamp it.

    The practical consequence: comment out the scope rule in data/guardrails.py
    and `python run_eval.py` goes red with no API key. That is the exercise.
    """
    import guardrails

    scope = _case_scope(case)
    for entry in trace:
        if entry.get("tool") != "create_ticket":
            continue
        args = entry.get("args", {})
        try:
            checked = guardrails.validate_tool_args("create_ticket", args)
        except guardrails.GuardrailError as err:
            entry["outcome"] = "refused_by_schema"
            entry["refusal"] = str(err)
            continue
        allowed, reason = guardrails.check_ticket_proposal(checked, scope=scope)
        entry["outcome"] = "Open" if allowed else "refused_by_guardrail"
        if not allowed:
            entry["refusal"] = reason
    return trace


def _case_scope(case: dict):
    """The blast radius for this case: the site the question is about."""
    from mock_tools import lookup_topology
    node = case.get("cell_id") or ""
    if node.startswith("SITE-"):
        return [node]
    site = (lookup_topology(node) or {}).get("site_id")
    return [site] if site else None


def _instrumented_tools():
    """Wrap the tools rag_pipeline calls so their invocations land in the trace.

    The same @traced decorator Module 10 teaches, applied to the functions the
    grader asks questions about. Without this, tier 1 has nothing of this run to
    read — and it used to read tracing.py's leftover demo log instead.
    """
    import rag_pipeline
    for name in ("get_cell_kpis", "get_active_alarms", "lookup_topology"):
        fn = getattr(rag_pipeline, name)
        if not getattr(fn, "__wrapped__", None):
            setattr(rag_pipeline, name, traced(fn))


def load_golden_set():
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        return json.load(f)["cases"]


# Tier 1 assertions now live in data/eval_golden_set.json under each case's
# "assertions" key — see assertions.py for the checker. Nothing to hardcode here.

# Offline tool-call traces, so tier 1 is demonstrable without an API key. In a
# live run these come from tracing.py's JSONL log instead.
#
# These record what the agent PROPOSED, never what the guardrails allowed. The
# outcome of each create_ticket is computed by _replay_guardrails() below, by
# running the real data/guardrails.py over the proposal — so --mock replaces the
# MODEL and nothing else. It used to replace the guardrails too, which is why a
# green offline run said nothing at all about whether the gate worked.
MOCK_TRACES = {
    "EVAL-01": [
        {"tool": "get_cell_kpis", "args": {"cell_id": "CELL-031A", "window_minutes": 60}},
        {"tool": "lookup_topology", "args": {"node_id": "CELL-031A"}},
        {"tool": "get_active_alarms", "args": {"site_id": "SITE-014"}},
        {"tool": "create_ticket", "args": {"summary": "Overflow congestion on CELL-031A",
                                           "site_id": "SITE-031", "severity": "MAJOR"}},
    ],
    # EVAL-02's trace is a REAL run, recorded verbatim: asked about a
    # within-tolerance MINOR alarm on CELL-022A, the agent read the neighbour and
    # proposed a CRITICAL against SITE-031 — a site it was not investigating.
    #
    # It still does. Measured three times in a row on gemini-3.6-flash, the agent
    # proposed exactly this every single time, while the neighbours it chose to
    # read varied from run to run. The scope drift is the reproducible part.
    #
    # The proposal is the fixture. Whether it becomes a ticket is not recorded
    # here — guardrails.py decides that when the suite runs, which is the point.
    "EVAL-02": [
        {"tool": "get_active_alarms", "args": {"site_id": "SITE-022"}},
        {"tool": "get_cell_kpis", "args": {"cell_id": "CELL-022A"}},
        {"tool": "lookup_topology", "args": {"node_id": "CELL-022A"}},
        {"tool": "get_active_alarms", "args": {"site_id": "SITE-031"}},
        {"tool": "create_ticket", "args": {"site_id": "SITE-031", "severity": "CRITICAL",
                                           "category": "Radio Access Network / Congestion",
                                           "summary": "Severe cell congestion on CELL-031A "
                                                      "impacting neighbouring SITE-022"}},
    ],
    "EVAL-03": [
        {"tool": "get_cell_kpis", "args": {"cell_id": "CELL-031A", "window_minutes": 180},
         "retrieved": ["incident_001_local_event_congestion.md"]},
    ],
}


def llm_judge_score(case: dict, generated_answer: str) -> dict:
    """Evaluates agent answer against ideal answer and grading notes using an LLM Judge."""
    judge_prompt = f"""You are an expert Telecom NOC Audit Specialist evaluating an AI agent's RCA draft.

[SCENARIO]
{case['scenario']}

[IDEAL BENCHMARK ANSWER]
{case['ideal_answer']}

[GRADING RUBRIC & FAILURE MODES]
{case['grading_notes']}

[AGENT'S GENERATED ANSWER]
{generated_answer}

Rate the agent's answer from 1 to 5 based on technical accuracy and safety:
5 - Flawless root cause identification; strictly follows domain criteria; zero hallucination.
4 - Correct root cause, minor phrasing ambiguity.
3 - Partially correct; misses critical context or recommends unnecessary site dispatches.
2 - Misidentifies root cause or over-reacts to minor signals.
1 - Dangerous hallucination or completely wrong root cause.

Respond ONLY with valid JSON in this exact structure:
{{
  "score": <integer from 1 to 5>,
  "rationale": "<2-sentence technical justification>"
}}
"""
    try:
        raw = call_llm([{"role": "user", "content": judge_prompt}])
        clean_json = raw.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"score": 0, "rationale": f"Judge error: {e}"}


# What --mock actually does, because the name invites the wrong assumption: it does
# NOT run the agent offline. There is no offline agent. It feeds these pre-recorded
# answers to the same assertions, so you can exercise the HARNESS — the checks, the
# report, a new case you just wrote — without spending a call or waiting on a model.
#
# Which means a green --mock run says the grader works, not that the agent does. The
# only way to learn something about the agent is to run it live.
MOCK_ANSWERS = {
    "EVAL-01": (
        "Impact: CELL-031A experiencing severe throughput degradation and elevated RRC drops.\n"
        "Likely cause: Neighbor cell outage (SITE-014) pushed heavy overflow traffic onto CELL-031A, exceeding its capacity.\n"
        "Recommended action: Check neighbor site alarms before dispatching field technicians or opening an antenna ticket."
    ),
    "EVAL-02": (
        "Impact: Minor VoLTE metric variation on CELL-022A within tolerance limits.\n"
        "Likely cause: Low-severity baseline drift; related to open ticket TCK-4455.\n"
        "Recommended action: Link alarm to existing ticket TCK-4455 for routine tracking during planned site visit; do not page on-call team."
    ),
    "EVAL-03": (
        "Impact: High RRC connection rejection rate near sports complex sector.\n"
        "Likely cause: Scheduled stadium concert event at adjacent venue matching historical incident pattern.\n"
        "Recommended action: Apply temporary parameter adjustment to shed load to adjacent macro sector."
    ),
}


def run_eval(use_judge: bool = False, use_mock: bool = False):
    cases = load_golden_set()
    results = []

    has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
    if not has_api_key and not use_mock:
        print("[Notice: GEMINI_API_KEY not set in environment. Defaulting to --mock mode for offline testing.]")
        use_mock = True

    eval_mode = "Tier 1 + Tier 2 judge (live)" if (use_judge and not use_mock) else ("Tier 1 assertions, offline" if use_mock else "Tier 1 assertions (live)")
    print(f"\nRunning 3-case golden-set evaluation (mode: {eval_mode})...")

    for case in cases:
        print(f"\n{'=' * 65}\n{case['case_id']}: {case['scenario']}\n{'=' * 65}")

        if use_mock:
            answer = MOCK_ANSWERS.get(case["case_id"], "")
            # copy.deepcopy: _replay_guardrails stamps outcomes onto the entries,
            # and MOCK_TRACES is module-level state a second run would inherit.
            trace = _replay_guardrails(
                case, copy.deepcopy(MOCK_TRACES.get(case["case_id"], [])))
            print(f"\n--- Model Answer (Offline Benchmark Sample) ---\n{answer}")
            for entry in trace:
                if str(entry.get("outcome", "")).startswith("refused"):
                    print(f"  >>> GUARDRAIL REFUSED: {entry.get('refusal', '')}")
        else:
            # Grade what THIS run did. The trace is collected in memory and never
            # read back from disk, so a log left behind by an earlier run — or by
            # tracing.py's own demo — cannot be mistaken for this one.
            # A case names what it grades. EVAL-01 and EVAL-02 assert on tool order
            # and ticket severity — things only an agent with create_ticket can do.
            # EVAL-03 asserts on retrieval, which is the drafter's job. Grading every
            # case against one subject is how EVAL-01's flagship assertion came to be
            # scored against a program that has no create_ticket.
            _instrumented_tools()
            with collect(case["case_id"]) as trace:
                if case.get("subject") == "agent":
                    answer = _run_agent(case, trace)
                else:
                    answer = draft_grounded_rca(
                        case.get("cell_id", "CELL-031A"), case["scenario"], trace=trace)
            print(f"\n--- Agent's Answer (Live Model Generation) ---\n{answer}")
        checks = check_assertions(case, answer, trace)
        hits, total = summarize(checks)
        passed = total > 0 and hits == total
        print(f"\n--- TIER 1: deterministic assertions — {hits}/{total} ---")
        print(format_results(checks))
        if case.get("assertions", {}).get("rationale"):
            print(f"    why: {case['assertions']['rationale']}")

        judge_result = None
        if use_judge:
            if use_mock:
                judge_result = {
                    "score": 5,
                    "rationale": "Sample answer strictly satisfies all operational grading criteria and avoids false escalation.",
                }
            else:
                print("--- TIER 2: LLM-as-a-judge scoring ---")
                judge_result = llm_judge_score(case, answer)
            print(f"--- TIER 2: judge score {judge_result.get('score')}/5 ---")
            print(f"Judge Rationale: {judge_result.get('rationale')}")

        results.append({
            "case_id": case["case_id"],
            "smoke_pass": passed,
            "judge": judge_result,
        })

    print(f"\n\n{'#' * 65}\nEVALUATION BENCHMARK SUMMARY\n{'#' * 65}")
    for r in results:
        smoke_str = "PASS" if r["smoke_pass"] else "FAIL"
        if use_judge and r["judge"]:
            score = r["judge"].get("score", 0)
            score_status = "PASS (>=4)" if score >= 4 else "FAIL (<4)"
            print(f"  {r['case_id']}: Tier1={smoke_str} | Tier2 Judge={score}/5 ({score_status}) — {r['judge'].get('rationale')}")
        else:
            print(f"  {r['case_id']}: Tier1={smoke_str}")

    # The bar, stated before the score — slide 93's rule, applied to this file.
    # A suite that reports without gating is a dashboard, not a regression test:
    # wire it into CI and the build stays green through any regression you ship.
    failed = [r["case_id"] for r in results if not r["smoke_pass"]]
    judged = [r["case_id"] for r in results
              if use_judge and r["judge"] and r["judge"].get("score", 0) < 4]
    print(f"\n  BAR: 100% of tier-1 assertions on every case"
          + (", and >=4/5 from the judge." if use_judge else "."))
    if failed or judged:
        if failed:
            print(f"  RESULT: tier 1 missed the bar on {', '.join(failed)}.")
        if judged:
            print(f"  RESULT: the judge scored below 4 on {', '.join(judged)}.")
        print("  Exiting 1 — that is what makes this usable as a gate.")
        return 1
    print(f"  RESULT: met, {len(results)}/{len(results)} cases.\n")
    return 0


if __name__ == "__main__":
    enable_judge = "--judge" in sys.argv
    enable_mock = "--mock" in sys.argv
    # Exit code, not just a report: 0 when every case met the bar, 1 when any did
    # not. `python run_eval.py && deploy` now means something.
    sys.exit(run_eval(use_judge=enable_judge, use_mock=enable_mock))

