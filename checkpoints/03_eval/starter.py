"""
Checkpoint 3 — Write your own eval.

Fill in MY_CASE below, then run: python check.py

The assertion vocabulary (see ../../module10-eval/assertions.py):
    required_tools        [str]        these tools must appear in the trace
    forbidden_tools       [str]        these must NOT appear
    tool_order            [[a, b]]     a must come before b
    max_ticket_severity   str          ceiling on create_ticket severity
    must_retrieve         [str]        these documents must be retrieved
    must_not_retrieve     [str]        these must not be
    answer_must_mention   [str]        substrings required in the answer
    answer_must_not_mention [str]      substrings forbidden in the answer
"""

MY_CASE = {
    "case_id": "EVAL-04",
    "scenario": "",  # TODO: describe the situation the agent is facing

    "assertions": {
        "name": "",  # TODO: short name for the failure mode you're guarding against
        # TODO: at least two assertions from the vocabulary above
        "rationale": "",  # TODO: one sentence — why this failure matters
    },

    # TODO: a trace from an agent that handles this WELL
    "good_trace": [
        # {"tool": "get_cell_kpis", "args": {"cell_id": "CELL-031A"}},
    ],
    "good_answer": "",

    # TODO: a trace from an agent that gets it WRONG. Your assertions must
    # reject this one — that's what makes the case a test rather than a comment.
    "bad_trace": [
        # {"tool": "create_ticket", "args": {"severity": "CRITICAL"}},
    ],
    "bad_answer": "",
}
