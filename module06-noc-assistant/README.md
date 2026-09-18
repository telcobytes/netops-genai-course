# Module 6 — Tool Calling & Function Calling: The NOC Assistant

This module moves from Module 5's hand-rolled text-parsing ReAct loop to **Native Tool Calling / Function Calling** via the model provider's API.

---

## Core Architectural Concepts

### 1. Regex Parsing vs Native Tool Calling
* **Module 5 (Regex Parsing):** The model emits plain text like `Action: get_cell_kpis[CELL-031A]`, which our code parses with regex. Brittle, prone to hallucinated formats, and hard to pass complex structured parameters.
* **Module 6 (Native Tool Calling):** We supply standard **JSON Schemas** describing tool names, descriptions, and parameter types (`TOOL_SCHEMAS`). The model returns a structured tool call chosen against those schemas, with typed arguments, instead of prose we have to parse.

### 2. The Model Is an Orchestrator, Not a Runtime
The model **never executes code directly**. It returns a structured tool call request:
```
Model -> {"name": "get_cell_kpis", "arguments": {"cell_id": "CELL-031A"}}
  └──> OUR Python code inspects the call, executes it, and sends the result back as a {"role": "tool"} message.
```

### 3. Read vs Write Tool Segregation (Blast-Radius Containment)
* **Read Tools (`get_cell_kpis`, `get_active_alarms`, `lookup_topology`):** Safe, idempotent, read-only queries into performance management (PM) and fault management (FM) databases. The agent calls these autonomously.
* **Write Tools (`create_ticket`):** Real-world side effects! Can trigger on-call dispatches or update production ITSM systems. In `noc_assistant.py`, this tool is intercepted by a **Human-in-the-Loop (HITL)** approval gate:
  ```
    >>> Agent wants to open a ticket: {'summary': '...', 'site_id': 'SITE-031'}
        Approve? [y/N]
  ```

### 4. Two Checks Before the Human, in This Order
A person should never be asked to approve something code can already prove is wrong — that is how an approval gate becomes a rubber stamp. `_dispatch_tool` therefore runs two checks first, and the order is the lesson:

1. **The schema** (`guardrails.validate_tool_args`). Is this a well-formed ticket at all? The enum lives in `CreateTicketArgs`, so both of these are refused in microseconds, with a message the model can read and correct itself from:
   ```
   >>> SCHEMA REFUSED: Rejected call to create_ticket — severity: Input should be 'MINOR', 'MAJOR' or 'CRITICAL'
   >>> SCHEMA REFUSED: Rejected call to create_ticket — summary: String should have at least 10 characters
   ```
2. **The policy** (`guardrails.check_ticket_proposal`). A ticket can be well-formed and still overreach. Severity is checked against the alarm feed, and the site against the investigation's scope:
   ```
   >>> GUARDRAIL REFUSED: severity CRITICAL exceeds the evidence — the worst active alarm on SITE-022 is MINOR
   ```

Only a proposal that passes both reaches a human. And if the human says **no**, the model is told so plainly (`declined_by_human`) and asked to summarise instead of re-proposing — the decline is as real an event as the approval, and the trace records both.

### 5. Blast Radius (`scope`)
`run_noc_assistant(question, scope=[...])` declares which sites this investigation may file tickets against. Module 6 leaves it `None` — unbounded — and Module 10 tightens it, because reading a neighbour's KPIs does not authorise filing a ticket against that neighbour.

---

## How to Run

```bash
export GEMINI_API_KEY="..."

# Run interactively (will pause for your approval before opening a ticket):
python noc_assistant.py
```

### Unattended / Automated Testing
To run in CI/CD or automated evaluation where `input()` is not interactive:
```bash
AUTO_APPROVE=1 python noc_assistant.py
```

---

## Try This

Three exercises. The first two need no API key — they call the dispatcher directly, which is where every safety decision is made.

**1. Watch a refusal that never reaches a person.** Two kinds, for two different reasons:

```python
import sys; sys.path += ["../data", "."]
from noc_assistant import _dispatch_tool

# not a valid ticket at all — the schema refuses it
_dispatch_tool("create_ticket", {"summary": "PRB saturation at SITE-031",
                                 "site_id": "SITE-031", "severity": "URGENT"})

# a valid ticket that overreaches — SITE-022's worst active alarm is MINOR
_dispatch_tool("create_ticket", {"summary": "VoLTE drops slightly above baseline",
                                 "site_id": "SITE-022", "severity": "CRITICAL"})
```

**2. Say no at the gate.** Run `python noc_assistant.py` and answer `n`. The model is told `declined_by_human` and asked to summarise instead of re-proposing — a decline is a recorded decision, not a silence. Then run it again with `AUTO_APPROVE=1` and notice you never see the prompt at all. That is the escape hatch doing its job, and the reason it should stay visible.

**3. Add the fifth tool, and make the schema do the work.** `guardrails.py` already models `set_tx_power` with a bound of 10–46 dBm. Add it to `TOOL_SCHEMAS`, dispatch it through `validate_tool_args` the way `create_ticket` is, and ask the agent to raise power on CELL-031A. A proposal of 95 dBm is refused in microseconds by the bound, with a message the model can act on — no prompt, no human, no argument. That is the same lesson as the severity enum, on a tool where being wrong costs real money.

---

## Two Things This Lab Does Not Do

* **Idempotency.** Propose the same ticket twice and you get two tickets. Against a mock that is harmless; against a real ITSM system it is a duplicate on someone's queue. Production passes a dedupe key derived from the site and the condition, so a retry updates the existing ticket instead of opening another.
* **Unbounded conversation.** `max_turns=10` bounds the loop the way Module 5's `max_steps` bounded its own: the model chooses what to do next, so something other than the model has to choose when to stop.

---

## Key Files
* `noc_assistant.py`: Complete implementation with `TOOL_SCHEMAS`, dispatch handler, and multi-turn tool-calling loop.
* `../data/llm_client.py`: Implements `call_llm_tools()` which converts OpenAI-style tool declarations to Gemini API function declarations and parses candidate tool calls.
* `../data/mock_tools.py`: OSS/BSS mock backend tools.
* `../data/guardrails.py`: the argument schemas (`CreateTicketArgs` and friends), the severity ceiling derived from the alarm feed, and the investigation scope. Run it directly — `python ../data/guardrails.py` — for six tool calls with three blocked, no API key needed.
