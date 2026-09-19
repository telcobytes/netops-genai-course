"""
noc_copilot.py — Module 11 capstone: the full NOC Copilot pipeline

Combines every module's piece into one end-to-end autonomous triage agent:
  Module 1  (Prompting)         -> Summarizing raw data into concise text
  Module 4  (RAG)               -> Structure-aware retrieval of historical incidents
  Module 5/6 (Agent + Tools)    -> Reasoning over live KPI/alarm/topology via tool calling
  Module 8  (Skill)             -> The 4-layer diagnostic RCA procedure (SKILL.md)
  Module 9  (MCP)               -> Standardized tool primitives
  Module 10 (Human-in-the-Loop) -> Strict approval gate before create_ticket fires

Pipeline: Detect -> Correlate -> Retrieve -> Diagnose -> Draft

Run:
    python noc_copilot.py

    Needs GEMINI_API_KEY. Without it, the run prints how to set one and stops —
    there is no offline mode here.
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


# The severity order lives in guardrails.py. One file owns it.
from guardrails import SEVERITY_RANK  # noqa: E402
from llm_client import format_usage, reset_usage  # noqa: E402


def load_rca_procedure() -> str:
    with open(SKILL_PATH, encoding="utf-8") as f:
        return f.read()


def detect() -> list:
    """Step 1: Pull the current batch of active alarms across the network."""
    alarms = get_active_alarms()
    major_or_worse = [a for a in alarms if a["severity"] in ("MAJOR", "CRITICAL")]
    print(f"{CYAN}[Detect]{RESET} Ingested {len(alarms)} active alarms; filtered to {BOLD}{len(major_or_worse)} MAJOR/CRITICAL{RESET} signals.")
    return major_or_worse


def correlate(alarms: list) -> list:
    """Step 2: group the alarms that are ONE FAULT into one incident.

    This step used to not exist, and the cost was visible every run: the three
    MAJOR/CRITICAL alarms in the feed -- ALM-9001 at 08:29, ALM-9002 at 08:44,
    ALM-9004 at 08:58 -- are all CELL-031A, all the same congestion event. The
    copilot triaged them as three separate incidents, ran the ReAct loop three
    times, and proposed three tickets for one fault.

    Module 10's EVAL-02 marks exactly that as failure: "recognise the existing
    related ticket rather than creating a duplicate." The capstone was
    demonstrating the thing the eval fails an agent for, and any NOC engineer
    watching would have caught it in the first minute.

    Correlation is the cheapest step in this pipeline and the easiest to leave
    out, because nothing crashes when you do -- you just pay three times and
    hand your on-call three tickets to close as duplicates.

    The key here is (site, cell). That is the simple version, and it is a
    deliberate teaching choice rather than the last word: real correlation also
    bounds a time window, follows topology (a parent transport fault raising
    alarms on every child cell), and knows which alarm types are symptoms of
    which. Widening this key is the exercise at the end of the module.
    """
    groups = {}
    for a in alarms:
        key = (a.get("site_id", ""), a.get("cell_id", ""))
        groups.setdefault(key, []).append(a)

    incidents = []
    for i, ((site, cell), members) in enumerate(sorted(groups.items()), 1):
        members.sort(key=lambda a: a.get("timestamp", ""))
        worst = max(members, key=lambda a: SEVERITY_RANK.get(a["severity"], 0))
        incidents.append({
            "incident_id": f"INC-{i}",
            "site_id": site,
            "cell_id": cell,
            "severity": worst["severity"],
            "alarms": members,
        })

    print(f"{CYAN}[Correlate]{RESET} {len(alarms)} signals -> "
          f"{BOLD}{len(incidents)} incident(s){RESET}.")
    for inc in incidents:
        ids = ", ".join(f"{a['alarm_id']} {a['severity']}" for a in inc["alarms"])
        where = inc["cell_id"] or inc["site_id"]
        print(f"           {inc['incident_id']}  {where}: {ids}")
    if len(incidents) < len(alarms):
        print(f"           {len(alarms) - len(incidents)} fewer investigation(s), "
              f"and no duplicate tickets to close tomorrow.")
    return incidents


def retrieve_context(incident: dict) -> str:
    """Step 3: Pull prior-incident context for this INCIDENT via RAG.

    The query is built from every alarm type in the group, not just one. Three
    symptoms of one fault describe it better than any one of them does.
    """
    chunks = load_and_chunk_knowledge_base()
    types = " ".join(sorted({a["alarm_type"] for a in incident["alarms"]}))
    query = f"{types} at {incident.get('site_id', '')} {incident.get('cell_id', '')}"
    top = retrieve(query, chunks, k=2)
    print(f"{YELLOW}[Retrieve]{RESET} Pulled {len(top)} historical runbooks matching incident symptoms.")
    return "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in top)


def diagnose_and_draft(incident: dict, prior_context: str, rca_procedure: str) -> str:
    """Steps 4 & 5: Reason over live data (tool calling) and draft ONE RCA for
    the whole incident, grounded in the RCA Skill's procedure and the retrieved
    prior incidents.

    The agent is handed every alarm in the group at once. That is the point: it
    should explain all three as one fault, not three times as three.
    """
    question = f"""{rca_procedure}

