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

## What these labs actually print (measured 18 Sep 2026)

| Lab | Result, live and offline |
|---|---|
| `02_routing.py` | **3 of 6** alarms dropped: RAN=2, CORE=1, DROP=3, **TRANSPORT=0**. Identical live and offline, twice each. |
| `04_evaluator_optimizer.py` | Seeded draft REJECTED, revision 1 PASSED, three live runs running. |
| `05_orchestrator_workers.py` | 4 raw alarms → 2 incidents; RAN high confidence, transport low; supervisor relies on RAN and says so. |

Two of those deserve a second look, and both make good exercises.

**The transport desk never gets an alarm.** Both transport-ish alarms in the feed
are MINOR and self-clearing, so they are dropped — correctly. The desk exists and
is never exercised, which is what a real noise-heavy feed looks like. If you want
to see it fire, hand `route()` a transport alarm you build in code (not by editing
`data/alarms.csv` — later modules count those rows).

**ALM-9002 goes to CORE, and it is arguable.** `RRC_DROP_RATE_HIGH` on a cell that
is simultaneously saturating is a *symptom* of capacity, which is exactly what the
critic in pattern 4 says. The router sees one alarm at a time, so it cannot know
that. That is the honest limit of per-item routing: correlation across items is a
different job, and pattern 5's deduplication is where it gets done.

## The three things worth remembering

**1. Routing is already how you work.** An alarm arrives, someone decides "that's
RAN" or "that's transport", and it goes to the right desk. Pattern 2 is your
escalation tree written down. Note the `DROP` route — most alarm feeds are mostly
noise, and a router without a way to say "this needs nobody" just distributes the
noise more efficiently.

**2. A critic only helps if it knows something the drafter didn't.** Self-critique
with identical context mostly produces confident hedging. In `04_evaluator_optimizer.py`
the critic holds the 4-layer diagnostic order from Module 5 — so it isn't asked
"is this RCA good?" (unanswerable) but "did it rule out the cheaper layers before
blaming an expensive one?" (a fact). That asymmetry is the whole pattern. And the
loop is bounded at `MAX_REVISIONS = 2`, for the same reason the ReAct loop has a
step budget.

Two things about that lab are worth knowing, because both were measured rather
than assumed:

*Strip the checklist out and the critic does not go soft — it goes generic.* On the
same draft it still rejected, but for a missing timeline, missing preventive
measures and an "unconfirmed" cause: criteria it invented, none of which is the
diagnostic error. It would have sent the drafter off to add a timeline while it
still blamed the AMF. A critic without an asymmetric advantage does not go quiet,
and generic looks like rigour.

*The first draft is seeded, on purpose.* Asked cold, the live model diagnoses
capacity correctly on the first attempt and the critic passes it — a loop that
never loops teaches nothing. So attempt 0 is a deliberately weak draft, the 3am
mistake of blaming the loudest and most expensive layer. Everything after it is
real: a live critic reads that draft, names what was skipped, and a live model
writes the revision.

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
