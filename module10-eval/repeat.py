#!/usr/bin/env python3
"""
repeat.py — Module 10 hands-on: the same question, several times.

    python module10-eval/repeat.py --case EVAL-01 --runs 5
    python module10-eval/repeat.py --runs 5 --prompt naive
    python module10-eval/repeat.py --runs 5 --mode chained

An agent does not give you the same answer twice, and — more to the point — it
does not take the same PATH twice. The conclusion is often stable while the
process underneath it is not, and nothing in the answer text tells you which run
you got. The trace does, which is why you record it before you need it.

What this measures
------------------
NEIGHBOUR-BEFORE-BLAME: before proposing a ticket, did the agent actually READ a
neighbour — its KPIs or its alarms?

Three states, never two — a run that proposed no ticket has neither complied nor
violated, and scoring that as a pass flatters an agent that did nothing.

This used to assert `lookup_topology` before `create_ticket`, which sounds like
the same thing and is not. An agent asked about SITE-031 looks up SITE-031's
topology as a matter of course. Measured on 16 Sep 2026, the naive prompt scored
100% on that proxy across five runs while reading ZERO neighbours. Assert the
rule; a proxy that a failing agent satisfies is not a measurement.

The three rungs, and why the third is different
-----------------------------------------------
  --prompt naive     the rule is not in the system prompt at all
  --prompt tuned     the rule is in the system prompt (what the course ships)
  --mode chained     the rule is not a request: lookup_topology is step one of a
                     hand-rolled chain, in Python, and cannot be skipped

The first two buy a better number. The third buys a guarantee, and the assertion
that was catching failures changes job — from testing the model to testing that
nobody refactored the step away.

DO NOT quote a compliance rate you have not measured on your own key. The numbers
move with the model.

Every run is written to trace_log.jsonl with a run index, so:

    python module10-eval/tracing.py --show --run 2
"""

import argparse
import contextlib
import hashlib
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "data"))
sys.path.append(os.path.join(HERE, "..", "module06-noc-assistant"))

import mock_tools                                        # noqa: E402
import tracing                                           # noqa: E402
from llm_client import call_llm                          # noqa: E402

BOLD, DIM, GRN, RED, YEL, CYN, OFF = (
    "\033[1m", "\033[2m", "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m")

SHORT = {"get_cell_kpis": "kpis", "get_active_alarms": "alarms",
         "lookup_topology": "topology", "create_ticket": "ticket"}

# An honest ten-minute first draft: it never mentions neighbour cells. That is the
# point — the rule lives in the instructor's head rather than in the system.
NAIVE_PROMPT = """You are a NOC assistant for NetOps Co. Answer the user's
question about network issues using the tools available to you. If you find a
problem, open a ticket describing it.
"""

CASES = {
    "EVAL-01": ("CELL-031A",
                "Why is site SITE-031 underperforming right now, and should we open a ticket?"),
    "EVAL-03": ("CELL-031A",
                "A trouble ticket reports slow data speeds near SITE-031 during evening peak "
                "hours for the past three days, with no specific alarm cited yet. What is "
                "going on and what should we do?"),
}


def instrument():
    """Wrap the four tools with @traced, so every call this harness makes lands in
    trace_log.jsonl under its run index. Without this the compliance number would
    exist and the trace behind it would not — and `tracing.py --show --run 2`,
    which slide 79 sends you to, would have nothing to show."""
    import noc_assistant
    for name in ("get_cell_kpis", "get_active_alarms", "lookup_topology", "create_ticket"):
        for module in (noc_assistant, mock_tools):
            fn = getattr(module, name, None)
            if fn is not None and not hasattr(fn, "__wrapped__"):
                setattr(module, name, tracing.traced(fn))


# --------------------------------------------------------------------- verdict

def neighbour_ids(cell_id):
    """The cells this one hands traffic to, plus their sites — the things an agent
    has to have READ before it is entitled to blame this cell."""
    topo = mock_tools.lookup_topology(cell_id) or {}
    ids = set()
    for cell in topo.get("neighbors", []):
        ids.add(cell)
        nb = mock_tools.lookup_topology(cell) or {}
        if nb.get("site_id"):
            ids.add(nb["site_id"])
    return ids


def verdict(calls, neighbours):
    """True / False / None. None matters: an agent that never proposes a ticket
    has neither complied nor violated, and collapsing that into a pass would
    flatter it."""
    names = [c["tool"] for c in calls]
    if "create_ticket" not in names:
        return None
    idx = names.index("create_ticket")
    return any(str(v) in neighbours
               for c in calls[:idx]
               for v in (c.get("args") or {}).values())


