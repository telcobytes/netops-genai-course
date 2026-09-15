# Incident Postmortem: Elevated VoLTE Call Drop Rate

**Site affected:** SITE-022 (CELL-022A)
**Date:** 2026-05-20
**Category:** Voice Quality

## Summary
Field reports and a minor threshold-crossing alarm both flagged a mild increase in
VoLTE call drop rate at SITE-022. The increase stayed within tolerance and did not
trigger a major or critical alarm, but was tracked as a trouble ticket after repeated
field reports.

## Root Cause
Investigation traced the issue to a marginal IMS signaling delay during call setup
under specific radio conditions at the cell edge, rather than a hard fault. The
condition was intermittent and tied to time-of-day traffic patterns.

## Resolution
No emergency action was taken since the drop rate stayed within tolerance. The issue
was scheduled for review alongside a planned software update for the site, and the
ticket was tracked as low-priority rather than escalated.

## Lessons Learned
- Not every alarm or field report requires an active-tools response — some findings
  are correctly resolved by tracking and scheduling a routine fix, not paging anyone.
- Useful example for an agent's triage logic: a MINOR severity alarm plus "within
  tolerance" language in the alarm description is a signal to draft a low-priority
  ticket rather than an urgent one.
