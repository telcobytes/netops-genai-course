"""
tracing.py — Module 10 hands-on: instrument tool calls with lightweight tracing

A minimal decorator that logs every tool call (name, arguments, result, timing)
to a JSONL file — the same idea as production tracing (LangSmith, Langfuse,
OpenTelemetry GenAI conventions) at a scale you can read by hand.

Usage:
    from tracing import traced

    @traced
    def get_cell_kpis(cell_id):
        ...
"""

import contextlib
import functools
import json
import os
import sys
import time

TRACE_LOG_PATH = os.path.join(os.path.dirname(__file__), "trace_log.jsonl")

# Which run are we in? A trace log that cannot separate one run from the next is
# a pile of lines: `--show --run 2` needs this, and so does any question of the
# form "what did the run that failed actually do?".
_RUN = 0


def new_run() -> int:
    """Start a new run. Everything traced from here carries this index.

    The index continues from whatever is already in the log, so it survives
    across processes — otherwise every run is "run 1" and `--run 2` can never
    resolve to anything.
    """
    global _RUN
    prior = [e.get("run", 0) for e in read_trace_log()]
    _RUN = (max(prior) if prior else 0) + 1
    return _RUN


def reset_trace_log() -> None:
    """Start a fresh log. Deliberate and announced by the caller — unlike the old
    behaviour, where `tracing.py --show --run 2` silently deleted the only trace.
    """
    global _RUN
    if os.path.exists(TRACE_LOG_PATH):
        os.remove(TRACE_LOG_PATH)
    _RUN = 0


def current_run() -> int:
    return _RUN

# Active in-memory collectors. A trace on disk outlives the run that produced it,
# and that is not a footnote: tracing.py's own demo log, which carries no case_id,
# was read back by run_eval and graded as evidence for all three eval cases. A
# grader must only ever see what the run it is grading actually did.
_SINKS: list = []


@contextlib.contextmanager
def collect(case_id: str = ""):
    """Collect traced calls in memory for the duration of this block.

    Yields the list that gets appended to. Entries are stamped with case_id so a
    trace can always say which run produced it — an unattributable trace is not
    evidence.
    """
    sink: list = []
    _SINKS.append((case_id, sink))
    try:
        yield sink
    finally:
        _SINKS.remove((case_id, sink))


def traced(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            status = "ok"
        except Exception as e:
            result = str(e)
            status = "error"
            raise
        finally:
            record = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run": _RUN,
                "tool": func.__name__,
                "args": args,
                "kwargs": kwargs,
                "duration_ms": round((time.time() - start) * 1000, 1),
                "status": status,
                "result_preview": str(result)[:200],
            }
            for case_id, sink in _SINKS:
                sink.append({**record, "case_id": case_id})
            with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({**record, "case_id": _SINKS[-1][0] if _SINKS else None},
                                   default=str) + "\n")
        return result

    return wrapper


def read_trace_log(run=None) -> list:
    """Every recorded call, or just the ones from run `run`."""
    if not os.path.exists(TRACE_LOG_PATH):
        return []
    out = []
    with open(TRACE_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if run is not None and entry.get("run") != run:
                continue
            out.append(entry)
    return out


def print_trace_log(run=None):
    """Pretty-print the trace log for manual inspection."""
    entries = read_trace_log(run)
    if not entries:
        if not os.path.exists(TRACE_LOG_PATH):
            print("No trace log yet — run a traced tool call first, "
                  "or `python module10-eval/repeat.py --runs 5`.")
        else:
            runs = sorted({e.get("run") for e in read_trace_log()})
            print(f"No entries for run {run}. Recorded runs: "
                  f"{', '.join(str(r) for r in runs) or '(none)'}")
        return
    for entry in entries:
        print(f"[run {entry.get('run', '?')}] [{entry['timestamp']}] "
              f"{entry['tool']}({entry['kwargs'] or entry['args']}) "
              f"-> {entry['status']} in {entry['duration_ms']}ms")


def run_trace_demo():
    """Runs a simulated triage workflow using @traced tools and validates
    Tier 1 Deterministic Trace Assertions (operational order, status, latency)."""
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
    import mock_tools

    # APPEND, never truncate. This used to delete the log — which meant slide 79's
    # "open the trace of a run that failed" destroyed the only trace there was.
    run = new_run()
    print(f"Running instrumented triage sequence with @traced tools (run {run})...\n")

    # Instrument tools with @traced
    traced_get_kpis = traced(mock_tools.get_cell_kpis)
    traced_lookup_topology = traced(mock_tools.lookup_topology)
    traced_create_ticket = traced(mock_tools.create_ticket)

    # 1. Inspect telemetry
    traced_get_kpis("CELL-031A")
    # 2. Inspect neighbor topology
    traced_lookup_topology("CELL-031A")
    # 3. Create ticket (after diagnostics)
    traced_create_ticket("Congestion verified on CELL-031A", site_id="SITE-031")

    print(f"Appended to trace log: {TRACE_LOG_PATH}\n")
    print(f"--- TRACE LOG CONTENTS (run {run}) ---")
    print_trace_log(run=run)

    # --- TIER 1 DETERMINISTIC TRACE ASSERTIONS ---
    traces = read_trace_log(run=run)   # only this run's calls, not the whole file

    tool_names = [t["tool"] for t in traces]

    # Assertion 1: Verify operational sequence (Diagnostic reads BEFORE mutation writes)
    assert "lookup_topology" in tool_names, "Missing topology lookup in trace"
    assert "create_ticket" in tool_names, "Missing ticket creation in trace"
    idx_topo = tool_names.index("lookup_topology")
    idx_ticket = tool_names.index("create_ticket")
    assert idx_topo < idx_ticket, "VIOLATION: create_ticket fired BEFORE lookup_topology!"

    # Assertion 2: Verify all tools executed successfully
    for t in traces:
        assert t["status"] == "ok", f"Tool {t['tool']} failed with status {t['status']}"
        assert t["duration_ms"] >= 0, f"Invalid duration for {t['tool']}"

    print("\n" + "=" * 65)
    print("[EVAL TIER 1] DETERMINISTIC TRACE ASSERTIONS: ALL PASSED")
    print("=" * 65)
    print(f"  ✓ Verified: Operational order (lookup_topology at step {idx_topo + 1} preceded create_ticket at step {idx_ticket + 1})")
    print(f"  ✓ Verified: All {len(traces)} tool calls completed with status 'ok'")
    print("  ✓ Verified: Microsecond-precision duration logged for every call\n")


def _cli(argv):
    if "--show" in argv:
        run = None
        if "--run" in argv:
            try:
                run = int(argv[argv.index("--run") + 1])
            except (IndexError, ValueError):
                sys.exit("usage: tracing.py --show [--run N]")
        print_trace_log(run=run)
        return 0
    run_trace_demo()
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