def label(call):
    """`topology(014A)` — enough argument to see where two paths diverge."""
    name = SHORT.get(call["tool"], call["tool"])
    args = call.get("args") or {}
    hint = args.get("cell_id") or args.get("node_id") or args.get("site_id") or ""
    hint = str(hint).replace("CELL-", "").replace("SITE-", "SITE-")
    return f"{name}({hint})" if hint else f"{name}()"


# --------------------------------------------------------------------- modes

def run_agent(question, prompt_style):
    """The Module 6 agent, free to choose its own path."""
    import noc_assistant
    original_prompt = noc_assistant.SYSTEM_PROMPT
    if prompt_style == "naive":
        noc_assistant.SYSTEM_PROMPT = NAIVE_PROMPT

    calls = []
    original_dispatch = noc_assistant._dispatch_tool

    def _dispatch(name, args):
        calls.append({"tool": name, "args": args})
        return original_dispatch(name, args)

    noc_assistant._dispatch_tool = _dispatch
    try:
        with contextlib.redirect_stdout(io.StringIO()):   # mute the agent's own prints
            answer = noc_assistant.run_noc_assistant(question)
        return calls, answer or ""
    finally:
        noc_assistant._dispatch_tool = original_dispatch
        noc_assistant.SYSTEM_PROMPT = original_prompt


def run_chained(cell_id, question):
    """The same job as a hand-rolled chain.

    The chain has to encode the RULE, not a step that happens to satisfy a proxy
    for it. A first version of this called lookup_topology and went straight to
    drafting — 100% on the old assertion, zero neighbours read. The neighbour
    sweep below is the rule; the model still writes the prose, it just no longer
    decides whether the check happens.
    """
    calls = []

    def step(name, fn, args, **kw):
        calls.append({"tool": name, "args": args})
        return fn(**kw)

    topo = step("lookup_topology", mock_tools.lookup_topology,
                {"node_id": cell_id}, node_id=cell_id) or {}
    site = topo.get("site_id", "")
    kpis = step("get_cell_kpis", mock_tools.get_cell_kpis,
                {"cell_id": cell_id}, cell_id=cell_id)
    alarms = step("get_active_alarms", mock_tools.get_active_alarms,
                  {"site_id": site}, site_id=site or None)

    # Step four, and the one the whole rule is about: read every neighbour before
    # concluding anything about this cell.
    neighbours = {}
    for cell in topo.get("neighbors", []):
        nb_topo = step("lookup_topology", mock_tools.lookup_topology,
                       {"node_id": cell}, node_id=cell) or {}
        nb_site = nb_topo.get("site_id")
        neighbours[cell] = {
            "kpis": step("get_cell_kpis", mock_tools.get_cell_kpis,
                         {"cell_id": cell}, cell_id=cell),
            "alarms": step("get_active_alarms", mock_tools.get_active_alarms,
                           {"site_id": nb_site}, site_id=nb_site) if nb_site else [],
        }

    answer = call_llm([{"role": "user", "content":
                        f"{question}\n\nTOPOLOGY: {topo}\nKPIs: {kpis}\nALARMS: {alarms}\n"
                        f"NEIGHBOURS: {neighbours}\n\n"
                        "Draft an RCA as Impact / Likely cause / Recommended action."}])

    rank = {"MINOR": 1, "MAJOR": 2, "CRITICAL": 3}
    worst = "MINOR"
    for a in alarms:
        if rank.get(str(a.get("severity", "")).upper(), 0) > rank[worst]:
            worst = str(a["severity"]).upper()

    # Build the ticket summary in CODE from the evidence. Truncating the model's
    # markdown to 300 characters produced ticket summaries that opened with
    # "**a high-priority ticket should be opened immediately**" — a chain that
    # constructs its own fields is the point of having a chain.
    crossed = [t["metric"] for t in (kpis.get("thresholds_crossed") or [])]
    args = {
        "summary": (f"{cell_id}: {len(crossed)} threshold(s) crossed "
                    f"({', '.join(crossed) or 'none'}); "
                    f"{len(neighbours)} neighbour(s) checked, "
                    f"{sum(1 for n in neighbours.values() if n['alarms'])} alarming"),
        "site_id": site, "severity": worst, "category": "Congestion",
    }
    calls.append({"tool": "create_ticket", "args": args})
    mock_tools.create_ticket(**args)
    return calls, answer or ""


# --------------------------------------------------------------------- report