---
INCIDENT TO TRIAGE — {len(incident['alarms'])} correlated alarm(s) on \
{incident.get('cell_id') or incident.get('site_id')}:
{json.dumps(incident['alarms'], indent=2)}

These alarms have been correlated as ONE incident. Explain them as one fault.
Open at most ONE ticket for it.

RELEVANT PRIOR INCIDENTS:
{prior_context}

Investigate using your tools, checking neighbor cell topology before concluding.
Draft the RCA in the Impact/Likely cause/Recommended action format.
If you conclude a ticket should be opened, propose create_ticket — human approval is required.
"""
    print(f"{GREEN}[Diagnose+Draft]{RESET} Launching cognitive ReAct triage on "
          f"{BOLD}{incident['incident_id']}{RESET}...")
    # Scope the guardrail to this incident's site. Reading a neighbour's KPIs is
    # part of the job; filing against the neighbour is not, and that is enforced
    # in code rather than asked for in the prompt.
    return run_noc_assistant(question, scope=[incident["site_id"]] if incident.get("site_id") else None)


def run_noc_copilot():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}         NETOPS CO. — AUTONOMOUS NOC COPILOT (CAPSTONE)               {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    reset_usage()          # measure THIS run, not whatever ran before it
    rca_procedure = load_rca_procedure()
    alarms_to_triage = detect()

    if not alarms_to_triage:
        print(f"{GREEN}All systems nominal. No MAJOR or CRITICAL alarms active.{RESET}")
        return

    incidents = correlate(alarms_to_triage)

    for inc in incidents:
        where = inc["cell_id"] or inc["site_id"]
        types = ", ".join(sorted({a["alarm_type"] for a in inc["alarms"]}))
        print(f"\n{YELLOW}----------------------------------------------------------------------{RESET}")
        print(f"{BOLD}Triaging Incident: {inc['incident_id']} | {where} | "
              f"{len(inc['alarms'])} alarm(s) | Worst: {inc['severity']}{RESET}")
        print(f"{BOLD}  {types}{RESET}")
        print(f"{YELLOW}----------------------------------------------------------------------{RESET}")

        prior_context = retrieve_context(inc)
        rca = diagnose_and_draft(inc, prior_context, rca_procedure)
        if not rca:
            rca = (f"{RED}[no RCA produced for {inc['incident_id']} — the agent ended without "
                   f"an answer. Re-run. If it repeats, the context has outgrown the output "
                   f"budget.]{RESET}")

        print(f"\n{BOLD}{GREEN}--- Final Verified RCA for {inc['incident_id']} ---{RESET}\n{rca}")

    # "What did that cost?" is the first question anyone's manager asks, and the
    # only honest answer is a measured one. Read from usage_metadata, not asserted.
    print(f"\n{CYAN}{format_usage('this capstone run')}{RESET}")


if __name__ == "__main__":
    run_noc_copilot()
