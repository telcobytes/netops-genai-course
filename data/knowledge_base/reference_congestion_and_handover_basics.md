# Course Reference Note: Congestion, Admission Control, and Handover (Simplified)

*This is an original, simplified teaching summary written for this course — not a
reproduction of any 3GPP or vendor specification. Use it as illustrative "spec-style"
grounding content for the RAG lab, and swap in real (properly licensed) internal
documentation when you build this for actual production use.*

## Admission control (simplified)
When a device tries to connect to a cell, the network checks whether the cell has
enough available capacity (radio resources) to admit the new connection. If the cell
is already heavily loaded, the network may reject or delay the new connection, or
hand the device off to a neighboring cell with more available capacity instead.

## Why PRB utilization matters
PRB (Physical Resource Block) utilization is a rough measure of how much of a cell's
available radio capacity is currently in use. Sustained utilization above roughly
70–80% is commonly treated as a warning sign that the cell is approaching its limit,
after which new connection attempts and handovers into the cell become more likely
to fail or degrade.

## Common triggers for a sudden congestion pattern
1. **A genuine surge in local demand** — an event, a holiday, a marketing promotion.
2. **Loss of a neighboring cell** — traffic that would normally spread across two
   cells concentrates onto the surviving one.
3. **A misconfiguration** — e.g., handover parameters biased incorrectly, causing a
   cell to accept more traffic than intended.

## Why root cause matters before acting
The correct response differs a lot depending on which of the three triggers above is
in play: a one-off event may need only a temporary handover-bias change, a neighbor
outage typically resolves itself once the neighbor is fixed, and a misconfiguration
needs a parameter correction. This is why an agent should check neighbor-cell status
and recent configuration changes *before* recommending or taking any corrective
action on the affected cell itself.
