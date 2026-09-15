# Colab notebooks — Modules 1 to 5

The first half of this course runs in your browser. **No install, no Python on your machine,
no IT ticket.** You need a Google account and a free Gemini API key.

| | Module | Run it |
|---|---|---|
| 1 | GenAI Foundations — the Incident Summarizer | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/notebooks/01_incident_summarizer.ipynb) |
| 2 | The No-Code Baseline | *no notebook — this module runs in a browser tab by design* |
| 3 | Prompt Engineering — the KPI Anomaly Explainer | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/notebooks/03_anomaly_explainer.ipynb) |
| 4 | Grounding Agents — RAG | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/notebooks/04_rag.ipynb) |
| 5 | From Prompts to Agents — the ReAct loop | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/telcobytes/netops-genai-course/blob/main/notebooks/05_react_loop.ipynb) |

> Colab opens any public GitHub notebook straight from its URL — nothing to host, nothing to
> deploy. If a badge 404s, the repo is private: Settings → Danger Zone → Change visibility.

## Your API key

Click the 🔑 **key icon** in Colab's left sidebar, add a secret named `GEMINI_API_KEY`, and turn
on *Notebook access*. Get a free key at [aistudio.google.com](https://aistudio.google.com) — no
credit card required.

**Never paste a key into a cell.** Notebooks get shared, and the key goes with them. Every
notebook here reads from Colab secrets and falls back to a masked `getpass` prompt if you're in
plain Jupyter instead.

## Why these five and not the rest

Modules 1–5 are exploratory: change a prompt, run it again, see what happened. That is what a
notebook is for, and the inline rendering earns its keep — a similarity bar chart in Module 4
shows you *by how much* the right document won, which a terminal can't.

From **Module 6 onward the course moves to files**, and that is deliberate. Tool schemas, a
packaged Skill on disk, an MCP server running as a process, an eval suite you could put in CI —
those *are* files. Putting them in a notebook would demonstrate the opposite of the lesson.
Notebooks also carry hidden state and out-of-order execution, which is a special kind of misery
when you're debugging an agent loop.

You haven't hit a limitation. You've outgrown the tool.

## One implementation, not two

These notebooks **import from `data/`** after cloning the repo — they do not re-implement
anything. `mock_tools.py`, `llm_client.py`, `rag_pipeline.py` and `react_agent.py` are the same
files the local scripts use. Fix a bug once and both halves of the course get it.

`data/nb_viz.py` holds the small HTML renderers (tables, similarity bars, agent traces). Nothing
in the course depends on it — the scripts print the same information as text.

## Running locally instead

Every notebook works in plain Jupyter. Clone the repo, `pip install -r requirements.txt`, set
`GEMINI_API_KEY`, and change the `sys.path.append` lines from `/content/netops-genai-course/...`
to a relative path.
