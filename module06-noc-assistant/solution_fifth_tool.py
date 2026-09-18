#!/usr/bin/env python3
"""
solution_fifth_tool.py — Module 6, exercise 3: add a tool and see whether the
model reaches for it.

    python solution_fifth_tool.py

The exercise asks you to add a fifth tool to the assistant. The interesting part
is not the wiring — that is ten lines below — it is whether the model USES it
without being told to. A tool the model never picks is a tool you are paying to
declare.

The tool is get_recent_changes(site_id): change and maintenance records for a
site. It is what a NOC engineer correlates against first — before blaming a cell,
ask whether anybody touched it — and nothing in the system prompt mentions it.

WHAT TO WATCH
-------------
1. Does the model call it at all? Its only advertisement is the `description`
   below. That one sentence is prompt surface: it is the whole of what the model
   knows about the tool when it decides.
2. Does it read the STATUS? SITE-022's only record is an RRU replacement that is
   SCHEDULED for 2026-09-16 — it has not happened. An agent that reports it as a
   cause has explained today's incident with next week's work.
3. Does it change the conclusion? For SITE-031 the answer should be "nothing
   recent explains this": the last change was a parameter retune on 3 Sep that
   added no capacity. A change check that comes back clean is evidence too.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "data"))
sys.path.insert(0, HERE)

import noc_assistant as A                    # noqa: E402
from mock_tools import get_recent_changes    # noqa: E402

# ---- the wiring: a schema the model reads, and a dispatch entry we execute ----

CHANGES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_recent_changes",
        # This sentence is the entire pitch. Say what the tool answers, not what
        # it queries: "has anything changed here recently" is a question the model
        # recognises as relevant; "returns rows from changes.csv" is not.
        "description": (
            "Recent change and maintenance records for a site: parameter changes, "
            "software upgrades and planned works, newest first, each with a status "
            "of COMPLETED or SCHEDULED. Use it to check whether a recent change "
            "explains what you are seeing before attributing a cause."
        ),
        "parameters": {
            "type": "object",
            "properties": {"site_id": {"type": "string"}},
            "required": ["site_id"],
        },
    },
}


def install():
    """Add the tool to the assistant's schemas and to its dispatch table.

    Read-only, so it needs no approval gate and no policy check — the asymmetry
    between this and create_ticket is the read/write split from the README, in
    the smallest form it takes.
    """
    if not any(t["function"]["name"] == "get_recent_changes" for t in A.TOOL_SCHEMAS):
        A.TOOL_SCHEMAS.append(CHANGES_SCHEMA)

    original_dispatch = A._dispatch_tool

    def dispatch(name, args):
        if name == "get_recent_changes":
            try:
                return get_recent_changes(**args)
            except Exception as err:                    # a bad site id, usually
                return {"error": f"Error executing get_recent_changes: {err}"}
        return original_dispatch(name, args)

    A._dispatch_tool = dispatch


if __name__ == "__main__":
    install()
    question = ("Why is site SITE-031 underperforming right now, and has anything "
                "changed there recently?")
    print(f"Question: {question}\n")
    print(A.run_noc_assistant(question))
    print("\n--- Did it reach for the new tool? Scroll up: look for "
          "[tool call] get_recent_changes.\n"
          "    If it did not, try deleting the second sentence of the description "
          "and running again.\n"
          "    The tool did not change. What the model knew about it did.")
