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
python anomaly_explainer.py CELL-031A --runs=10  # ten samples per rung, not three
python anomaly_explainer.py CELL-031A --no-examples   # drop the examples from the
                                                      # validated report as well
```

Or open [`03_anomaly_explainer.ipynb`](03_anomaly_explainer.ipynb) in Colab. The two
paths now cover the same ground — the notebook adds the visual KPI table and shows the
Pydantic rejection as its own step.

---

## 1. Zero-shot — the drift

```
Categorize this cell anomaly in a few words: {readings}
```

The script asks three times — ten with `--runs=10`. You get reasonable answers and
almost no two identical strings: *"Cell Congestion / Capacity Overload"*, *"Severe Cell
Congestion"*, *"High Traffic Congestion / Cell Overload"*, and so on.

Now look closely at what is drifting, because it is not what people expect.

On CELL-031A those answers are **not** disagreeing. Ten runs produced nine distinct
strings and every one of them meant *congestion*. The model was not confused, not
unsure, not split between hypotheses — it agreed with itself completely and still
handed back nine different spellings of the same conclusion.

That is worse than disagreement, not better. A model that was genuinely torn would at
least be telling you something. This one is confident, correct, consistent, and still
`0/10` usable:

```python
if category == "CAPACITY_PRB_EXHAUSTION":   # never fires. Not once.
```

The drift is in the *wording*, and the wording is the only part your code can see.

Run the healthy cell and you get the other half of the picture: ten runs, ten distinct
strings, every one of them meaning "nothing is wrong" — and every one of them right.
Either way, zero that code can branch on.

This is the first time in the course you see non-determinism do real damage, and
Module 10 is built on it.

## 2. Taxonomy enforcement — and which intervention actually does it

In telecom, few-shot is not about tone. The useful framing is **domain taxonomy
enforcement**: get the model using your fault categories instead of inventing its own.

But be careful which intervention you credit, because going from rung 1 to rung 3 changes
**three** things at once — it names the four domains, it pins the reply format, and it adds
two worked examples. Lump those together and you will conclude "few-shot fixed it" when the
domain list may be doing all the work.

So the script runs the rungs separately and counts:

| rung | prompt | what it adds |
|---|---|---|
| 1 | *"Categorize this cell anomaly in a few words"* | nothing — the control |
| 2 | names the four domains, asks for the domain name only | the taxonomy and the format |
| 3 | rung 2 plus two worked examples | the examples, and only the examples |

`WHAT EACH RUNG BOUGHT` at the bottom of the output is the measurement. If rung 3 buys
nothing over rung 2 on your data, **that is a result — report it.** You would otherwise pay
for those examples in every prompt, forever, and never know. This is the first time in the
course that measuring beats asserting, and Module 10 is where it gets done properly.

Two things before you generalise from it: the default three runs is a demo rather than
evidence (`--runs=10`), and CELL-031A is an easy case with one obvious bucket. Worked
examples earn their keep on ambiguous inputs — try the healthy cell.

```
RADIO_ACCESS_INTERFERENCE   CAPACITY_PRB_EXHAUSTION
TRANSPORT_BACKHAUL_JITTER   CORE_SIGNALING_REJECT
```

Use these exact strings. `module07-workflow-patterns/01_prompt_chaining.py` branches on
them, so a shortened name here silently fails validation four modules later.

They are declared **once**, as a `Literal`, and the list the prompt interpolates is read
back off it with `typing.get_args`. Spelling the four strings out in both places is the
same two-sources-of-truth mistake as retyping a threshold: edit one, and the validator and
the prompt quietly stop agreeing about what a legal answer is.

**A note on the examples themselves**, because the choice is deliberate. Neither example is
CELL-031A's answer, and both use only metrics the model is actually sent. An earlier version
of this lab used *"PRB 94%, users 210 against planned capacity 150 → CAPACITY_PRB_EXHAUSTION"*
— and CELL-031A is PRB 96.3% with 214 users against a planned capacity of 150. The example
was the answer, two percent away, and it also quoted a figure (`planned_capacity_users`) that
lives in `topology.json` and never reaches the model at all. Few-shot looked powerful when
what it was really doing was matching a near neighbour.

Examples teach the **shape** of the reasoning — which combination of KPIs points where. The
domain list sets the **bounds**. Keep those jobs separate and the technique is doing what you
say it is doing.

## 3. Structured output — and the distinction that matters

Two levels of enforcement, and you want both:

| | what it buys you | what it does **not** |
|---|---|---|
| `json_mode=True` | the API returns something that **parses** | your keys. It sets the response MIME type; it passes no schema. A model can hand you perfectly valid JSON with entirely different fields in it. |
| `AnomalyReport` (Pydantic) | the JSON **means what you asked for** — right fields, right types, `Literal` enum, length bounds on the summary | nothing about whether the content is *true*. That is Module 10's job. |

That last cell is not a disclaimer, and the healthy cell in **Your turn** is where you find
that out. Run `CELL-022A` and you get ten fault classifications on a cell where nothing is
wrong — every one conformant, every one validated, every one false. `json_mode` buys
parseable. Pydantic buys **well-formed**. Neither buys *true*.

Worse, the constraint is what causes it. All four domains are faults, so a conformant answer
on a healthy cell is wrong by construction, and the `Literal` that protects you from an
invented category also forbids the model from reporting the truth. **A validator cannot save
you from a taxonomy with no word for "fine."**

Asking nicely gets JSON most of the time. Most of the time is fine for prose and
useless for anything your code parses.

`data/guardrails.py` in Module 10 is this same mechanism pointed at tool arguments.
Learn it here, where being wrong is free.

### One number, one place

The prompt asks which of `PRB > 75%`, `RRC drop > 5%` and `setup success < 95%` were
crossed — and it **interpolates those limits out of `mock_tools.THRESHOLDS`** rather than
spelling them out.

That was not always true here. The three numbers were typed out in the tool, again in
this script's prompt, and again in the notebook's KPI table. Raise the PRB limit in
`mock_tools.py` and the other two would have carried on asking about 75%, the model would
have carried on answering about 75%, and nothing would have errored.

Anything a prompt states about your network belongs in code first and gets interpolated
in. A number you retype into a prompt is a number that can drift away from the system it
describes — and the prompt is the copy nobody thinks to grep.

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

1. **`python anomaly_explainer.py CELL-022A --runs=10`** — the healthy cell. Run this one
   first. Ten fault classifications on a cell where nothing is wrong: PRB 57%, setup
   success 98.7%, drops 1.3%, throughput flat, answer key empty. Every one of them passes
   the `Literal`. Every one is false.

   Look at which rung got it right. The loose prompt — the one this module spends two
   slides criticising — said *"Normal Operation, no anomaly"* ten times out of ten. It was
   unusable by code and correct. The constrained rungs were usable by code and wrong.

   **Why:** all four domains are faults. There is no member meaning "nothing is wrong", so
   on a healthy cell a schema-conformant answer is *guaranteed* to be false. The constraint
   did not fail to help — it removed the model's ability to say the true thing. An agent
   wired this way opens a ticket on every healthy cell in the network.

2. **Fix it.** Give the taxonomy a word for "fine":

   - add `"NO_FAULT_DETECTED"` to the `FaultDomain` `Literal` (`FAULT_DOMAINS` follows on
     its own — that is what declaring it once buys you)
   - tell the prompt when to use it. A member the prompt never mentions is a member the
     model will not reach for, so adding it to the enum alone just moves the failure.

   Re-run CELL-022A. Then re-run **CELL-031A**, because a fix that repairs the healthy cell
   by making the model timid on the broken one has moved the failure rather than removed
   it. That regression check is the half people skip.

   Stuck, or want to compare? **`python solution_no_fault.py`** runs both cells before and
   after, side by side, and scores correctness against the answer key.

   The rule is worth more than the patch: **a classifier with no null class will always
   classify.** Before you constrain a model to a fixed set, ask what it should say when
   none of them apply.

3. **`python anomaly_explainer.py CELL-031A --runs=10`** — three samples per rung is a
   demo, ten is closer to evidence. Write down what each rung bought. You will want that
   number in Module 10, where the same question gets asked with a real harness.

4. **Add `confidence: float = Field(ge=0, le=1)`** to `AnomalyReport` and update the
   prompt. Then try it *without* updating the prompt, and watch Pydantic catch the
   mismatch in microseconds, for free, instead of three modules later inside an agent
   loop where it looks like a tool bug.

---

**Next:** the explainer only knows the numbers you hand it. It has no idea NetOps Co.
has seen this exact congestion pattern before and already knows how it was resolved.
Module 4 teaches it to remember.
