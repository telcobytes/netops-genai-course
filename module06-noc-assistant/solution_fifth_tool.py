#!/usr/bin/env python3
"""
solution_fifth_tool.py — the worked answer to Module 6's exercise 3.

    python solution_fifth_tool.py            # offline: the wiring, no key needed
    python solution_fifth_tool.py --live     # ask the agent, once (~10 calls)

THE EXERCISE
------------
Add a fifth tool and find out whether the model REACHES for it. The wiring is ten
lines and is not the lesson. The lesson is that a tool the model never picks is a
tool you are paying to declare — and the only thing advertising it is one sentence
of `description`.

The tool is get_recent_changes(site_id): change and maintenance records for a
site. It is what a NOC correlates against first — before blaming a cell, ask
whether anybody touched it — and nothing in the system prompt mentions it.

WHAT HAPPENED WHEN THIS WAS RUN (18 Sep 2026, gemini-3.6-flash)
---------------------------------------------------------------
The model called get_recent_changes unprompted, in its FIRST batch of tool calls,
before it looked at a single KPI. It then cited CHG-2041 in its answer and noted
that the retune "added no capacity" — i.e. it used the record to RULE OUT a cause,
which is what a change check is for. That run also asked for three tools at once,
three times; noc_assistant prints "[3 tool calls in one turn]" when that happens.

Your run may differ. Agent runs vary — Module 5 measured the same question taking
four steps once and five the next time. Run it twice before you conclude anything.

One more measurement, because it is the opposite of what people expect: rewriting
this tool's description did NOT change whether the model picked it. Rich wording
and a bare "Returns change records for a site." both produced a call at position
three, twice each. Only stripping the NAME as well — renaming it query_records
with a bare description — moved it, and then only in one run of two, to position
nine. On a small, well-named toolset the name and the system prompt carry the
decision. Descriptions earn their keep when tools are confusable.

WHAT TO WATCH
-------------
1. Does it call the tool at all, given nothing asked it to?
2. Does it read the STATUS? SITE-022's only record is an RRU replacement that is
   SCHEDULED for 2026-09-16. It has not happened. An agent that offers it as a
   cause has explained today's incident with next week's work.
3. Does a clean result change anything? SITE-031's last change added no capacity,
   so "nothing recent explains this" is itself evidence — and the answer above
   used it that way.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "data"))
sys.path.insert(0, HERE)

import noc_assistant as A                    # noqa: E402
from mock_tools import get_recent_changes    # noqa: E402

# ---------------------------------------------------------------------------
# The wiring: one schema the model reads, one dispatch entry your code executes.
# ---------------------------------------------------------------------------

CHANGES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_recent_changes",
        # This sentence is the entire pitch, and it is prompt engineering wearing
        # a schema's clothes. Say what the tool ANSWERS, not what it queries:
        # "has anything changed here recently" is a question the model recognises
        # as relevant to a fault; "returns rows from changes.csv" is not.
        "description": (
            "Recent change and maintenance records for a site: parameter changes, "
            "software upgrades and planned works, newest first, each with a status "
            "of COMPLETED or SCHEDULED. Use it to check whether a recent change "
            "explains what you are seeing before attributing a cause."
        ),
        "parameters": {
            "type": "object",
            # Note what is NOT here: no severity, no bounds, no enum. This tool
            # reads. create_ticket writes, and that is why only create_ticket gets
            # a schema check, a policy check and a human. Scope the ceremony to
            # the blast radius.
            "properties": {"site_id": {"type": "string"}},
            "required": ["site_id"],
        },
    },
}


def install():
    """Add the tool to the assistant's schemas and dispatch table.

    This wraps noc_assistant rather than editing it, so the shipped lab stays as
    students found it and both files keep working. In your own code you would
    simply add the schema to TOOL_SCHEMAS and the function to the dispatch dict
    in _dispatch_tool — the same two places, permanently.
    """
    if not any(t["function"]["name"] == "get_recent_changes" for t in A.TOOL_SCHEMAS):
        A.TOOL_SCHEMAS.append(CHANGES_SCHEMA)

    original_dispatch = A._dispatch_tool

    def dispatch(name, args):
        if name == "get_recent_changes":
            try:
                return get_recent_changes(**args)
            except Exception as err:       # a bad site id, usually
                # Returned, not raised: an error the model can read is an error it
                # can correct. Raising here would end the run instead.
                return {"error": f"Error executing get_recent_changes: {err}"}
        return original_dispatch(name, args)

    A._dispatch_tool = dispatch


def offline_demo():
    """Everything that does not need a model: the wiring, and what it returns."""
    install()
    names = [t["function"]["name"] for t in A.TOOL_SCHEMAS]
    print("Tools the model can now see:")
    for n in names:
        print(f"   {n}{'   <- the new one' if n == 'get_recent_changes' else ''}")

    print("\nWhat the model reads about it — this is the whole advertisement:")
    print("  ", CHANGES_SCHEMA["function"]["description"])

    print("\nDispatch works (your code executes it, not the model):")
    for site in ("SITE-031", "SITE-022"):
        rows = A._dispatch_tool("get_recent_changes", {"site_id": site})
        print(f"   {site}:")
        for r in rows:
            print(f"     {r['change_id']}  {r['status']:<9} {r['performed_at'][:10]}  {r['description'][:58]}")

    print("\nA bad argument comes back as an observation, not an exception:")
    print("  ", json.dumps(A._dispatch_tool("get_recent_changes", {"site_id": "SITE-999"}))[:120])

    print("""
Read SITE-022 again: the RRU replacement is SCHEDULED for 16 Sep. It has not
happened, and an agent that offers it as today's cause has explained an incident
with next week's work. Status is not decoration.

Now the part this cannot show you offline: whether the model picks the tool up
when nothing tells it to. That needs a real run —

    python solution_fifth_tool.py --live
""")


def live_demo():
    install()
    question = ("Why is site SITE-031 underperforming right now, and has anything "
                "changed there recently?")
    print(f"Question: {question}\n")
    print(A.run_noc_assistant(question))
    print("""
--- Did it reach for the new tool? Scroll up for [tool call] get_recent_changes.

If it did not, run it again before concluding anything: agent runs vary, and this
tool was called at position three in four measured runs. And do not reach for the
description as the fix — rewording it changed nothing in those runs. The name and
the system prompt are what put a tool in play.""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="ask the agent for real (needs GEMINI_API_KEY, ~10 calls)")
    live_demo() if ap.parse_args().live else offline_demo()
