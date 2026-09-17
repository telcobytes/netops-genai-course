#!/usr/bin/env python3
"""
lab_query_construction.py — Module 4 hands-on: step 3, constructing the query.

    python module04-rag/lab_query_construction.py            # needs GEMINI_API_KEY
    python module04-rag/lab_query_construction.py --offline  # bag-of-words, no key

THE SETUP
---------
Module 4 teaches RAG as five steps: chunk, embed, construct the query, retrieve,
augment. Step 3 is the one most RAG code skips: it embeds the user's text as-is.
This lab shows what that costs.

Here is EVAL-03's ticket:

    "A trouble ticket (TCK-4471) reports slow data speeds near SITE-031 during
     evening peak hours for the past three days, with no specific alarm cited yet."

It is a congestion question. The knowledge base has a congestion postmortem in
it. Watch which document comes back first.

FAIL -> FIX -> PASS
-------------------
The lab runs the same search three ways. Think of them as rungs on a ladder:
each one changes only the text we search with, and nothing else.

  RUNG 1  style="question"           embed the ticket, whole
  RUNG 2  style="measured"           embed the alarms and the KPI thresholds
  RUNG 3  style="measured+question"  measured facts first, ticket after

What each rung actually searches with, for CELL-031A:

  RUNG 1  "A trouble ticket (TCK-4471) reports slow data speeds near SITE-031 ..."
  RUNG 2  "high prb utilization rrc drop rate high backhaul latency warning cell
           congestion prb utilization rrc drop rate rrc setup success rate
           CELL-031A SITE-031"
  RUNG 3  the rung 2 text, then ". ", then the rung 1 text

Same knowledge base, same embedding model, same scoring. If the top result
changes between rungs, the search text is the only possible reason.

Rung 1 is not a strawman. It is what most RAG code does, because embedding the
user's text is the obvious thing to do.

Whichever rung you use, the ticket itself still goes into the prompt unchanged.
Query construction only changes what you SEARCH with.
"""
import argparse
import os
import sys

# Let Python find the course's shared code: data/ holds mock_tools.py (the fake
# network: KPIs, alarms, topology) and this folder holds rag_pipeline.py.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "data"))
sys.path.append(HERE)

import rag_pipeline as R                                  # noqa: E402
from mock_tools import get_active_alarms, get_cell_kpis   # noqa: E402

# Terminal colour codes, so PASS prints green and FAIL prints red.
BOLD, DIM, GRN, RED, CYN, OFF = (
    "\033[1m", "\033[2m", "\033[92m", "\033[91m", "\033[96m", "\033[0m")

# The scenario: the cell and site the ticket is about, the ticket text, and the
# document that SHOULD come back first. incident_001 is the congestion
# postmortem for this exact cell; if it ranks first, the rung passes.
CELL, SITE = "CELL-031A", "SITE-031"
QUESTION = ("A trouble ticket (TCK-4471) reports slow data speeds near SITE-031 during "
            "evening peak hours for the past three days, with no specific alarm cited yet.")
WANT = "incident_001_local_event_congestion.md"

# (style passed to build_retrieval_query, what it does, a short aside for the printout)
RUNGS = [
    ("question", "embed the ticket, whole", "what most RAG code does"),
    ("measured", "embed the alarms + crossed KPI thresholds", "no prose at all"),
    ("measured+question", "measured facts first, ticket after", "the pipeline's default"),
]


