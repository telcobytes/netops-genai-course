# Module 7 — Agentic Workflow Patterns for NOC Operations

Module 5 covered how *one* agent thinks (CoT, ReAct, Plan & Execute, Reflection).
This module covers a different axis: how steps and agents get **wired together**.

## What you'll learn

By the end you should be able to:

1. **Pick a pattern on purpose.** Five ways to wire work, each with the situation it
   is for — and the situations it is not for.
2. **Drop noise before it costs anything.** A router without a DROP route does not
   reduce noise, it distributes it faster.
3. **Build a critic that is worth its tokens.** A critic only helps if it knows
   something the drafter didn't; without that it invents criteria and sounds rigorous.
4. **Say why you chose multi-agent.** The reason is disagreement you can read, not speed.
5. **Know what to bound.** Every loop here has a cap, for the same reason the ReAct
   loop had a step budget.

## The setup

Everything runs against the same mock network as the rest of the course — no live
OSS access, no credentials:

| Input | What it is |
|---|---|
| `data/alarms.csv` | Six active alarms across SITE-031, SITE-014 and SITE-022 — a small alarm storm, mostly noise |
| `data/kpis.csv` | 15-minute counters for CELL-031A and its neighbours (the congestion the course opened with) |
| `data/topology.json` | Neighbours, planned capacity and vendor per site |

The scenario is the one running through the whole course: **CELL-031A is degrading,
and the question is whether the cell is at fault or something else is pushing load
onto it.**

## Two ways to run every lab

| | Command | What you get |
|---|---|---|
| **Mock** | `python 02_routing.py --mock` | Canned model answers. The wiring runs end to end, free, no key, same result every time. |
| **Live** | `python 02_routing.py` | The same wiring with a real model making the decisions. Needs `GEMINI_API_KEY`. |

Without a key you get mock either way, and the first line of output says so. Start
in mock to see the shape, then run it live — the orchestration is the lesson, and
the model is a component inside it.

## The five patterns

| # | Pattern | Telecom shape | Reach for it when |
|---|---------|---------------|-------------------|
| 1 | **Prompt Chaining** | alarm → classify domain → draft RCA → format ticket | The steps are always the same, in the same order |
| 2 | **Routing** | triage dispatcher → RAN / transport / core / drop | Incoming work is heterogeneous and specialists need different tools |
| 3 | **Parallelization** | KPI + alarms + topology at once, then synthesize | Sub-tasks are independent *and* latency matters |
| 4 | **Evaluator-Optimizer** | RCA draft → critic with the 4-layer checklist → revise | Output is open-ended, quality varies, a human will read it |
| 5 | **Orchestrator-Workers** | supervisor + RAN desk + transport desk | Evidence comes from different domains and may conflict |

## Run them

```bash
python 01_prompt_chaining.py --mock
python 02_routing.py --mock
python 03_parallelization.py --mock
python 04_evaluator_optimizer.py --mock
python 05_orchestrator_workers.py --mock
```

Drop `--mock` on any of them to run it live.

## What you should see

Measured on `gemini-3.6-flash`, and identical offline unless noted.
Your live numbers may differ a little — agent runs vary — but the shapes should hold.

**1. Chaining.** Three links, each validated before the next runs: a fault domain
from the taxonomy, an RCA, then ticket arguments that parse. The value is not the
decomposition, it is that a failure names its own step.

**2. Routing.** Six alarms in, and the tally is `RAN=2  TRANSPORT=0  CORE=1  DROP=3`:

```
3 of 6 alarms never reached a specialist.
```

All three dropped alarms describe themselves as within tolerance, informational or
self-recovered. During a storm that ratio is what keeps the system usable.

**3. Parallelization.** Three analyses fan out and are synthesized, and the run
prints its wall clock — 5.07s live for three analyses. Run sequentially, the
operator waits for the sum instead of the slowest one.

**4. Evaluator-optimizer.** The first draft blames the AMF and is REJECTED, with the
skipped layers named; revision 1 walks the cheaper layers first and PASSES.

Then the run ends by putting that same draft past **two critics at once** — one
holding the checklist, one without it, everything else identical:

```
WITH the 4-layer checklist   rejected for: Physical / RF, Transport / Backhaul
WITHOUT it                   rejected for: incident timeline, preventive measures,
                                           confirmed root cause
```

Both rejected it. Only one read the actual mistake. That contrast is the pattern's
whole argument, so the lab runs it rather than asserting it.

**5. Orchestrator-workers.** Four raw alarms collapse to two incidents, the two desks
report separately and **disagree**, and the supervisor says which evidence it relied
on and which it set aside.

## Two things the output should make you ask

**Why does the transport desk never get anything?** Because both transport-ish alarms
are MINOR and self-clearing, so they are correctly dropped. A desk that sits idle on
a noisy feed is not a bug — it is what the ratio looks like. To watch it fire, build
a transport alarm as a dict in code and pass it to `route()`. Don't add a row to
`data/alarms.csv`: later modules count those rows.

**Is ALM-9002 really a CORE problem?** `RRC_DROP_RATE_HIGH` on a cell that is
simultaneously saturating is a *symptom* of capacity — which is exactly what the
critic in pattern 4 concludes. The router sees one alarm at a time, so it cannot know
that. Correlating across alarms is a different job, and it is what deduplication does
in pattern 5.

## The three things worth remembering

**1. Routing is already how you work.** An alarm arrives, someone decides "that's RAN"
or "that's transport", and it goes to the right desk. Pattern 2 is your escalation
tree written down — including the DROP route, which is the part people skip.

**2. A critic only helps if it knows something the drafter didn't.** In
`04_evaluator_optimizer.py` the critic holds the 4-layer diagnostic order and the
drafter never sees it, so the question is not "is this RCA good?" (unanswerable) but
"were the cheaper layers ruled out before an expensive one was blamed?" (a fact). The
loop is bounded at `MAX_REVISIONS = 2`.

Two details of that lab, both measured rather than assumed:

* **Strip the checklist out and the critic does not go soft — it goes generic.** On the
  same draft it still rejected, but for a missing timeline, missing preventive measures
  and an "unconfirmed" cause: criteria it invented, none of them the diagnostic error.
  It would have sent the drafter off to add a timeline while it still blamed the AMF.
  Generic looks like rigour, which is why this failure is worse than praise.
* **The first draft is seeded, on purpose.** Asked cold, the live model diagnoses
  capacity correctly first time and the critic passes it — a loop that never loops
  teaches nothing. Attempt 0 is the 3am mistake of blaming the loudest, most expensive
  layer; everything after it is real.

**3. Multi-agent is worth it for disagreement, not for speed.** The RAN desk reports
saturation with high confidence; the transport desk reports an auto-cleared latency
warning with low confidence. One agent would weigh both inside a single context and
silently pick a winner. Two desks force the conflict into the open, where the
supervisor has to say which evidence it trusted — and where you can read that
reasoning. That is the CELL-031A question this course opened with.

*(Those two confidence values are constants in the worker functions, so the
disagreement happens on every run. What the model actually does is the synthesis:
weighing the two reports and naming the one it set aside.)*

## What this module is NOT

Pattern 4 is a **runtime** loop that improves one answer. Module 10's evaluation is
**offline** testing that tells you whether the agent works at all. They are
complements and you want both — see `../module10-eval/README.md`.

Next: **Checkpoint 2** in `../checkpoints/02_routing/` — build the dispatcher
yourself, five alarms, and drop the noise.
