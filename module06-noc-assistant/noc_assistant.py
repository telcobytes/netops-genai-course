"""
noc_assistant.py — Module 6 hands-on: tool calling via the provider's native API

Unlike Module 5's hand-rolled text parsing, this uses the LLM API's actual
function-calling feature: we describe each tool with a JSON Schema, the model
decides which to call and with what arguments, and returns a structured request
that WE execute (the model never runs anything itself).

create_ticket is the one tool with a real side effect — it always requires a
human "y/n" confirmation before it actually fires (Module 10's human-in-the-loop
rule, previewed here).

Run:
    python noc_assistant.py
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm_tools  # noqa: E402
import guardrails  # noqa: E402
from mock_tools import (  # noqa: E402
    get_cell_kpis,
    get_active_alarms,
    lookup_topology,
    create_ticket,
)

SYSTEM_PROMPT = """You are a NOC assistant for NetOps Co. Use the available tools
to investigate before answering. Always check KPIs and alarms for the cell/site in
question, and check neighboring cells' topology before concluding the cell itself
is at fault — a neighbor outage can push overflow traffic onto a healthy cell.

When your investigation supports opening a ticket, CALL create_ticket. Do not ask
permission in your answer first. A human approval gate is enforced in code around
that tool, so calling it is a proposal, not an action — calling it is how you put
the proposal in front of a person.
"""
# Why the prompt no longer says "only if the user has approved it":
#
# That wording asked the MODEL to enforce the safety gate, which is exactly what
# Module 10 tells you never to do — safety belongs at the architectural boundary,
# in code, where the model does not get a vote. It also worked badly in both
# directions. The agent obeyed by describing a ticket in prose and asking, so the
# real gate in _dispatch_tool never ran, and nothing in the trace recorded the
# agent's most consequential decision. Module 10's central assertion —
# lookup_topology before create_ticket — had nothing to compare, because
# create_ticket never appeared.
#
# Now the agent proposes by calling the tool, _dispatch_tool asks the human, and
# the decision is visible in the trace whichever way the human answers.

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_cell_kpis",
            "description": "Get a COMPUTED KPI summary for a cell over a time window: rolling averages, deltas, and which operational thresholds are currently crossed. The tool does the arithmetic so you don't have to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cell_id": {"type": "string"},
                    "window_minutes": {
                        "type": "integer",
                        "description": "Look-back window in minutes. Defaults to 60.",
                    },
                },
                "required": ["cell_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_alarms",
            "description": "Get active alarms, optionally filtered to one site.",
            "parameters": {
                "type": "object",
                "properties": {"site_id": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_topology",
            "description": "Get topology info (neighbors, vendor, planned capacity) for a site or cell.",
            "parameters": {
                "type": "object",
                "properties": {"node_id": {"type": "string"}},
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": "Open a trouble ticket. Has a REAL side effect — requires human approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "site_id": {"type": "string"},
                    "category": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["MINOR", "MAJOR", "CRITICAL"],
                        "description": "Match the severity to the evidence. Do not escalate a within-tolerance signal.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]


def _dispatch_tool(name: str, args: dict):
    if name == "create_ticket":
        # Guardrails run BEFORE the human is asked. A person should never be shown a
        # proposal that code can already prove is out of bounds — that is how an
        # approval gate degrades into a rubber stamp.
        #
        # Two checks, in this order, and the order is the lesson:
        #
        #   1. The SCHEMA: is this even a well-formed ticket? The enum lives in
        #      CreateTicketArgs, so severity="URGENT" and a nine-character summary
        #      are rejected here, in microseconds, with a message the model can
        #      read and correct itself from. Asking the human first would be asking
        #      them to approve something that cannot be filed.
        #   2. The POLICY: is it in scope, and does the alarm feed support this
        #      severity? A ticket can be perfectly well-formed and still overreach.
        try:
            args = guardrails.validate_tool_args("create_ticket", args)
        except guardrails.GuardrailError as err:
            print(f"\n  >>> SCHEMA REFUSED: {err}")
            return {
                "status": "refused_by_schema",
                "reason": str(err),
                "note": "Rejected by the argument schema before any human saw it. "
                        "Re-propose with a valid severity and a summary of at least "
                        "10 characters.",
            }

        allowed, reason = guardrails.check_ticket_proposal(args)
        if not allowed:
            print(f"\n  >>> GUARDRAIL REFUSED: {reason}")
            return {
                "status": "refused_by_guardrail",
                "reason": reason,
                "note": "Refused in code, before any human saw it. Re-propose within the "
                        "investigation's scope and at a severity the alarm feed supports.",
            }
        print(f"\n  >>> Agent wants to open a ticket: {args}")
        if os.environ.get("AUTO_APPROVE") == "1":
            print("      [AUTO_APPROVE=1 detected: automatically approving ticket creation]")
            approved = True
        else:
            try:
                approved = input("      Approve? [y/N] ").strip().lower() == "y"
            except (EOFError, KeyboardInterrupt):
                print("      [Non-interactive environment: defaulting to 'No']")
                approved = False

        if not approved:
            # The agent's proposal is still a real, recorded event — the human
            # said no to it. Tell the model plainly so it stops re-proposing.
            return {
                "status": "declined_by_human",
                "note": "A human reviewed this proposal and declined it. "
                        "Do not propose it again; summarise your findings instead.",
            }
        try:
            return create_ticket(**args)
        except Exception as err:
            return {"error": f"Error creating ticket: {err}"}

    dispatch = {
        "get_cell_kpis": get_cell_kpis,
        "get_active_alarms": get_active_alarms,
        "lookup_topology": lookup_topology,
    }
    if name not in dispatch:
        return {"error": f"Unknown tool: '{name}'. Available tools: {list(dispatch.keys()) + ['create_ticket']}"}

    try:
        return dispatch[name](**args)
    except Exception as err:
        return {"error": f"Error executing {name}: {err}"}


def run_noc_assistant(question: str, max_turns: int = 10, scope=None) -> str:
    """`scope` declares the blast radius: the site ids this investigation may file
    tickets against. None leaves it unbounded, which is the Module 6 default."""
    with guardrails.investigation(scope):
        return _run(question, max_turns)


def _run(question: str, max_turns: int) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(max_turns):
        message = call_llm_tools(messages, tools=TOOL_SCHEMAS)

        if not message.tool_calls:
            if not message.content:
                # An empty turn: no text, no tool call. llm_client returns content=None
                # when the model's parts carry neither text nor a function call, and
                # returning it here put a bare "None" on screen as a capstone RCA.
                # Don't return nothing — spend another turn. max_turns is the bound.
                messages.append({"role": "user",
                                 "content": "Continue. Give your final answer now."})
                continue
            return message.content

        # Record the assistant's tool-call request, then execute each one
        messages.append(message)
        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            print(f"\n[tool call] {tool_call.function.name}({args})")
            result = _dispatch_tool(tool_call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

    return "Reached max turns without a final answer."


if __name__ == "__main__":
    question = "Why is site SITE-031 underperforming right now, and should we open a ticket?"
    print(f"Question: {question}\n")
    answer = run_noc_assistant(question)
    print(f"\n=== FINAL ANSWER ===\n{answer}")
