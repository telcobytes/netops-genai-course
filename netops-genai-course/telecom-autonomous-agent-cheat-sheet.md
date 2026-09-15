# The NetOps Autonomous Triage Stack — Architecture Cheat-Sheet

A durable reference guide for building and deploying AI agents in Mobile Network Operations (RAN, Transport, Core).

---

## 1. The Autonomous Triage Stack (5-Layer Model)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: OPERATIONAL OUTPUT & ACTIONS                                        │
│ • Formats: Structured JSON Schema (RFC-7159)                                │
│ • Artifacts: Shift-handoff briefings, 3GPP fault categorization, RCA drafts │
│ • Systems: ServiceNow, Jira, Remedy, Slack Incident Channels                │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: SAFETY, EVALS & GUARDRAILS                                         │
│ • Privilege Scoping: Autonomous read-only vs. gated mutating tools          │
│ • Schema Enforcement: Strict Pydantic parameter range validation            │
│ • Injection Hardening: Data-delimiter isolation (`<ticket_text>`)           │
│ • Regression Testing: 3-tier golden evals (Trace, Schema, LLM-as-a-Judge)   │
│ • Core Gate: `create_ticket` / state mutation ALWAYS requires human sign-off │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: COGNITIVE REASONING ENGINE                                         │
│ • Loop: ReAct (Reason → Act → Observe)                                       │
│ • Cost-Ordered Diagnostic: RF/Physical → Transport → Signaling → Core       │
│ • Circuit Breakers: Hard step budget (`max_steps=5`) & cycle detection       │
│ • Memory Architecture: Ephemeral scratchpad + working session state         │
│ • Packaging: Platform-agnostic Skills and SOP playbooks                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: TELECOM KNOWLEDGE GROUNDING (RAG)                                  │
│ • Ingestion: Structure-Aware Chunking (preserves SIP ladders, 3GPP tables)  │
│ • Retrieval: Cosine similarity over domain runbooks and historical RCAs     │
│ • Mode: Agentic RAG — retrieval invoked as an on-demand tool, not a pipeline │
├─────────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: NETWORK DATA & PROTOCOL INTEGRATION (MCP)                          │
│ • Transport: Model Context Protocol (stdio / JSON-RPC over SSE)             │
│ • Primitive 1 (Tools): `get_cell_kpis()`, `lookup_topology()`, `alarms()`   │
│ • Primitive 2 (Resources): `pcap://`, `syslog://`, `spec://` streams        │
│ • Primitive 3 (Prompts): Centralized, server-managed RCA interaction recipes │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The 4 Golden Rules of Telecom Agent Engineering

1. **Ground First:** Retrieval and live telemetry beat parametric weights every time. Even a #1 benchmarked domain model like TelecomGPT-R1 has zero knowledge of your live network's real-time state.
2. **Tools Compute, Agents Reason:** Never pass raw 1-second counter dumps into an LLM. Compute 15-minute rolling averages and threshold deltas inside your tool; let the agent interpret the semantic meaning.
3. **Standardize via MCP:** Implement your OSS/BSS connectors once behind an MCP server. Any compliant host (IDE, desktop app, custom backend) can connect without rewriting custom glue code.
4. **Enforce Human Gates:** Any action that mutates network state or submits an external ticket must require human-in-the-loop approval. Tracing and evals tell you the agent is *probably* right; humans keep "probably" from causing network outages.

---

## 3. Production Prompt Template: 3GPP Fault Taxonomy Enforcement

Use few-shot examples to constrain the agent's root-cause taxonomy to deterministic 3GPP operational buckets:

