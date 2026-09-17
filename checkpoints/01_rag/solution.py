"""Checkpoint 1 — one working answer. Try it yourself before reading this.

Run this file to write the document, then run check.py.

What makes it rank: the distinguishing MECHANISM (jitter, packet delay
variation, transport, link) sits in the same paragraph as the shared symptoms
(slow speeds, evening, stalling video) and explicitly states what is NORMAL
(PRB, user count) — which is exactly what the query says. Symptom words alone
would tie with incident_001; the mechanism words break the tie.
"""

import os

DOC = """# Incident Postmortem: Evening Slow Speeds Caused by Backhaul Jitter

**Site affected:** SITE-031 (CELL-031A)
**Date:** 2026-07-22
**Category:** Transport / Backhaul

## Summary
Customers near SITE-031 reported slow speeds and stalling video during evening hours,
with the same customer-facing symptoms as a congestion event. Crucially, PRB utilization
looked normal and active user count stayed within planned capacity for the cell — so the
radio side was not the constraint. The degradation was caused by jitter and packet delay
variation on the backhaul link, not by air-interface congestion.

## Root Cause
A microwave backhaul link serving the site developed intermittent packet delay variation
during evening hours, correlating with thermal conditions on the hop. Jitter exceeded the
transport budget for latency-sensitive traffic, causing TCP throughput collapse and video
rebuffering while radio KPIs remained nominal.

## Resolution
Transport engineering adjusted the modulation profile on the affected microwave hop and
scheduled a hardware inspection. Throughput recovered immediately and evening complaints
stopped within 24 hours.

## Prevention
Where customer complaints describe congestion symptoms but PRB utilization and active user
count are normal, check transport before RF. Normal radio KPIs alongside poor customer
experience is the signature of a transport-layer fault, not a capacity problem.
"""

if __name__ == "__main__":
    # Writes into THIS checkpoint's own kb/ folder, not the shared corpus.
    # It used to write into data/knowledge_base/, where every later module and
    # all three eval cases retrieve. A fifth document changes the rankings --
    # and EVAL-03 now asserts which document ranks FIRST, so a student who ran
    # this checkpoint and then re-ran the eval could watch a passing case go red
    # for a reason that had nothing to do with the code they were grading.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "kb", "incident_004_backhaul_jitter.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(DOC)
    print(f"Wrote {os.path.basename(path)} — now run: python check.py")
