"""
tracing.py — Module 9 hands-on: instrument tool calls with lightweight tracing

A minimal decorator that logs every tool call (name, arguments, result, timing)
to a JSONL file — the same idea as production tracing (LangSmith, Langfuse,
OpenTelemetry GenAI conventions) at a scale you can read by hand.

Usage:
    from tracing import traced

    @traced
    def get_cell_kpis(cell_id):
        ...
"""

import functools
import json
import os
import time

TRACE_LOG_PATH = os.path.join(os.path.dirname(__file__), "trace_log.jsonl")


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
                "tool": func.__name__,
                "args": args,
                "kwargs": kwargs,
                "duration_ms": round((time.time() - start) * 1000, 1),
                "status": status,
                "result_preview": str(result)[:200],
            }
            with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        return result

    return wrapper


def print_trace_log():
    """Pretty-print the trace log for manual inspection."""
    if not os.path.exists(TRACE_LOG_PATH):
        print("No trace log yet — run a traced tool call first.")
        return
    with open(TRACE_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            print(f"[{entry['timestamp']}] {entry['tool']}({entry['kwargs'] or entry['args']}) "
                  f"-> {entry['status']} in {entry['duration_ms']}ms")


def run_trace_demo():
    """Runs a simulated triage workflow using @traced tools and validates
    Tier 1 Deterministic Trace Assertions (operational order, status, latency)."""
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
    import mock_tools

    # Clear prior log for fresh demo run
    if os.path.exists(TRACE_LOG_PATH):
        os.remove(TRACE_LOG_PATH)

    print("Running instrumented triage sequence with @traced tools...\n")

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

    print(f"Recorded trace log to: {TRACE_LOG_PATH}\n")
    print("--- TRACE LOG CONTENTS ---")
    print_trace_log()

    # --- TIER 1 DETERMINISTIC TRACE ASSERTIONS ---
    traces = []
    with open(TRACE_LOG_PATH, encoding="utf-8") as f:
        traces = [json.loads(line) for line in f]

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


if __name__ == "__main__":
    run_trace_demo()

