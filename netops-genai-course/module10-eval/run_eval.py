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
    python run_eval.py

Run both tiers:
    python run_eval.py --judge
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "module04-rag"))
from llm_client import call_llm  # noqa: E402
from rag_pipeline import draft_grounded_rca  # noqa: E402
from assertions import check_assertions, format_results, summarize  # noqa: E402

GOLDEN_SET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "eval_golden_set.json"
)


def load_trace(case_id: str) -> list:
    """Read tool calls for this case from tracing.py's JSONL log, if present.
    Returns [] when there's no trace — tier 1 then reports vacuous passes rather
    than crashing, which is the right behaviour for a first live run.
    """
    path = os.path.join(os.path.dirname(__file__), "trace_log.jsonl")
    if not os.path.exists(path):
        return []
    steps = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("case_id") not in (None, case_id):
                continue
            steps.append({
                "tool": entry.get("tool") or entry.get("function") or "",
                "args": entry.get("kwargs") or entry.get("args") or {},
                "retrieved": entry.get("retrieved", []),
            })
    return steps


def load_golden_set():
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        return json.load(f)["cases"]


# Tier 1 assertions now live in data/eval_golden_set.json under each case's
# "assertions" key — see assertions.py for the checker. Nothing to hardcode here.

# Offline tool-call traces, so tier 1 is demonstrable without an API key. In a
# live run these come from tracing.py's JSONL log instead.
MOCK_TRACES = {
    "EVAL-01": [
        {"tool": "get_cell_kpis", "args": {"cell_id": "CELL-031A", "window_minutes": 60}},
        {"tool": "lookup_topology", "args": {"node_id": "CELL-031A"}},
        {"tool": "get_active_alarms", "args": {"site_id": "SITE-014"}},
        {"tool": "create_ticket", "args": {"summary": "Overflow congestion on CELL-031A",
                                           "site_id": "SITE-031", "severity": "MAJOR"}},
    ],
    "EVAL-02": [
        {"tool": "get_active_alarms", "args": {"site_id": "SITE-022"}},
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
            print(f"\n--- Model Answer (Offline Benchmark Sample) ---\n{answer}")
        else:
            answer = draft_grounded_rca("CELL-031A", case["scenario"])
            print(f"\n--- Agent's Answer (Live Model Generation) ---\n{answer}")

        trace = MOCK_TRACES.get(case["case_id"], []) if use_mock else load_trace(case["case_id"])
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


if __name__ == "__main__":
    enable_judge = "--judge" in sys.argv
    enable_mock = "--mock" in sys.argv
    run_eval(use_judge=enable_judge, use_mock=enable_mock)

