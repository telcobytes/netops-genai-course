"""
noc_copilot.py — Module 11 capstone: the full NOC Copilot pipeline

Combines every module's piece into one end-to-end autonomous triage agent:
  Module 1  (Prompting)      -> the alarm batch summarised into one incident brief
  Module 3  (Structure)      -> the fixed Impact / Likely cause / Recommended action shape
  Module 4  (RAG)            -> retrieval of the historical runbooks for this incident
  Module 5  (ReAct)          -> the reasoning loop, with a step budget
  Module 6  (Tools + gate)   -> native tool calling, and the human approval gate
  Module 7  (Patterns)       -> correlate-then-triage, one incident at a time
  Module 8  (Skill)          -> the 4-layer diagnostic procedure, read from SKILL.md
  Module 10 (Guardrails)     -> scope and severity checked in code, before the human

Module 9's MCP server exposes these same tools over the protocol. This file calls
them directly instead, so the capstone has no transport to debug — run
module09-mcp/mcp_client.py to see the same tools over MCP.

Pipeline: Detect -> Correlate -> Retrieve -> Diagnose -> Draft

Run:
    python noc_copilot.py
    python noc_copilot.py --no-skill     # Failure Lab #4: the same run, procedure removed

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


# Failure Lab #4. Without the Skill's 4-layer order, nothing forces the agent to
# read a neighbour before it attributes cause — so it blames the cell that is
# alarming, which is the mistake a junior engineer makes in their first week.
#
# The rule lives in THREE places, and all three have to go or the lab proves
# nothing:
#   1. the Skill's 4-layer procedure (SKILL.md), replaced by NAIVE_PROCEDURE
#   2. the "checking neighbor cell topology" clause in diagnose_and_draft
#   3. noc_assistant.SYSTEM_PROMPT, which says it outright
#
# This was measured, not assumed. Removing only 1 and 2 changed nothing: the
# agent read CELL-014A and CELL-022A before ticketing on both runs, because
# Module 6's system prompt still told it to. An ablation that leaves the rule
# somewhere in the context is not an ablation — it is a demo that the rule works.
# Module 10's repeat.py --prompt naive makes exactly this point.
#
# WHAT THE ABLATION ACTUALLY BUYS, measured on gemini-3.6-flash:
#
#   with the Skill     4 runs, 4 read a neighbour first. Three of the four read
#                      all four candidates — both neighbour cells and both sites.
#   without it         3 runs: one read both, one read only CELL-022A, and one
#                      read NOTHING and blamed the alarming cell outright.
#
# So the Skill did not change whether the agent USUALLY checks. It changed
# whether it ALWAYS checks, and how completely. That is slide 89's rule again:
# a prompt buys a better number, structure buys a guarantee.
#
# Note for whoever runs this live: the failure is INTERMITTENT, roughly one run
# in three. Do not promise it will appear on cue. Run it more than once — the
# variance between runs is the lesson, and the variance is reproducible even
# when the failure is not. Re-measure on your own key; the numbers move.
NAIVE_PROCEDURE = """You are a NOC engineer. Read the alarms you are given,
investigate with your tools, and write an RCA in the
Impact / Likely cause / Recommended action format.
"""

# Module 6's prompt with the neighbour rule taken out, and nothing else changed.
NAIVE_SYSTEM_PROMPT = """You are a NOC assistant for NetOps Co. Use the available
tools to investigate before answering.

