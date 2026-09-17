"""
react_agent.py — Module 5 hands-on: a ReAct loop built from scratch, no framework

The model outputs plain text in a Thought / Action / Observation format. Our code
parses the Action line, dispatches to a real (mocked) tool, feeds the result back
as an Observation, and loops — until the model outputs a Final Answer.

Safety circuit breakers implemented:
1. Hard step budget (`max_steps=6`).
2. Cycle detection: catches repetitive tool calling (ping-pong) and forces progress.
3. Graceful fallback: handles unknown tools and execution errors without crashing.

Run:
    python react_agent.py
"""

import os
import re
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm  # noqa: E402
from mock_tools import get_cell_kpis, get_active_alarms, lookup_topology  # noqa: E402

TOOLS = {
    "get_cell_kpis": get_cell_kpis,
    "get_active_alarms": get_active_alarms,
    "lookup_topology": lookup_topology,
}

SYSTEM_PROMPT = """You are a NOC triage agent for NetOps Co. You reason step by
step and can call tools to check real data before concluding. Available tools:

- get_cell_kpis[cell_id]     — returns recent KPI counters for a cell
- get_active_alarms[site_id] — returns active alarms for a site
- lookup_topology[node_id]   — returns topology info (neighbors, capacity, vendor)

Follow the 4-layer diagnostic order:
1. Physical / RF (local cell alarms & counters)
2. Transport / Backhaul (neighbor cells & link state)
3. Control-Plane Signalling (RRC drop reject causes)
4. Core Services (AMF/SMF/PCF)

Use EXACTLY this format, one step at a time:

Thought: <your reasoning about what to check next>
Action: tool_name[argument]

Wait for the Observation before continuing. When you have enough information,
respond with:

Thought: <final reasoning>
Final Answer: <your conclusion, in 2-3 sentences>

Never skip straight to a Final Answer without checking at least one tool first.
Do NOT repeat the same tool call with the same arguments if data has already been returned.
"""

ACTION_PATTERN = re.compile(r"Action:\s*(\w+)\[(.*?)\]")


def run_react_agent(question: str, max_steps: int = 6) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    call_history = []  # Tracks (tool_name, argument) to detect cognitive cycles

    for step in range(1, max_steps + 1):
        response_text = call_llm(messages)
        print(f"\n--- Step {step} ---\n{response_text}")

        if "Final Answer:" in response_text:
            return response_text

        match = ACTION_PATTERN.search(response_text)
        messages.append({"role": "assistant", "content": response_text})

        if not match:
            messages.append({
                "role": "user",
                "content": "Observation: No valid Action found. Use the exact "
                           "format 'Action: tool_name[argument]' or give a Final Answer.",
            })
            continue

        tool_name, arg = match.group(1), match.group(2).strip()

        # Circuit Breaker: Cognitive Cycle Detection
        call_history.append((tool_name, arg))
        if call_history.count((tool_name, arg)) >= 2:
            observation = (
                f"CYCLE DETECTED: You have already called {tool_name}[{arg}]. "
                "The network telemetry has not changed. Do NOT call this tool again with the same argument; "
                "reason on the data you already have or inspect neighboring nodes."
            )
            print(f"Observation: {observation}")
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            continue

        if tool_name not in TOOLS:
            observation = f"Unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}"
        else:
            try:
                observation = TOOLS[tool_name](arg)
            except Exception as e:  # keep the loop alive even on a bad argument
                observation = f"Error calling {tool_name}: {e}"

        print(f"Observation: {observation}")
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    return (
        "Max steps reached without a Final Answer — cognitive step budget exhausted. "
        "Escalating incident to Human L3 NOC Queue with recorded diagnostic trace."
    )


if __name__ == "__main__":
    question = "Why is CELL-031A underperforming right now?"
    print(f"Question: {question}")
    result = run_react_agent(question)
    print(f"\n=== RESULT ===\n{result}")
