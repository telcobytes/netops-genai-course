# The labs

One folder per module, `module00` through `module11`. Everything that module needs
lives in its folder: the script, the notebook if it has one, and a README. Shared
material sits in `data/` (mock tools, the LLM client, the knowledge base, the CSVs)
and `checkpoints/`.

| Module | Folder | Run it |
|---|---|---|
| 1 · GenAI Foundations — the Incident Summarizer | `module01-summarizer/` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/module01-summarizer/01_incident_summarizer.ipynb) · or `python module01-summarizer/summarizer.py` |
| 2 · The No-Code Baseline | `module02-nocode/` | *no code, no key, by design* — NotebookLM in a browser tab: the repo's change bundle, then 3GPP TS 38.331 itself. [Lab brief](module02-nocode/README.md) |
| 3 · Prompt Engineering — the KPI Anomaly Explainer | `module03-anomaly-explainer/` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/module03-anomaly-explainer/03_anomaly_explainer.ipynb) · or `python module03-anomaly-explainer/anomaly_explainer.py` |
| 4 · Grounding Agents — RAG | `module04-rag/` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/module04-rag/04_rag.ipynb) · or `python module04-rag/rag_pipeline.py` |
| 5 · From Prompts to Agents — the ReAct loop | `module05-react-loop/` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/module05-react-loop/05_react_loop.ipynb) · or `python module05-react-loop/react_agent.py` |
| 6 · Tool Calling & the approval gate | `module06-noc-assistant/` | `python module06-noc-assistant/noc_assistant.py` |
| 7 · Workflow Patterns + the Triage Triad | `module07-workflow-patterns/` | `python module07-workflow-patterns/05_orchestrator_workers.py` |
| 8 · The Telecom RCA Skill | `module08-rca-skill/` | `python module08-rca-skill/run_skill.py CELL-031A` |
| 9 · Model Context Protocol | `module09-mcp/` | `python module09-mcp/mcp_server.py`, then `mcp_client.py` |
| 10 · Evaluation, tracing & guardrails | `module10-eval/` | `python module10-eval/run_eval.py` |
| 11 · Capstone — the NOC Copilot | `module11-capstone/` | `python module11-capstone/noc_copilot.py` |

Colab opens any public GitHub notebook straight from its URL — nothing to host,
nothing to deploy. If a badge 404s, the repo is private: Settings → Danger Zone →
Change visibility.

---

## Modules 1–5 run in your browser

**No install, no Python on your machine, no IT ticket.** A Google account and a free
Gemini API key is the whole prerequisite.

Click the 🔑 **key icon** in Colab's left sidebar, add a secret named
`GEMINI_API_KEY`, and turn on *Notebook access*. Get a free key at
[aistudio.google.com](https://aistudio.google.com) — no credit card.

**Never paste a key into a cell.** Notebooks get shared and the key goes with them.
Every notebook here reads from Colab secrets and falls back to a masked `getpass`
prompt if you're in plain Jupyter.

Each notebook's first cell clones this repo into `/content/netops-genai-course` and
imports from it, so the notebook and the script are running the same code regardless
of which folder the notebook itself lives in.

## Why those five and not the rest

Modules 1–5 are exploratory: change a prompt, run it again, see what happened. That
is what a notebook is for, and the inline rendering earns its keep — the similarity
bar chart in Module 4 shows you *by how much* the right document won, which a
terminal can't.

From **Module 6 onward the course moves to files**, and that is deliberate. Tool
schemas, a packaged Skill on disk, an MCP server running as a process, an eval suite
you could put in CI — those *are* files. Putting them in a notebook would demonstrate
the opposite of the lesson. Notebooks also carry hidden state and out-of-order
execution, which is a special kind of misery when you are debugging an agent loop.

You haven't hit a limitation. You've outgrown the tool.

## One implementation, not two

A notebook and its script are two front ends onto the same code. Notebook 4 imports
`load_and_chunk_knowledge_base`, `retrieve`, `embed_with_gemini_api` and
`_cosine_similarity` from `rag_pipeline.py`; notebook 5 imports `run_react_agent`
from `react_agent.py`; notebooks 1, 3 and 4 all import `mock_tools` and `llm_client`
from `data/`. Fix a bug once and both halves of the course get it.

There is **one deliberate exception**, and it says so in the notebook:
`01_incident_summarizer.ipynb` writes its own `summarize()` rather than importing
`summarize_tickets`, because Module 1's whole point is watching the abstraction get
built — raw `genai` call, then `llm_client`, then a function you can edit.
`summarizer.py` is the tidied-up finished version, and the diff between them is the
lesson.

`data/nb_viz.py` holds the small HTML renderers (tables, similarity bars, agent
traces). Nothing in the course depends on it — the scripts print the same information
as text.

## Running the notebooks locally instead

Every notebook works in plain Jupyter. Clone the repo,
`pip install -r requirements.txt`, set `GEMINI_API_KEY`, and change the
`sys.path.append` lines from `/content/netops-genai-course/...` to a relative path.

## Checkpoints

Three graded self-tests, spaced across the course. Bigger than a "Your turn", smaller
than the capstone — 15–25 minutes each. `starter.py` has the TODOs, `check.py` prints
PASS or FAIL, `solution.py` is for after you have tried.

| After module | Checkpoint | Run |
|---|---|---|
| 4 | Teach it a new runbook | `cd checkpoints/01_rag && python check.py` |
| 7 | Build the dispatcher | `cd checkpoints/02_routing && python check.py` |
| 10 | Write your own eval | `cd checkpoints/03_eval && python check.py` |
