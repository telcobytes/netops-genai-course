# NetOps Co. — Q3 Network Change Advisory Bundle (Sample)

*Original sample document for course use — a stand-in for the kind of dense,
multi-page bundle (vendor change requests, maintenance notices, incident summaries)
that piles up in a real NOC inbox. Have students upload this into a notebook-style
AI tool (e.g., NotebookLM) and ask it to produce a one-page briefing.*

## Change Request CR-2201: VendorA Software Upgrade
VendorA will push a software upgrade to all 5G-NR cells in the North region between
01:00–04:00 local time on the night of September 20th. Expected impact: brief
(under 2 minute) service interruption per cell as it reboots into the new software
version. No customer-facing announcement is planned since the maintenance window is
outside peak hours.

## Change Request CR-2214: VendorB Parameter Update
VendorB will apply an updated handover parameter set to CELL-022A to reduce the
VoLTE call drop rate flagged in ticket TCK-4455. The change will be applied during a
low-traffic window and monitored for 48 hours afterward before being marked complete.

## Maintenance Notice: Backhaul Provider Fiber Work
The backhaul provider serving the SITE-014/SITE-031 corridor has scheduled fiber
splicing work for September 22nd, with a possible brief latency increase (not a full
outage) during the maintenance window. No customer impact is expected.

## Incident Summary: Recurring Congestion Near Event Venue (SITE-031)
As documented in a prior incident postmortem, CELL-031A has shown a recurring
congestion pattern tied to scheduled events at a nearby venue. The RF planning team
has an open action item to evaluate a permanent capacity or coverage adjustment for
this cell ahead of the venue's upcoming event calendar for Q4.

## Open Items Needing NOC Manager Sign-off
1. Approve or reject the CR-2201 maintenance window.
2. Confirm monitoring plan for CR-2214's 48-hour post-change window.
3. Decide whether to proactively apply the temporary handover-bias fix at CELL-031A
   ahead of the next known event at the nearby venue, or wait for the RF team's
   permanent-capacity recommendation.
