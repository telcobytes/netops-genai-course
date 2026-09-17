# Generative AI & Agentic AI for Mobile Network Operations (NOC)

Companion code repository for the master course: **Generative AI & Agentic AI for Mobile Network Operations**.

The entire course follows one continuous operational incident at **NetOps Co.**, a fictional mobile network operator whose 5G cell `CELL-031A` suffers severe recurring afternoon congestion. Across 10 hands-on modules, you build and assemble an enterprise autonomous NOC copilot layer-by-layer.

---

## Quick Start Guide

We recommend running the labs locally in your terminal or IDE (VS Code, PyCharm, Cursor).

```
                  ┌───────────────────────────────────────────────┐
                  │          STUDENT ONBOARDING CHOICES           │
                  └───────┬───────────────────────────────┬───────┘
                          │                               │
            Personal Laptop / Dev Box           Corporate Telecom Laptop
                          │                     (Locked down / No Admin)
                          ▼                               ▼
                 Option 1: Local Terminal         Option 2: GitHub Codespaces
                 (VS Code / PyCharm / iTerm)      (1-Click Zero-Install in Browser)
```

### Option 1: Local Terminal / VS Code (Recommended for 90% of Students)

Follow these 3 simple steps to get started in under 2 minutes:

#### Step 1: Clone & Setup Virtual Environment (One-time)
```bash
git clone https://github.com/<YOUR-GITHUB-USERNAME>/telecom-agentic-ai-course.git
cd telecom-agentic-ai-course

python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# Windows CMD:         venv\Scripts\activate
# Windows PowerShell:  .\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

#### Step 2: Set Free Gemini API Key (One-time)
This course uses **Google's Gemini API** by default because Google AI Studio offers a genuinely free tier with **no credit card required**:
1. Go to [aistudio.google.com](https://aistudio.google.com/) and sign in with any Google account.
2. Click **"Get API key"** → **"Create API key"**.
3. Set it in your active terminal session:
```bash
export GEMINI_API_KEY="your_api_key_here"      # macOS / Linux
set GEMINI_API_KEY="your_api_key_here"         # Windows CMD
$env:GEMINI_API_KEY="your_api_key_here"        # Windows PowerShell
```
*(Prefer OpenAI or Anthropic Claude? See `data/llm_client.py` — swap the commented block in one file, and all 10 modules automatically follow).*

#### Step 3: Your "Minute-5 First Win" Sanity Check
Verify your setup by inspecting NetOps Co.'s network data:
```bash
python data/mock_tools.py
```
You should see cell KPI counters, active site alarms, a topology lookup, and a mock ticket printed to your terminal.

---

### Option 2: Zero-Install Browser Fallback (GitHub Codespaces)

If you are on a **managed corporate laptop** (e.g. Ericsson, Nokia, AT&T, Verizon) where installing Python or running terminal scripts is blocked by enterprise endpoint policies:

1. In your web browser, navigate to the top of this GitHub repository.
2. Click the green **`<> Code`** button → select the **`Codespaces`** tab → click **`Create codespace on main`**.
3. A full VS Code workspace will open directly in your browser tab in ~30 seconds with Python already installed.
4. In the browser terminal at the bottom, run:
   ```bash
   pip install -r requirements.txt
   export GEMINI_API_KEY="your_api_key_here"
   python module01-summarizer/summarizer.py
   ```

---

## Running the Course Labs

Every script can be run directly from the **repository root** without changing directories:

| Module | Hands-On Topic | Command to Run from Repo Root |
|---|---|---|
| **01** | *First API call — the 3-line pattern* | `python module01-summarizer/gemini_quickstart.py` |
| **01** | Incident Summarizer | `python module01-summarizer/summarizer.py` |
| **02** | Deep Research (No-Code) | *(no code by design — see [`module02-nocode/`](module02-nocode/))* |
| **03** | Structured Anomaly Explainer | `python module03-anomaly-explainer/anomaly_explainer.py CELL-031A` |
| **04** | Semantic RAG Grounding | `python module04-rag/rag_pipeline.py` |
| **05** | Hand-Rolled ReAct Agent | `python module05-react-loop/react_agent.py` |
| **06** | Native Tool Calling & HITL | `python module06-noc-assistant/noc_assistant.py` |
| **07** | Workflow Patterns + Triage Triad | `python module07-workflow-patterns/05_orchestrator_workers.py --mock` |
| **08** | The Telecom RCA Skill | `python module08-rca-skill/run_skill.py CELL-031A` |
| **09** | Model Context Protocol (MCP) | `python module09-mcp/mcp_client.py` |
| **10** | Observability, Tracing & Tiered Eval | `python module10-eval/run_eval.py` |
| **10** | Guardrails (privilege, bounds, injection) | `python data/guardrails.py` |
| **11** | **Capstone: Autonomous NOC Copilot** | `python module11-capstone/noc_copilot.py` |

### Notebooks (Modules 1–5)

Each of those five modules keeps its Colab notebook **inside its own module folder**
next to the script — `module04-rag/04_rag.ipynb`, and so on. One folder per module, so
there is no second tree to cross-reference. See [`LABS.md`](LABS.md) for the launch
badges and the API-key setup.

From Module 6 on, the course moves to files on your machine, because tool schemas,
Skills, MCP servers and eval suites *are* files.

### Checkpoints

Three graded self-tests — `starter.py` has the TODOs, `check.py` prints PASS or FAIL,
`solution.py` is for after you have tried. 15–25 minutes each.

| After module | Checkpoint | Run |
|---|---|---|
| 4 | Teach it a new runbook | `cd checkpoints/01_rag && python check.py` |
| 7 | Build the dispatcher | `cd checkpoints/02_routing && python check.py` |
| 10 | Write your own eval | `cd checkpoints/03_eval && python check.py` |

---

## Course Architecture Reference

For an end-to-end architecture breakdown, prompt templates, cognitive circuit breaker rules, and resume portfolio snippets, see:
👉 **[`telecom-autonomous-agent-cheat-sheet.md`](telecom-autonomous-agent-cheat-sheet.md)**

---

## Troubleshooting & FAQ

* **API Key Missing Warning:** If you see `[ERROR] GEMINI_API_KEY environment variable is not set`, check that you ran `export GEMINI_API_KEY="..."` in the same terminal tab you are using to run Python.
* **Offline Fallbacks:** If running without internet access:
  * `module04-rag/rag_pipeline.py` automatically falls back to an offline cosine similarity vectorizer.
  * `module10-eval/run_eval.py --mock` runs the 3-case evaluation benchmark on offline sample responses.
* **Free Tier Quotas:** Gemini's free tier allows 15 requests per minute, which is more than enough for all course exercises. If you hit a rate limit, simply wait 10 seconds and re-run.
