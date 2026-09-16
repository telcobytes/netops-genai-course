"""
run_skill.py — Module 8 hands-on: executing a portable Skill bundle in Python

Demonstrates how modern agent architectures ingest an external Skill (SKILL.md):
1. Loads the standardized domain instructions and 4-layer diagnostic procedure from SKILL.md.
2. Injects the skill procedure into the agent's system prompt.
3. Connects the tools re-exported by tools.py.
4. Executes autonomous investigation and formats the RCA into the standard NetOps Co. template.

Run:
    python run_skill.py
    python run_skill.py CELL-022A
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm_tools  # noqa: E402
from tools import get_cell_kpis, get_active_alarms, lookup_topology, create_ticket  # noqa: E402

SKILL_FILE = os.path.join(os.path.dirname(__file__), "SKILL.md")


def load_skill_instructions() -> str:
    """Reads the portable procedure definition from SKILL.md."""
    with open(SKILL_FILE, encoding="utf-8") as f:
        return f.read()


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
            "description": "Open a trouble ticket. Gated side effect — requires human approval.",
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
        print(f"\n  >>> Skill requested ticket creation: {args}")
        if os.environ.get("AUTO_APPROVE") == "1":
            print("      [AUTO_APPROVE=1 detected: ticket approved]")
            approved = True
        else:
            try:
                approved = input("      Approve? [y/N] ").strip().lower() == "y"
            except (EOFError, KeyboardInterrupt):
                approved = False

        if not approved:
            return {"status": "declined_by_human", "note": "Ticket was not approved."}
        return create_ticket(**args)

    dispatch = {
        "get_cell_kpis": get_cell_kpis,
        "get_active_alarms": get_active_alarms,
        "lookup_topology": lookup_topology,
    }
    if name not in dispatch:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return dispatch[name](**args)
    except Exception as err:
        return {"error": f"Tool execution failed: {err}"}


def execute_skill(cell_id: str = "CELL-031A", max_turns: int = 10) -> str:
    skill_content = load_skill_instructions()
    system_prompt = (
        "You are an autonomous NetOps AI Assistant. You have been equipped with "
        "the following specialized operational Skill:\n\n"
        f"{skill_content}\n\n"
        "Strictly adhere to the diagnostic procedure and the exact RCA output format specified in the Skill."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Investigate performance and produce an RCA for cell {cell_id}."},
    ]

    print(f"Executing Telecom RCA Skill on: {cell_id}...\n")

    for turn in range(1, max_turns + 1):
        message = call_llm_tools(messages, tools=TOOL_SCHEMAS)
        if not message.tool_calls:
            return message.content

        messages.append(message)
        for tc in message.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"  [Skill Action] {tc.function.name}({args})")
            result = _dispatch_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    return "Max turns reached without concluding RCA."


if __name__ == "__main__":
    target_cell = sys.argv[1] if len(sys.argv) > 1 else "CELL-031A"
    rca = execute_skill(target_cell)
    print(f"\n{'=' * 65}\nSTANDARDIZED SKILL RCA OUTPUT:\n{'=' * 65}\n{rca}\n")
