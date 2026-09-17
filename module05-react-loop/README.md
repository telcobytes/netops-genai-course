# Module 5 — From Prompts to Agents: The Hand-Rolled ReAct Loop

An autonomous triage agent in pure Python, with **zero agent frameworks** (no LangChain, no CrewAI, no AutoGen). Everything here is a loop, a regex, a dictionary of tools and two guards — small enough to read in one sitting, which is the point. When the frameworks change next year, this still makes sense.

---

## The loop

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Thought: reason about what to check next                 │
│ 2. Action: name a tool and an argument — tool_name[arg]     │
│ 3. Observation: YOUR code runs the tool, feeds back the data│
└──────────────────────────────┬──────────────────────────────┘
                               │ loops until
                               ▼
                Final Answer: the conclusion
```

**The model never executes anything.** It emits text saying what it wants; `run_react_agent` decides whether to run it. Every safety property in this course lives in that gap — which is why asking the agent to `create_ticket` (a tool that is not registered) gets you `Unknown tool` rather than a ticket.

---

## What a run prints

```
--- Step 1 --- (sending 1,095 chars in 2 messages)
Thought: Let's check Layer 1 (Physical / RF) ...
Action: get_cell_kpis[CELL-031A]
Observation: {'cell_id': 'CELL-031A', 'latest': {...}, 'thresholds_crossed': [...]}
...
Done in 5 step(s). Context grew 1,095 -> 5,618 chars.
```

The size on each step is what that step actually costs: **the whole conversation, sent again.** A run's cost grows with steps × history, not with steps.

That is also why observations are trimmed before they are stored. `get_cell_kpis` returns a `readings` list — the five raw 15-minute rows the summary was computed from — which no run has ever cited. Dropping it takes one observation from 2,236 to 907 characters and, measured by replaying the same four actions, the run sends **8,856 characters instead of 12,843: 31% less, from one field**.

---

## The three guards

1. **Step budget (`max_steps=6`).** A hard ceiling. Reached without a conclusion, the agent stops and says so; nothing is escalated automatically, because nothing here can escalate.
2. **Repeat detection.** The same `(tool, argument)` twice in one question gets an observation saying so instead of a second call. **This rule is right here and wrong in production:** the fixtures are a frozen snapshot, so a repeat cannot return anything new. On a live network, re-reading a KPI two minutes later is how you watch a cell recover. Key it on `(tool, argument, time bucket)`, or only complain when the observation really came back unchanged.
3. **Graceful fallback.** Unknown tools and bad arguments become observations the model can read and correct itself from, instead of exceptions.

---

## Memory: the transcript is yours

`run_react_agent` takes a `history` list you own. Pass one in and the transcript is written back into it; pass the same list to a later question and the agent continues:

```python
session = []
run_react_agent("Why is CELL-031A underperforming right now?", history=session)
run_react_agent("What should the NOC do about it first?", history=session)
```

Measured 17 Sep 2026: the first question took 5 steps, the follow-up 2 — it already held the KPIs, the topology and the alarms, and spent its one call checking a neighbour's headroom before recommending an offload. Memory does not make the agent skip work; it stops it repeating work it already did.

Nothing about that memory lives in the model. It lives in your list, which is what "the agent has state" actually means — and why deciding what stays in it is your job.

---

## The tools, and the 4-layer order

The system prompt tells the agent to work through Physical/RF → Transport/Backhaul → Control-Plane Signalling → Core Services, cheapest and most likely first.

This lab ships three read-only tools — `get_cell_kpis`, `get_active_alarms`, `lookup_topology` — which cover **layers 1 and 2**. Layers 3 and 4 are in the prompt to show how the order extends once you add tools for them (an RRC reject-cause lookup, a core KPI feed); here the agent infers them from the same counters.

---

## How to run

```bash
export GEMINI_API_KEY="..."          # free key: aistudio.google.com
python react_agent.py                 # the question, then a follow-up on the same session
```

Without a key it prints how to set one and exits — this module needs a model, since the whole lab is the model deciding what to do next.

In Colab, open `05_react_loop.ipynb`, which adds a rendered trace, the memory section, and four exercises: ask about the healthy cell CELL-022A, take `lookup_topology` away and watch it blame the cell it was given, ask for a tool that is not registered, and squeeze the budget to 2 steps.
