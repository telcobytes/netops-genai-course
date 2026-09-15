# Module 6 — Tool Calling & Function Calling: The NOC Assistant

This module moves from Module 5's hand-rolled text-parsing ReAct loop to **Native Tool Calling / Function Calling** via the model provider's API.

---

## Core Architectural Concepts

### 1. Regex Parsing vs Native Tool Calling
* **Module 5 (Regex Parsing):** The model emits plain text like `Action: get_cell_kpis[CELL-031A]`, which our code parses with regex. Brittle, prone to hallucinated formats, and hard to pass complex structured parameters.
* **Module 6 (Native Tool Calling):** We supply standard **JSON Schemas** describing tool names, descriptions, and parameter types (`TOOL_SCHEMAS`). The model's attention mechanism natively selects tools and outputs strongly-typed JSON arguments.

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

## Key Files
* `noc_assistant.py`: Complete implementation with `TOOL_SCHEMAS`, dispatch handler, and multi-turn tool-calling loop.
* `../data/llm_client.py`: Implements `call_llm_tools()` which converts OpenAI-style tool declarations to Gemini API function declarations and parses candidate tool calls.
* `../data/mock_tools.py`: OSS/BSS mock backend tools.
