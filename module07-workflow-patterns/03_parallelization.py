"""
PATTERN 3 — PARALLELIZATION

Fan the same incident out to several independent analyses at once, then have a
synthesizer combine their findings. Nothing waits on anything it doesn't need.

Telecom shape: during an incident you want the KPI picture, the alarm picture
and the topology picture. None of those three depends on the others — so
checking them one after another just makes the operator wait three times.

When to reach for it:
  The sub-tasks are genuinely independent AND latency matters. During an alarm
  storm both are true, which is why this pattern has an obvious operational
  justification here that it doesn't have in a generic chatbot.

When NOT to:
  If analysis B needs analysis A's answer, this is a chain, not a fan-out.
  Forcing it parallel just means B works from worse information.

Run:  python 03_parallelization.py --mock     # canned answers: the wiring, free, same every time
      python 03_parallelization.py            # the same wiring with a live model in it

      Without GEMINI_API_KEY you get --mock either way, and the banner says so.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from _common import ask, banner, step, CYAN, GREEN, BOLD, RESET

sys.path.append("../data")
from mock_tools import get_active_alarms, get_cell_kpis, lookup_topology  # noqa: E402

CELL = "CELL-031A"
SITE = "SITE-031"


def analyse_kpis() -> str:
    k = get_cell_kpis(CELL)
    crossed = "; ".join(f"{c['metric']}={c['value']}" for c in k["thresholds_crossed"])
    return ask(
        f"In one sentence, what do these KPI movements mean?\n{json.dumps(k['delta'])}\nCrossed: {crossed}",
        mock=f"PRB and drop rate rose sharply while throughput halved — classic saturation. Crossed: {crossed}")


def analyse_alarms() -> str:
    alarms = get_active_alarms(SITE)
    types = ", ".join(a["alarm_type"] for a in alarms)
    return ask(
        f"In one sentence, what story do these alarms tell?\n{json.dumps(alarms)}",
        mock=f"Four alarms on {SITE}, escalating from utilization warning to congestion critical ({types}).")


def analyse_topology() -> str:
    topo = lookup_topology(CELL) or {}
    neighbours = topo.get("neighbors", [])
    neighbour_state = {n: get_cell_kpis(n).get("thresholds_crossed", []) for n in neighbours}
    healthy = [n for n, c in neighbour_state.items() if not c]
    return ask(
        f"In one sentence, are the neighbours healthy?\n{json.dumps({k: len(v) for k, v in neighbour_state.items()})}",
        mock=f"Neighbours {', '.join(neighbours)} are within thresholds ({len(healthy)}/{len(neighbours)} healthy) — "
             "no evidence of overflow from a failing neighbour.")


WORKERS = {"KPI feed": analyse_kpis, "Alarm log": analyse_alarms, "Topology": analyse_topology}


def synthesize(findings: dict) -> str:
    joined = "\n".join(f"- {name}: {text}" for name, text in findings.items())
    return ask(
        f"""Three independent analyses of the same incident. Combine them into one
conclusion in 2 sentences. Say explicitly if they agree or conflict.

{joined}""",
        mock=("All three agree: CELL-031A is saturating under its own load, not absorbing overflow "
              "from a failing neighbour. The cause is local capacity, so the fix is a capacity or "
              "handover-bias change rather than a neighbour repair."))


def run() -> None:
    banner("PATTERN 3 — PARALLELIZATION",
           "three independent analyses at once, then one synthesizer")

    step(1, "Fan out", f"{len(WORKERS)} analyses dispatched concurrently")
    started = time.time()
    with ThreadPoolExecutor(max_workers=len(WORKERS)) as pool:
        futures = {name: pool.submit(fn) for name, fn in WORKERS.items()}
        findings = {name: f.result() for name, f in futures.items()}
    parallel_elapsed = time.time() - started

    for name, text in findings.items():
        print(f"    {CYAN}{name:10}{RESET} {text}")

    step(2, "Synthesize")
    print("    " + synthesize(findings))

    print(f"\n{BOLD}Wall clock:{RESET} {parallel_elapsed:.2f}s for {len(WORKERS)} analyses.")
    print(f"{GREEN}Run sequentially, the operator waits for the slowest chain instead of the "
          f"slowest single analysis.{RESET} With live model calls that difference is seconds per "
          "incident — and during a storm, seconds times hundreds.")


if __name__ == "__main__":
    run()
