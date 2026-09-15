# Incident Postmortem: Localized Congestion Near a Public Event Venue

**Site affected:** SITE-031 (CELL-031A)
**Date:** 2026-06-14
**Category:** Congestion / Capacity

## Summary
A cell adjacent to a public event venue experienced a sharp rise in active users during
a scheduled evening event. PRB utilization climbed above 90%, RRC setup success rate
dropped into the 80s, and RRC drop rate rose above 7%. Customers in the area reported
slow data speeds and occasional call setup failures for roughly two hours.

## Root Cause
The cell's planned capacity was sized for typical daytime and evening traffic in the
area, not for a one-off event drawing a large crowd within its coverage footprint.
Neighboring cells did not absorb the overflow because of a coverage gap between
sectors near the venue entrance.

## Resolution
NOC engineers manually triggered a temporary parameter change to favor handovers to
a neighboring cell with spare capacity, and coordinated with the RF planning team to
review coverage near the venue. No permanent capacity upgrade was required since the
event was one-off; a note was added to the site record to proactively apply the same
temporary handover bias ahead of any future scheduled events at that venue.

## Lessons Learned
- Cells near event venues, stadiums, or transit hubs should be flagged for proactive
  monitoring ahead of known scheduled events.
- A quick manual handover-bias change was sufficient; no hardware change was needed.