```text
You are NetOps Co.'s Lead NOC Triage Specialist.
Analyze the provided telemetry and categorize the root cause STRICTLY into one of the following 3GPP fault domains:
- CAPACITY_PRB_EXHAUSTION
- RADIO_ACCESS_INTERFERENCE
- TRANSPORT_BACKHAUL_JITTER
- CORE_SIGNALING_REJECT
- HARDWARE_EQUIPMENT_FAULT

[FEW-SHOT EXAMPLES]
Input: High DL PRB utilization (>90%), CQI stable (11-13), connected users > 350, zero active alarms.
Output: {"category": "CAPACITY_PRB_EXHAUSTION", "confidence": 0.95, "justification": "PRB exhaustion driven by user density without radio degradation."}

Input: Sudden spike in RRC connection drops, CQI dropped to < 5, neighbor site CELL-022A active TX alarm.
Output: {"category": "RADIO_ACCESS_INTERFERENCE", "confidence": 0.91, "justification": "Neighbor cell RF interference causing downlink SINR deterioration."}

Input: Normal radio metrics, high uplink latency (>85ms), GTP-U packet loss detected on microwave backhaul hop.
Output: {"category": "TRANSPORT_BACKHAUL_JITTER", "confidence": 0.94, "justification": "Fronthaul/backhaul link congestion causing packet discard."}

[CURRENT INCIDENT]
Input: {incident_telemetry}
Output:
```

---

## 4. ReAct Cognitive Circuit Breakers (Production Checklist)

When running autonomous triage loops in your Python agent, always implement the following guards:

- [ ] **Hard Step Limit:** `if step_count > 5: return escalate_to_human_l3()`
- [ ] **Tool Cycle Detection:** `if (tool_name, tool_args) in execution_history: inject_tool_warning()`
- [ ] **Negative Telemetry Handling:** Explicitly prompt that `active_alarms = []` is conclusive evidence that the local site is healthy—not an API error.
- [ ] **Fallback Briefing:** When timed out, output an **Escalation Summary**:
  - *Symptom:* Observed anomaly.
  - *Ruled Out:* List of clean subsystems inspected.
  - *Blocker:* Missing counter or ambiguity preventing autonomous resolution.

---

## 5. Resume / Portfolio Snippet

Add this bullet to your CV or LinkedIn profile:

> **Autonomous Telecom Operations Engineer**
> *"Architected and deployed an end-to-end Autonomous NOC Triage Agent in Python using ReAct loops, Model Context Protocol (MCP), and Structure-Aware RAG. Automated cross-domain root-cause analysis across 4G/5G RAN, Backhaul, and Core networks, reducing incident triage time from 20 minutes to 4 seconds with 3-tier golden-set eval verification."*

---

## 6. Python Prerequisites & 10-Minute Refresher

This course assumes basic Python comfort (reading functions and dictionaries). If you are coming from Bash, Perl, SQL, or vendor CLIs, here are the exact 5 patterns used across our agent scripts:

### A. Dictionary Access & List Comprehensions
Filtering alarms or KPI rows:
```python
# Filtering list of dicts (used in Module 10 Detect step)
major_alarms = [a for a in active_alarms if a["severity"] in ("MAJOR", "CRITICAL")]
```

### B. Standard File I/O (`csv` & `json`)
Loading tickets and parsing topology:
```python
import csv, json

with open("data/tickets.csv", newline="", encoding="utf-8") as f:
    tickets = list(csv.DictReader(f))

topology = json.loads(open("data/topology.json").read())
```

### C. Type Hints (Used in MCP & Tool Definitions)
Every FastMCP tool uses standard Python type annotations:
```python
def get_cell_kpis(cell_id: str, window_minutes: int = 15) -> list[dict]:
    ...
```

### D. Decorators (FastMCP Syntax)
In Module 8, tools are exposed via Python decorators:
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("noc-tools")

@mcp.tool()
def lookup_topology(node_id: str) -> dict:
    ...
```

### E. Top-Rated Free Refreshers (If You Need a Quick Brush-Up)
1. **[Automate the Boring Stuff with Python](https://automatetheboringstuff.com/) (Al Sweigart)** — The gold-standard practical guide for sysadmins & network engineers (Chapters on CSV, JSON, and Regex).
2. **[FastAPI Python Types Intro](https://fastapi.tiangolo.com/python-types/)** — The best 10-minute visual guide to modern Python type hints and dictionaries.
3. **[Exercism Python Track](https://exercism.org/tracks/python)** — Free, interactive, test-driven syntax drills.
