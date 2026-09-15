# Incident Postmortem: Overflow Traffic From a Neighboring Cell Outage

**Site affected:** SITE-031 (CELL-031A)
**Date:** 2026-04-02
**Category:** Congestion / Capacity

## Summary
A neighboring 4G cell (CELL-022A) went out of service due to a hardware fault. Devices
in the overlapping coverage area re-selected to CELL-031A, which then saw active users
climb well beyond its planned capacity within about 15 minutes. RRC drop rate and
throughput degraded on CELL-031A as a secondary effect of an outage elsewhere.

## Root Cause
CELL-022A's RRU failed and triggered an automatic cell shutdown. There was no capacity
headroom reserved on the surviving neighbor cell to absorb a full outage of an
adjacent cell during a busy period.

## Resolution
Field team replaced the faulty RRU at SITE-022 and restored CELL-022A within about
90 minutes, after which traffic on CELL-031A returned to normal levels on its own.
No changes were needed on CELL-031A itself once the root cause (the neighbor outage)
was resolved.

## Lessons Learned
- When a cell shows a sudden capacity/congestion pattern, always check whether a
  *neighboring* cell has an active fault before assuming the affected cell itself
  has a hardware or configuration problem — the real root cause may be elsewhere
  in the topology.
- This is a good example for triage agents: checking neighbor-cell alarm status
  should be an early step whenever a congestion-pattern alarm fires.
