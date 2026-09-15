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
2. **Check neighbors before blaming the cell itself.** Call `lookup_topology` on
   the affected cell to find its neighbors, then check THEIR alarm status too.
   A neighbor outage can push overflow traffic onto an otherwise healthy cell —
   this is a common root cause that's easy to miss if you only look at the cell
   that's alarming.
3. **Check for a known prior pattern.** If a knowledge base or incident history is
   available (see Module 4's RAG pipeline), check whether this matches a
   previously-resolved incident before treating it as novel.
4. **Draft the RCA in this exact structure, every time:**
   ```
   Impact: <what the user/network experiences>
   Likely cause: <root cause, with the evidence that supports it>
   Recommended action: <a specific, proportionate next step>
   ```
5. **Never call `create_ticket` without explicit human approval.** This is the one
   tool with a real side effect (see Module 9's human-in-the-loop rule).

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
(150). Neighbor cells (CELL-014A, CELL-022A) show no active faults, ruling out a
neighbor-outage cause — this matches a recurring pattern seen near a nearby event
venue in a prior incident.

Recommended action: Apply a temporary handover-bias adjustment to shed load to
CELL-014A, and flag RF planning's open action item to assess a permanent
capacity/coverage fix for this cell.
```