def fork_point(paths):
    """How many leading calls every run shared before they diverged."""
    if len(paths) < 2:
        return len(paths[0]) if paths else 0
    n = 0
    for step_calls in zip(*paths):
        if len(set(step_calls)) != 1:
            break
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=sorted(CASES), default="EVAL-01")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--prompt", choices=["naive", "tuned"], default="tuned")
    ap.add_argument("--mode", choices=["agent", "chained"], default="agent")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between runs, to stay under free-tier RPM")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("[error] GEMINI_API_KEY is not set.")
    os.environ["AUTO_APPROVE"] = "1"   # the human gate is Module 6's lesson, not this one

    cell_id, question = CASES[args.case]
    neighbours = neighbour_ids(cell_id)
    instrument()
    tracing.reset_trace_log()
    print(f"\n{BOLD}{args.case}  ·  mode {args.mode}  ·  prompt {args.prompt}  ·  "
          f"{args.runs} runs{OFF}")
    print(f"{DIM}fresh trace log — each run is recorded under its own index{OFF}")
    print(f"question: {question}")
    print(f"{DIM}a run complies if it reads one of {', '.join(sorted(neighbours))} "
          f"before proposing a ticket{OFF}\n")

    results = []
    for i in range(1, args.runs + 1):
        run_index = tracing.new_run()
        started = time.time()
        try:
            if args.mode == "chained":
                calls, answer = run_chained(cell_id, question)
            else:
                calls, answer = run_agent(question, args.prompt)
            error = None
        except Exception as exc:
            calls, answer, error = [], "", f"{type(exc).__name__}: {exc}"
        elapsed = time.time() - started

        v = verdict(calls, neighbours)
        mark = {True: f"{GRN}OK {OFF}", False: f"{RED}BAD{OFF}", None: f"{YEL}—  {OFF}"}[v]
        note = {True: "", False: "  blamed the cell without reading a neighbour",
                None: "  no ticket proposed"}[v]
        path = [label(c) for c in calls]
        if error:
            mark, note = f"{RED}ERR{OFF}", "  " + error.split("\n")[0][:90]
        print(f"  run {run_index:>2}  {mark}  {len(calls):>2} calls  "
              f"{' → '.join(path) or '(no tools)'}{note}  {DIM}[{elapsed:.1f}s]{OFF}")

        results.append({"run": run_index, "path": path, "verdict": v, "error": error,
                        "sha": hashlib.sha256((answer or "").encode()).hexdigest()[:8]})
        if len(results) >= 3 and all(r["error"] for r in results[-3:]):
            print(f"\n  {RED}[aborting: three consecutive failures]{OFF}\n")
            break
        if i < args.runs:
            time.sleep(args.sleep)

    clean = [r for r in results if not r["error"]]
    ok = sum(1 for r in clean if r["verdict"] is True)
    bad = sum(1 for r in clean if r["verdict"] is False)
    na = sum(1 for r in clean if r["verdict"] is None)
    graded = ok + bad
    paths = [r["path"] for r in clean]

    print(f"\n{BOLD}{'=' * 72}{OFF}")
    if graded:
        print(f"  {BOLD}NEIGHBOUR-BEFORE-BLAME COMPLIANCE:  {ok}/{graded} graded runs "
              f"({100 * ok // graded}%){OFF}")
    else:
        print("  NEIGHBOUR-BEFORE-BLAME COMPLIANCE:  no gradable run — no ticket was proposed")
    print(f"  no ticket proposed: {na}    errors: {len(results) - len(clean)}")
    print(f"  distinct tool trajectories: {len({tuple(p) for p in paths})} / {len(clean)}")
    print(f"  distinct answer texts:      {len({r['sha'] for r in clean})} / {len(clean)}")
    if len(paths) > 1:
        shared = fork_point(paths)
        print(f"  {CYN}identical for the first {shared} call(s), then the paths fork{OFF}")
    print(f"{BOLD}{'=' * 72}{OFF}")

    if args.mode == "chained":
        print(f"""
  {BOLD}This rate is not a measurement of the model.{OFF} lookup_topology is step one
  of a chain, in Python. It cannot be skipped, forgotten, or talked out of, so
  the number is a property of the code. The assertion that was catching failures
  can now never fail — it changed job, from testing the model to testing that
  nobody refactored the step away.
""")
    else:
        print(f"""
  {BOLD}Write down the number before you change anything.{OFF} Then run the other two
  rungs and compare:

      python module10-eval/repeat.py --runs {args.runs} --prompt naive
      python module10-eval/repeat.py --runs {args.runs} --mode chained

  And open a run that interests you — the whole path, with arguments and timings:

      python module10-eval/tracing.py --show --run 2
""")


if __name__ == "__main__":
    main()
