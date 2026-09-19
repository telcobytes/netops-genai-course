# Module 11 — Capstone: The Autonomous NOC Copilot

Every piece from the course, wired into one triage pipeline: alarms in, a grounded
RCA and a gated ticket proposal out.

---

## How to run

```bash
export GEMINI_API_KEY="..."
cd module11-capstone

python noc_copilot.py              # the full pipeline
python noc_copilot.py --no-skill   # Failure Lab #4 — the same run, procedure removed
```

No offline mode: without a key it prints how to set one and stops. Set
`AUTO_APPROVE=1` to skip the interactive approval prompt on a non-interactive run.

---

## The pipeline

```
DETECT     6 active alarms -> 3 MAJOR/CRITICAL
CORRELATE  3 signals -> 1 incident        (one fault, not three tickets)
RETRIEVE   prior runbooks for this incident's symptoms      (Module 4)
DIAGNOSE   the ReAct loop, with live KPI / alarm / topology tools  (Modules 5, 6)
DRAFT      one RCA, one gated ticket proposal               (Modules 6, 8, 10)
```

**Correlate is the step people leave out**, and nothing crashes when you do — you
just pay three times and hand your on-call three duplicate tickets to close. The
three MAJOR/CRITICAL alarms in the feed are all CELL-031A, all the same
congestion event. Grouping them is the cheapest win in the pipeline.

### Where each module shows up

| module | what it contributes here |
|---|---|
| 1, 3 | the brief, and the fixed Impact / Likely cause / Recommended action shape |
| 4 | retrieval of the historical runbooks for this incident |
| 5 | the reasoning loop and its step budget |
| 6 | native tool calling, and the human approval gate |
| 7 | correlate-then-triage: one incident at a time, not one alarm at a time |
| 8 | the 4-layer diagnostic procedure, read from `SKILL.md` at runtime |
| 10 | scope and severity, checked in code **before** the human is asked |

Module 9's MCP server exposes these same tools over the protocol. This file calls
them directly so the capstone has no transport to debug — run
`module09-mcp/mcp_client.py` to see the same tools over MCP.

---

## Failure Lab #4 — the agent blames the cell that is alarming

```bash
python noc_copilot.py --no-skill
```

This removes the 4-layer procedure and runs everything else unchanged. Every run
now prints a **verdict** — not how the RCA reads, but what the agent *did*:

```
[Verdict] neighbour(s) read before any ticket: CELL-014A, CELL-022A, SITE-014, SITE-022
[Verdict] NO neighbour was read before the agent concluded. It blamed the cell that was alarming.
```

**Run it more than once.** The failure is intermittent, and that is the finding:

| | runs | read a neighbour before ticketing |
|---|---|---|
| with the Skill | 4 | 4 of 4 — three of them read all four candidates |
| `--no-skill` | 3 | 2 of 3. One read nothing at all. |

The procedure did not change whether the agent *usually* checks. It changed
whether it *always* checks, and how completely. A rule that only usually runs is
not a rule — it is a good habit, and you cannot put a good habit on a rota.

**Why it is three places, not one.** The neighbour rule lives in `SKILL.md`, in
this file's prompt, *and* in Module 6's `SYSTEM_PROMPT`. Removing only the first
two changes nothing — measured, the agent complied both times anyway. An ablation
that leaves the rule somewhere in the context is not an ablation; it is a
demonstration that the rule works. `--no-skill` removes all three.

Then close the loop: Module 10's `run_eval.py` asserts neighbour-before-blame
deterministically, in microseconds, with no API call. That is what catches this
when nobody is watching.

---

## Your turn

1. **Widen the correlation key.** It is `(site, cell)` today, which is the simple
   version on purpose. Real correlation bounds a time window, follows topology (a
   transport fault raising alarms on every child cell), and knows which alarm
   types are symptoms of which. Change the key and watch the incident count move.
2. **Run `--no-skill` five times** and write down the compliance rate. Then run
   `module10-eval/repeat.py --runs 5 --mode chained` and compare what a *chain*
   buys over a *procedure*.
3. **Break a guardrail and re-run the eval.** `module10-eval/README.md` has the
   exercise. The capstone is what the eval is grading.

---

**Next:** Module 12 — what you built, and what production adds on top.
