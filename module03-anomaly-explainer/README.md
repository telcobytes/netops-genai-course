# Module 3 — Prompt Engineering: The KPI Anomaly Explainer

Module 1 produced prose a human reads. This module produces **JSON code can act on**,
which is the bridge from prompting to agents.

Three techniques, in the order they build on each other, and then the thing that makes
them reliable.

---

## How to run

```bash
export GEMINI_API_KEY="..."
cd module03-anomaly-explainer

python anomaly_explainer.py CELL-031A            # a real anomaly in the sample data
python anomaly_explainer.py CELL-022A            # a healthy cell
python anomaly_explainer.py CELL-031A --ablate   # the same run, few-shot examples removed
```

Or open [`03_anomaly_explainer.ipynb`](03_anomaly_explainer.ipynb) in Colab. The two
paths now cover the same ground — the notebook adds the visual KPI table and shows the
Pydantic rejection as its own step.

---

## 1. Zero-shot — the drift

```
Categorize this cell anomaly in a few words: {readings}
```

The script asks three times. You get three reasonable answers and no two identical
strings: *"capacity congestion"*, *"high user density"*, *"PRB exhaustion event"*.

Every one of those is correct. None of them is something `if category == ...` can
branch on, and that is the whole problem. This is also the first time in the course you
see non-determinism do real damage — Module 10 is built on it.

## 2. Few-shot — taxonomy enforcement

In telecom, few-shot is not about tone. It is **domain taxonomy enforcement**: give the
model the buckets and two worked examples, and the drift stops.

```
RADIO_ACCESS_INTERFERENCE   CAPACITY_PRB_EXHAUSTION
TRANSPORT_BACKHAUL_JITTER   CORE_SIGNALING_REJECT
```

Use these exact strings. `module07-workflow-patterns/01_prompt_chaining.py` branches on
them, so a shortened name here silently fails validation four modules later.

## 3. Structured output — and the distinction that matters

Two levels of enforcement, and you want both:

| | what it buys you | what it does **not** |
|---|---|---|
| `json_mode=True` | the API returns something that **parses** | your keys. It sets the response MIME type; it passes no schema. A model can hand you perfectly valid JSON with entirely different fields in it. |
| `AnomalyReport` (Pydantic) | the JSON **means what you asked for** — right fields, right types, `Literal` enum, length bounds on the summary | nothing about whether the content is *true*. That is Module 10's job. |

Asking nicely gets JSON most of the time. Most of the time is fine for prose and
useless for anything your code parses.

`data/guardrails.py` in Module 10 is this same mechanism pointed at tool arguments.
Learn it here, where being wrong is free.

---

## What the model is and is not shown

`get_cell_kpis` does the arithmetic — rolling averages, deltas, threshold crossings —
and hands back a small, already-correct summary. **Tools compute. Agents reason.** Never
make a language model add up a long table.

But notice what the script sends: `latest`, `rolling_avg` and `delta`, and **not** the
tool's own `thresholds_crossed` verdict.

That matters both ways:

- Send the verdict and the model is transcribing an answer it was handed, not analysing
  anything — and you cannot tell from the output, because the output is right.
- Withhold the wrong field and the task becomes unanswerable. `latest` has to go in:
  CELL-031A averages **72.8%** PRB across the window while its latest reading is
  **96.3%**, so a model given only the average would be correct to say nothing crossed
  75%.

Held back, `thresholds_crossed` becomes the **answer key** the script prints before it
asks the model anything. That is what makes this an exercise rather than a demo.

---

## Your turn

1. **`python anomaly_explainer.py CELL-022A`** — a healthy cell. The answer key is
   empty; the question is whether the model agrees. A prompt that only ever says
   "something is wrong" is not analysing anything.

2. **`python anomaly_explainer.py CELL-031A --ablate`** — drops the few-shot examples
   and changes nothing else. Run it four or five times and count how often the category
   still validates. That number is the argument for few-shot, measured on your own data
   instead of asserted on a slide. Write it down; Module 10 does this properly, with a
   harness.

3. **Add `confidence: float = Field(ge=0, le=1)`** to `AnomalyReport` and update the
   prompt. Then try it *without* updating the prompt, and watch Pydantic catch the
   mismatch in microseconds, for free, instead of three modules later inside an agent
   loop where it looks like a tool bug.

---

**Next:** the explainer only knows the numbers you hand it. It has no idea NetOps Co.
has seen this exact congestion pattern before and already knows how it was resolved.
Module 4 teaches it to remember.
