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

**3. Add a fifth tool, and see whether the model reaches for it.** `get_recent_changes(site_id)` returns change and maintenance records — what a NOC correlates against first: before blaming a cell, ask whether anybody touched it. Add it to `TOOL_SCHEMAS`, dispatch it (read-only, so no gate), and ask about SITE-031 without mentioning changes.

The wiring is ten lines. The question is whether the model **uses** it, and the only thing advertising it is the `description` — that one sentence is prompt surface. Watch three things: does it call the tool at all; does it read the *status* (SITE-022's only record is an RRU replacement **SCHEDULED** for 16 Sep, which has not happened); and does a clean result change the answer (SITE-031's last change added no capacity, so "nothing recent explains this" is itself evidence).

`python solution_fifth_tool.py` shows the wiring and what the tool returns — offline, no key. Add `--live` to ask the agent for real (about 10 calls) and see whether it picks the tool up.

**4. Rewrite a description and watch tool choice move.** Change `get_cell_kpis`'s description from *"Get a COMPUTED KPI summary… The tool does the arithmetic so you don't have to"* to *"Returns KPI data for a cell."* and run twice. Does it still call it first? Does it start passing `window_minutes`? Does it try to do the arithmetic itself? Runs vary, so run each version twice before concluding anything — the point is that you cannot stop a model choosing badly, but you can make the right choice the obvious one.

---

## Two Things This Lab Does Not Do

* **Idempotency.** Propose the same ticket twice and you get two tickets. Against a mock that is harmless; against a real ITSM system it is a duplicate on someone's queue. Production passes a dedupe key derived from the site and the condition, so a retry updates the existing ticket instead of opening another.
* **Unbounded conversation.** `max_turns=10` bounds the loop the way Module 5's `max_steps` bounded its own: the model chooses what to do next, so something other than the model has to choose when to stop.

### What a production wiring adds

Named here rather than built, because each would add machinery that hides the lesson:

| Concern | What you add |
|---|---|
| Transient failures | Retry with backoff on 429 and 5xx, and a cap so a retry storm cannot become the outage |
| A tool that hangs | A per-call timeout, returned to the model as an observation rather than raised |
| Duplicate writes | An idempotency key derived from the condition, so a retry updates rather than duplicates |
| Cost and latency | A per-call log of tokens, duration and outcome — Module 10 turns this into tracing |
| Several calls at once | `message.tool_calls` is a list. Independent reads can run in parallel; writes must not be reordered, which is why the read/write split is worth keeping strict |

---

## Key Files
* `noc_assistant.py`: Complete implementation with `TOOL_SCHEMAS`, dispatch handler, and multi-turn tool-calling loop.
* `../data/llm_client.py`: Implements `call_llm_tools()` which converts OpenAI-style tool declarations to Gemini API function declarations and parses candidate tool calls.
* `../data/mock_tools.py`: OSS/BSS mock backend tools.
* `../data/guardrails.py`: the argument schemas (`CreateTicketArgs` and friends), the severity ceiling derived from the alarm feed, and the investigation scope. Run it directly — `python ../data/guardrails.py` — for six tool calls with three blocked, no API key needed.
