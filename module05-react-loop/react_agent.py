"""
react_agent.py — Module 5 hands-on: a ReAct loop built from scratch, no framework

The model outputs plain text in a Thought / Action / Observation format. Our code
parses the Action line, dispatches to a real (mocked) tool, feeds the result back
as an Observation, and loops — until the model outputs a Final Answer.

Safety circuit breakers implemented:
1. Hard step budget (`max_steps=6`).
2. Cycle detection: catches repetitive tool calling (ping-pong) and forces progress.
   Correct here because the fixtures are frozen; see the note at the check itself
   before you take this rule to a live network.
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

# Fields the model reasons over. get_cell_kpis also returns `readings` -- the five
# raw 15-minute rows the summary was computed from -- which is most of its ~1,800
# characters and which no run has ever cited.
#
# Why it matters, and it is not tidiness: every step re-sends the ENTIRE
# conversation, so an observation kept at step 1 is paid for again at steps 2, 3
# and 4. Cost grows with steps x history, not with steps.
#
# Measured on the four-step run this file prints (17 Sep 2026), replaying the same
# actions with and without this one line:
#
#     without trimming   1,095 -> 3,400 -> 3,660 -> 4,688   12,843 chars sent
#     with trimming      1,095 -> 2,071 -> 2,331 -> 3,359    8,856 chars sent
#
# 31% of the run, from dropping a single field the model never reads. That is the
# cheapest lever in the loop, and the context hygiene the memory slide asks for.
KPI_FIELDS = ("cell_id", "window_start", "window_end", "latest", "rolling_avg",
              "delta", "thresholds_crossed")


def _trim(tool_name, result):
    """Keep what the model uses; drop what it only pays for."""
    if tool_name == "get_cell_kpis" and isinstance(result, dict):
        return {k: v for k, v in result.items() if k in KPI_FIELDS}
    return result


def _context_size(messages):
    return sum(len(m["content"]) for m in messages)


def run_react_agent(question: str, max_steps: int = 6) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    call_history = []  # Tracks (tool_name, argument) to detect cognitive cycles

    start_size = _context_size(messages)
    for step in range(1, max_steps + 1):
        # Printed before the call, because this is what the step actually costs:
        # the whole conversation so far, sent again.
        print(f"\n--- Step {step} --- (sending {_context_size(messages):,} chars "
              f"in {len(messages)} messages)")
        response_text = call_llm(messages)
        print(response_text)

        if "Final Answer:" in response_text:
            messages.append({"role": "assistant", "content": response_text})
            print(f"\nDone in {step} step(s). Context grew {start_size:,} -> "
                  f"{_context_size(messages):,} chars.")
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

        # Circuit breaker: repeat detection.
        #
        # Treating a repeat as an error is right for THIS lab because the fixtures
        # are frozen -- calling get_cell_kpis twice returns the same bytes. Do not
        # ship this rule as-is: in a live network, re-reading a KPI two minutes
        # later is how you watch a cell recover, and a guard like this would block
        # it. In production, key the check on (tool, argument, time bucket), or
        # only complain when the observation actually came back unchanged.
        call_history.append((tool_name, arg))
        if call_history.count((tool_name, arg)) >= 2:
            observation = (
                f"CYCLE DETECTED: You have already called {tool_name}[{arg}] in this "
                "turn, and this lab's telemetry is a frozen snapshot, so the answer "
                "cannot have changed. Do NOT call it again with the same argument; "
                "reason on the data you already have or inspect neighboring nodes."
            )
            print(f"Observation: {observation}")
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            continue

        if tool_name not in TOOLS:
            observation = f"Unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}"
        else:
            try:
                observation = _trim(tool_name, TOOLS[tool_name](arg))
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
