# Module 5 — From Prompts to Agents: The Hand-Rolled ReAct Loop

This module builds an autonomous triage agent from scratch in pure Python with **zero agent frameworks** (no LangChain, no CrewAI, no AutoGen).

---

## The ReAct Architecture

The agent runs a dynamic cognitive loop:
```
┌─────────────────────────────────────────────────────────────┐
│ 1. Thought: Reason about current state and what to check    │
│ 2. Action: Output formatted tool call `tool_name[arg]`      │
│ 3. Observation: Code executes tool and feeds back telemetry │
└──────────────────────────────┬──────────────────────────────┘
                               │ loops until
                               ▼
            Final Answer: Root Cause Conclusion
```

---

## Production Circuit Breakers Built-In

1. **Hard Step Budget (`max_steps=6`):** Prevents infinite loops and runaway API costs.
2. **Cycle Detection:** If the agent queries the exact same tool and parameter twice (e.g. asking for `get_cell_kpis[CELL-031A]` again because it's confused), the execution harness intercepts the call with a diagnostic warning, forcing progress.
3. **Escalation Fallback:** If the step budget is exhausted without reaching a conclusion, the agent gracefully falls back to an escalation briefing for Human L3 NOC engineers.

---

## How to Run

```bash
python react_agent.py
```
