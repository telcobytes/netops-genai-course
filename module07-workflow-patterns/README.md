# Module 7 — Agentic Workflow Patterns for NOC Operations

Module 5 covered how *one* agent thinks (CoT, ReAct, Plan & Execute, Reflection).
This module covers a different axis: how steps and agents get **wired together**.

Five patterns, one telecom example each. All five run offline with `--mock`, so
you can study the orchestration before spending a token.

```bash
python 01_prompt_chaining.py --mock
python 02_routing.py --mock
python 03_parallelization.py --mock
python 04_evaluator_optimizer.py --mock
python 05_orchestrator_workers.py --mock
```

| # | Pattern | Telecom shape | Reach for it when |
|---|---------|---------------|-------------------|
| 1 | **Prompt Chaining** | alarm → classify domain → draft RCA → format ticket | The steps are always the same, in the same order |
| 2 | **Routing** | triage dispatcher → RAN / transport / core / drop | Incoming work is heterogeneous and specialists need different tools |
| 3 | **Parallelization** | KPI + alarms + topology at once, then synthesize | Sub-tasks are independent *and* latency matters |
| 4 | **Evaluator-Optimizer** | RCA draft → critic with the 4-layer checklist → revise | Output is open-ended, quality varies, a human will read it |
| 5 | **Orchestrator-Workers** | supervisor + RAN desk + transport desk | Evidence comes from different domains and may conflict |

## The three things worth remembering

**1. Routing is already how you work.** An alarm arrives, someone decides "that's
RAN" or "that's transport", and it goes to the right desk. Pattern 2 is your
escalation tree written down. Note the `DROP` route — most alarm feeds are mostly
noise, and a router without a way to say "this needs nobody" just distributes the
noise more efficiently.

**2. A critic only helps if it knows something the drafter didn't.** Self-critique
with identical context mostly produces confident hedging. In `04_evaluator_optimizer.py`
the critic holds the 4-layer diagnostic order from Module 5 — so it isn't asked
"is this RCA good?" (unanswerable) but "did it rule out RF before blaming Core?"
(a fact). That asymmetry is the whole pattern. And the loop is bounded at
`MAX_REVISIONS = 2`, for the same reason the ReAct loop has a step budget.

**3. Multi-agent is worth it for disagreement, not for speed.** In
`05_orchestrator_workers.py` the RAN desk reports saturation with high confidence
and the transport desk reports an auto-cleared latency warning with low confidence.
A single agent would weigh both inside one context and silently pick a winner.
Two desks reporting separately force the conflict into the open, where the
supervisor has to say which evidence it trusted — and where you can read that
reasoning. That is the CELL-031A question this course opened with.

## What this module is NOT

Pattern 4 is a **runtime** loop that improves one answer. Module 10's evaluation
is **offline** testing that tells you whether the agent works at all. They are
complements and you want both — see `../module10-eval/README.md`.
