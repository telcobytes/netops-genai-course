"""
summarizer.py — Module 1 hands-on: the Incident Summarizer

Loads NetOps Co.'s trouble tickets and asks an LLM to produce a NOC shift-handoff
briefing: grouped by site, flagging anything urgent or recurring.

Run:
    python summarizer.py

    Needs GEMINI_API_KEY. Without it, the run prints how to set one and stops —
    there is no offline mode here.

Requires: GEMINI_API_KEY set in your environment (or see llm_client.py to switch
providers).
"""

import csv
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from llm_client import call_llm  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_tickets(path=None):
    path = path or os.path.join(DATA_DIR, "tickets.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize_tickets(tickets):
    ticket_text = "\n".join(
        f"- [{t['ticket_id']}] {t['site_id']} ({t['category']}, {t['status']}): {t['summary']}"
        for t in tickets
    )
    prompt = f"""You are helping a NOC shift-handoff. Below are open and recently
closed trouble tickets. Write a short shift-handoff briefing: group by site,
call out anything that looks urgent or recurring, and keep it under 150 words.

TICKETS:
{ticket_text}
"""
    return call_llm([{"role": "user", "content": prompt}])


if __name__ == "__main__":
    tickets = load_tickets()
    print(f"Loaded {len(tickets)} tickets.\n")
    briefing = summarize_tickets(tickets)
    print("--- SHIFT-HANDOFF BRIEFING ---\n")
    print(briefing)

    # Hands-on exercise (from the lecture): try modifying the prompt above to:
    #   1. Return only bullet points, no prose
    #   2. Flag only CRITICAL-sounding categories
    #   3. Produce a version under 50 words
    # and compare how much control you have over the output shape.
