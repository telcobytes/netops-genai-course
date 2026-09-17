---
name: telecom-rca
description: Diagnose a NetOps Co. cell/site performance issue and draft an RCA (root cause analysis) in the standard Impact/Likely cause/Recommended action format. Use this whenever asked to investigate why a cell or site is underperforming, or to draft an incident write-up.
---

# Telecom RCA Skill

This packages the Module 3 (prompting) + Module 6 (tool calling) work from this
course into one reusable bundle — "how NetOps Co. does RCA," defined once, instead
of re-explained in every prompt.

## When to use this skill
- A user asks why a specific cell or site is underperforming
- A user asks you to draft an RCA or incident summary
- An alarm or KPI anomaly needs triage

## Procedure

1. **Gather live data first.** Call `get_cell_kpis` and `get_active_alarms` for the
   cell/site in question before concluding anything.

2. **Check neighbours BEFORE blaming the cell.** Call `lookup_topology` on the
   affected cell to find its neighbours, then read THEIR KPIs and alarms too. A
   neighbour outage can push overflow traffic onto an otherwise healthy cell — a
   common root cause that is easy to miss if you only look at the cell that is
   alarming. Module 10's evaluation asserts this one directly: a neighbour's id
   must appear in the trace before any ticket is proposed.

3. **Work the four layers in cost order.** Cheapest and most common first; stop at
   the first layer whose evidence actually explains the symptom.

   1. **Physical / RF** — local cell alarms and counters; antenna tilt, VSWR,
      hardware faults
   2. **Transport / Backhaul** — link latency, jitter, packet loss between site
      and core (this is where a neighbour's state matters)
   3. **Control-Plane Signalling** — RRC/NAS setup failures, reject causes, timer
      expiries
   4. **Core Services** — AMF/SMF/PCF; checked last, least likely and most
      expensive to investigate

   This order is judgement, not discovery. A model will not derive it, and if you
   do not supply it the agent checks things in whatever order the prompt happens to
   suggest — which is how a routine congestion event turns into a core investigation.

   Before treating anything as novel, also check whether a knowledge base or
   incident history has a matching prior incident (see Module 4's RAG pipeline).

4. **Never call `create_ticket` without explicit human approval.** This is the one
   tool with a real side effect. The enforcement lives in Module 10's
   human-in-the-loop gate; the expectation travels with this bundle, so an agent
   loading this Skill in another project inherits the rule along with the procedure.

## Output format

Draft the RCA in this exact structure, every time:

```
Impact: <what the user/network experiences>
Likely cause: <root cause, with the evidence that supports it>
Recommended action: <a specific, proportionate next step>
```

## Tools this skill expects to have access to
See `tools.py` in this folder — it re-exports the four mock tools from
`data/mock_tools.py` so an agent loading this skill has everything it needs in
one place.

## Example

**Input:** "Why is CELL-031A underperforming?"

**Good output:**
```
Impact: Data throughput on CELL-031A has dropped from ~169 Mbps to ~54 Mbps over
the last hour, with RRC drop rate climbing to 11.4%.

Likely cause: Active users on the cell (214) now exceed its planned capacity
(150). Neighbour cells (CELL-014A, CELL-022A) show no active faults, ruling out a
neighbour-outage cause — this matches a recurring pattern seen near a nearby event
venue in a prior incident.

Recommended action: Apply a temporary handover-bias adjustment to shed load to
CELL-014A, and flag RF planning's open action item to assess a permanent
capacity/coverage fix for this cell.
```
