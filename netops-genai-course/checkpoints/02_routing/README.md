# Checkpoint 2 — Build the dispatcher

**After Module 7 (Workflow Patterns) · ~25 minutes**

Five alarms from two sites. Four of them belong to a specialist desk. One of
them belongs to nobody.

You're a NOC engineer — you already do this in your head every shift. This
checkpoint asks you to write it down.

## Task

Implement `route(alarm)` in `starter.py` so that each alarm goes to exactly one
of `RAN`, `TRANSPORT`, `CORE`, or `DROP`.

## Pass condition

```bash
python check.py
```

Passes at **5/5 correct routes**, with `ALM-7104` dropped rather than escalated.

## The one that matters

`ALM-7104` is a MINOR cabinet temperature warning that auto-cleared after 90
seconds. It is real, it is in the feed, and it needs nobody. A router with no
`DROP` route doesn't reduce noise — it just distributes it faster. During an
alarm storm that's the difference between a system that helps and one that
makes things worse.

## Two ways to solve it

Either is a pass, and the comparison is the lesson:

- **Deterministic** — keyword rules in Python. Free, instant, and for a feed
  this predictable, genuinely the right answer.
- **LLM router** — one `ask()` call with the route definitions. Handles wording
  you didn't anticipate, costs a call per alarm.

If you solve it deterministically, ask yourself what wording would break your
rules. If you solve it with a model, ask yourself whether this feed needed one.