def short(name):
    # Shorten file names for the printout:
    #   "incident_003_volte_call_drops.md" -> "inc_3 (VoLTE)"
    return name.replace("incident_00", "inc_").replace(".md", "") \
               .replace("_local_event_congestion", " (congestion)") \
               .replace("_neighbor_outage_overflow", " (neighbour outage)") \
               .replace("_volte_call_drops", " (VoLTE)") \
               .replace("reference_congestion_and_handover_basics", "reference")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="bag-of-words instead of dense embeddings (no key needed)")
    args = ap.parse_args()

    # rag_pipeline.retrieve() uses Gemini whenever a key is set and word counts
    # otherwise. --offline hides the key for this run, so retrieval falls back to
    # word counts even if you have one.
    if args.offline:
        os.environ.pop("GEMINI_API_KEY", None)
    elif not os.environ.get("GEMINI_API_KEY"):
        sys.exit("[error] GEMINI_API_KEY is not set. Use --offline to run bag-of-words,\n"
                 "        but read the note it prints before you trust the result.")

    engine = "offline bag-of-words" if args.offline else "Gemini dense embeddings"
    # Live data for the cell: KPI readings (with which thresholds were crossed) and
    # the active alarms on its site. Rungs 2 and 3 build their search text from these.
    kpis, alarms = get_cell_kpis(CELL), get_active_alarms(SITE)
    # Steps 1 and 2 happen once: cut the knowledge base into its 24 chunks.
    # (The chunks are embedded the first time retrieve() runs, then reused.)
    chunks = R.load_and_chunk_knowledge_base()

    print(f"\n{BOLD}QUERY CONSTRUCTION — three rungs, one knowledge base{OFF}")
    print(f"{DIM}engine: {engine} · {len(chunks)} chunks · looking for {short(WANT)}{OFF}")
    print(f"\nthe ticket, as written:\n  {DIM}{QUESTION}{OFF}\n")
    if args.offline:
        print(f"{DIM}  Offline bag-of-words matches words, not meaning, and does not reproduce\n"
              f"  the rung 1 failure. Expect all three rungs to pass. Run with a key to see\n"
              f"  the real thing.{OFF}\n")

    results = []
    for style, what, aside in RUNGS:
        # Step 3: build the search text for this rung.
        q = R.build_retrieval_query(QUESTION, kpis, alarms, CELL, SITE, style=style)
        # Step 4: score all 24 chunks against it and keep the top 3. per_source=False
        # shows raw chunks, so one incident can take several slots -- which is how
        # you see a winner dominate (offline, rung 1 gives incident_001 slots 1 and 2).
        ranked = R.retrieve(q, chunks, k=3, per_source=False)
        # PASS if the congestion postmortem is ranked first. Measured with Gemini,
        # rung 1 put incident_003 (VoLTE) first by 0.001; rungs 2 and 3 put
        # incident_001 first. Step 5 (the LLM) never runs here: this lab is only
        # about which document the search finds.
        top = ranked[0]["source"] if ranked else ""
        ok = WANT in top
        results.append((style, ok))

        mark = f"{GRN}PASS{OFF}" if ok else f"{RED}FAIL{OFF}"
        print(f"  {mark}  {BOLD}{style}{OFF} — {what}  {DIM}({aside}){OFF}")
        print(f"        embedded: {DIM}{q[:96]}{'...' if len(q) > 96 else ''}{OFF}")
        for i, m in enumerate(ranked, 1):
            flag = f"  {CYN}<- ranked first{OFF}" if i == 1 else ""
            print(f"          {i}. {short(m['source'])}{flag}")
        print()

    print(BOLD + "=" * 72 + OFF)
    # Three possible endings: the failure this lab is about (rung 1 wrong, rung 3
    # right), no failure because we ran offline, or no failure with Gemini today.
    if results[0][1] is False and results[-1][1] is True:
        print(f"""
  Rung 1 put the wrong document first. Nothing about the retriever changed
  between rung 1 and rung 3 — same model, same chunks, same cosine similarity.
  Only the string being embedded changed.

  Why rung 1 loses: three of the ticket's four phrases describe the SHAPE OF
  THE REPORT — "a trouble ticket", "reports", "no specific alarm cited yet",
  "past three days". The VoLTE postmortem IS a trouble ticket with no major
  alarm that recurs by time of day. It is a near-perfect match to the
  paperwork and a poor match to the fault. The retriever did its job.

  {BOLD}Retrieve on what you measured and how it behaves, not on how it was
  reported.{OFF} Ticket numbers, who raised it, and whether an alarm was cited
  are routing metadata. They belong in the ticket. They do not belong in a
  vector.
""")
    elif args.offline:
        print("""
  No failure offline, as expected: bag-of-words counts shared words, and the
  ticket shares plenty with the congestion postmortem. The failure this lab is
  about comes from dense embeddings matching the MEANING of the report wording.
  Run it again with GEMINI_API_KEY set.
""")
    else:
        print(f"""
  You did not get the failure this lab is built around: on this embedding model,
  today, rung 1 ranked {'correctly' if results[0][1] else 'differently than expected'}.
  Write down what you actually saw. A retrieval result is a measurement with a
  date on it, not a property of the code. Then read build_retrieval_query in
  rag_pipeline.py and decide whether the rule still holds for you.
""")

    print(f"""  {BOLD}YOUR TURN{OFF}  (all edits are in this file)
  1. ALM-9003 is a MINOR, auto-cleared backhaul alarm on SITE-031, and rungs 2
     and 3 search with it along with everything else. Should it be there?
     In main(), after the line that fetches the alarms, add:
         alarms = [a for a in alarms if a["severity"] != "MINOR"]
     Re-run and see whether the ranking moves.
  2. Test the explanation, not just the result. Change QUESTION to the same
     complaint with the report wording removed, e.g.
         "Customers near SITE-031 say data is slow every evening."
     Does rung 1 still put the VoLTE incident first? (Rung 2 will not change:
     "measured" ignores the question entirely.)
  3. Make a folder next to this file called scratch_kb/ and add a short .md
     document that is only paperwork: a ticket raised from field reports, no
     alarm cited, recurring in the evenings. Then change the chunks line to:
         chunks = R.load_and_chunk_knowledge_base([R.KB_DIR, os.path.join(HERE, "scratch_kb")])
     Which rung breaks first? Do not add it to data/knowledge_base/: later
     modules and the eval are graded against that folder.
""")
    print(BOLD + "=" * 72 + OFF)


if __name__ == "__main__":
    main()
