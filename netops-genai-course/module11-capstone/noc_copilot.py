"""
noc_copilot.py — Module 10 capstone: the full NOC Copilot pipeline

Combines every module's piece into one end-to-end autonomous triage agent:
  Module 1  (Prompting)         -> Summarizing raw data into concise text
  Module 4  (RAG)               -> Structure-aware retrieval of historical incidents
  Module 5/6 (Agent + Tools)    -> Reasoning over live KPI/alarm/topology via tool calling
  Module 7  (Skill)             -> The 4-layer diagnostic RCA procedure (SKILL.md)
  Module 8  (MCP)               -> Standardized tool primitives
  Module 9  (Human-in-the-Loop) -> Strict approval gate before create_ticket fires

Pipeline: Detect -> Retrieve -> Diagnose -> Draft

Run:
    python noc_copilot.py
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "module04-rag"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "module06-noc-assistant"))

from mock_tools import get_active_alarms  # noqa: E402
from rag_pipeline import load_and_chunk_knowledge_base, retrieve  # noqa: E402
from noc_assistant import run_noc_assistant  # noqa: E402

SKILL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "module08-rca-skill", "SKILL.md"
)

# Terminal ANSI Color Palette (NOC Command Center Theme)
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_rca_procedure() -> str:
    with open(SKILL_PATH, encoding="utf-8") as f:
        return f.read()


def detect() -> list:
    """Step 1: Pull the current batch of active alarms across the network."""
    alarms = get_active_alarms()
    major_or_worse = [a for a in alarms if a["severity"] in ("MAJOR", "CRITICAL")]
    print(f"{CYAN}[Detect]{RESET} Ingested {len(alarms)} active alarms; filtered to {BOLD}{len(major_or_worse)} MAJOR/CRITICAL{RESET} signals.")
    return major_or_worse


def retrieve_context(alarm: dict) -> str:
    """Step 2: Pull relevant prior-incident context for this alarm's site via RAG."""
    chunks = load_and_chunk_knowledge_base()
    query = f"{alarm['alarm_type']} at {alarm.get('site_id', '')} {alarm.get('cell_id', '')}"
    top = retrieve(query, chunks, k=2)
    print(f"{YELLOW}[Retrieve]{RESET} Pulled {len(top)} historical runbooks matching incident symptoms.")
    return "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in top)


def diagnose_and_draft(alarm: dict, prior_context: str, rca_procedure: str) -> str:
    """Steps 3 & 4: Reason over live data (tool calling) and draft the RCA,
    grounded in the RCA Skill's procedure and the retrieved prior incidents.
    """
    question = f"""{rca_procedure}

---
NEW ALARM TO TRIAGE: {json.dumps(alarm)}

RELEVANT PRIOR INCIDENTS:
{prior_context}

Investigate using your tools, checking neighbor cell topology before concluding.
Draft the RCA in the Impact/Likely cause/Recommended action format.
If you conclude a ticket should be opened, propose create_ticket — human approval is required.
"""
    print(f"{GREEN}[Diagnose+Draft]{RESET} Launching cognitive ReAct triage on {BOLD}{alarm['alarm_id']}{RESET}...")
    return run_noc_assistant(question)


def run_noc_copilot():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}         NETOPS CO. — AUTONOMOUS NOC COPILOT (CAPSTONE)               {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    rca_procedure = load_rca_procedure()
    alarms_to_triage = detect()

    if not alarms_to_triage:
        print(f"{GREEN}All systems nominal. No MAJOR or CRITICAL alarms active.{RESET}")
        return

    for alarm in alarms_to_triage:
        print(f"\n{YELLOW}----------------------------------------------------------------------{RESET}")
        print(f"{BOLD}Triaging Alarm: {alarm['alarm_id']} | Type: {alarm['alarm_type']} | Severity: {alarm['severity']}{RESET}")
        print(f"{YELLOW}----------------------------------------------------------------------{RESET}")

        prior_context = retrieve_context(alarm)
        rca = diagnose_and_draft(alarm, prior_context, rca_procedure)

        print(f"\n{BOLD}{GREEN}--- Final Verified RCA for {alarm['alarm_id']} ---{RESET}\n{rca}")


if __name__ == "__main__":
    run_noc_copilot()