When your investigation supports opening a ticket, CALL create_ticket. Do not ask
permission in your answer first. A human approval gate is enforced in code around
that tool, so calling it is a proposal, not an action.
"""


def load_rca_procedure(use_skill: bool = True) -> str:
    if not use_skill:
        return NAIVE_PROCEDURE
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


def _watch_tools(neighbour_ids):
    """Record which tools ran, so the lab can report what the agent DID.

    Returns (restore, seen). `seen` grows as the agent works: the set of
    neighbour ids it read, and whether it proposed a ticket yet.
    """
    import noc_assistant

    original = noc_assistant._dispatch_tool
    seen = {"neighbours": set(), "ticket_proposed": False}

    def _dispatch(name, args):
        if name == "create_ticket":
            seen["ticket_proposed"] = True
        else:
            # Only neighbours read BEFORE the proposal count. Reading one
            # afterwards is not a check, it is a footnote.
            if not seen["ticket_proposed"]:
                for value in (args or {}).values():
                    if str(value) in neighbour_ids:
                        seen["neighbours"].add(str(value))
        return original(name, args)

    noc_assistant._dispatch_tool = _dispatch

    def restore():
        noc_assistant._dispatch_tool = original

    return restore, seen


def _neighbour_ids(cell_id: str) -> set:
    """The cells this one hands traffic to, plus their sites."""
    from mock_tools import lookup_topology
    topo = lookup_topology(cell_id) or {}
    ids = set()
    for cell in topo.get("neighbors", []):
        ids.add(cell)
        nb = lookup_topology(cell) or {}
        if nb.get("site_id"):
            ids.add(nb["site_id"])
    return ids


def diagnose_and_draft(incident: dict, prior_context: str, rca_procedure: str,
                       use_skill: bool = True) -> str:
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

Investigate using your tools{', checking neighbor cell topology before concluding' if use_skill else ''}.
Draft the RCA in the Impact/Likely cause/Recommended action format.
If you conclude a ticket should be opened, propose create_ticket — human approval is required.
"""
    print(f"{GREEN}[Diagnose+Draft]{RESET} Launching cognitive ReAct triage on "
          f"{BOLD}{incident['incident_id']}{RESET}...")

    import noc_assistant
    neighbours = _neighbour_ids(incident.get("cell_id") or "")
    restore, seen = _watch_tools(neighbours)
    original_prompt = noc_assistant.SYSTEM_PROMPT
    if not use_skill:
        # The third place the rule lives. See NAIVE_SYSTEM_PROMPT.
        noc_assistant.SYSTEM_PROMPT = NAIVE_SYSTEM_PROMPT
    try:
        # Scope the guardrail to this incident's site. Reading a neighbour's KPIs
        # is part of the job; filing against the neighbour is not, and that is
        # enforced in code rather than asked for in the prompt.
        answer = run_noc_assistant(
            question, scope=[incident["site_id"]] if incident.get("site_id") else None)
    finally:
        restore()
        noc_assistant.SYSTEM_PROMPT = original_prompt

    # The verdict is about what the run DID, not how the RCA reads. A fluent RCA
    # that never read a neighbour is exactly the failure this lab is about.
    if neighbours:
        if seen["neighbours"]:
            print(f"{GREEN}[Verdict]{RESET} neighbour(s) read before any ticket: "
                  f"{BOLD}{', '.join(sorted(seen['neighbours']))}{RESET}")
        else:
            print(f"{RED}[Verdict]{RESET} {BOLD}NO neighbour was read before the agent "
                  f"concluded.{RESET} It blamed the cell that was alarming.")
            print(f"           Candidates it never looked at: {', '.join(sorted(neighbours))}")
    return answer


def run_noc_copilot(use_skill: bool = True):
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}         NETOPS CO. — AUTONOMOUS NOC COPILOT (CAPSTONE)               {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")
    if not use_skill:
        print(f"{RED}{BOLD}FAILURE LAB #4 — the Skill's 4-layer procedure is DISABLED.{RESET}")
        print(f"{RED}Nothing now forces a neighbour check before the agent attributes "
              f"cause.{RESET}\n")

    reset_usage()          # measure THIS run, not whatever ran before it
    rca_procedure = load_rca_procedure(use_skill)
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
        rca = diagnose_and_draft(inc, prior_context, rca_procedure, use_skill)
        if not rca:
            rca = (f"{RED}[no RCA produced for {inc['incident_id']} — the agent ended without "
                   f"an answer. Re-run. If it repeats, the context has outgrown the output "
                   f"budget.]{RESET}")

        print(f"\n{BOLD}{GREEN}--- Final Verified RCA for {inc['incident_id']} ---{RESET}\n{rca}")

    # "What did that cost?" is the first question anyone's manager asks, and the
    # only honest answer is a measured one. Read from usage_metadata, not asserted.
    print(f"\n{CYAN}{format_usage('this capstone run')}{RESET}")


if __name__ == "__main__":
    # --no-skill is Failure Lab #4: same capstone, same data, procedure removed.
    run_noc_copilot(use_skill="--no-skill" not in sys.argv)
