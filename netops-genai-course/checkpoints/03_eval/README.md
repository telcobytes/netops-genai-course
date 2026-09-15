# Checkpoint 3 — Write your own eval

**After Module 10 (Evaluation & Observability) · ~20 minutes**

The golden set has three cases. You're going to add a fourth — and it has to be
a *real* test.

## Task

In `starter.py`, fill in `MY_CASE` with a fourth golden case: a scenario, a
tier-1 `assertions` block, and two traces — one from an agent that should pass,
one from an agent that should fail.

## Pass condition

```bash
python check.py
```

Passes when your case is well-formed, has at least two assertions, **passes on
your good trace, and FAILS on your bad trace.**

## The requirement that catches people

A golden case that passes on every trace you throw at it is not a test. It's a
decoration. Plenty of real test suites are full of them — assertions so loose
that nothing could ever trip them, which is why they're green and why they've
never caught a regression.

So `check.py` demands that your case **discriminates**: it must reject something.
If your bad trace passes, your assertions are too weak, and the fix is to make
them sharper — not to make the bad trace worse.

## Choosing what to test

Pick a failure mode you actually worry about. Some that aren't yet covered:

- The agent proposes `set_tx_power` without human approval
- It opens a second ticket for a site that already has an open one
- It calls the same tool five times without the inputs changing
- It recommends a field dispatch for something resolvable remotely
- It never calls `get_active_alarms` and misses the alarm context entirely

The best one is whichever failure you'd be most annoyed to explain to your
manager.
