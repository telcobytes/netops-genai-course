# Module 10 — Evaluation, Observability & Tracing

"It worked once in my demo" is not a standard you can put on a rota. This module
builds the harness that tells you whether an agent is safe *today*, and the
tracing that tells you what it actually did.

---

## How to run

Tier 1 needs no API key. Everything else does.

```bash
cd module10-eval

python run_eval.py              # the golden set, tier 1 — works with no key
python run_eval.py --judge      # adds tier 2, the LLM judge          (needs a key)
python run_eval.py --mock       # force the offline path explicitly

python tracing.py               # the @traced decorator, end to end   (no key)
python tracing.py --show --run 2   # read one run back out of the log

export GEMINI_API_KEY="..."
python repeat.py --runs 5                    # the same question, five times
python repeat.py --runs 5 --prompt naive     # ...with the rule removed
python repeat.py --runs 5 --mode chained     # ...with the rule made structural
python lab_prompt_injection.py               # the alarm that gave the orders
python lab_prompt_injection.py --clean       # the same run, unpoisoned
```

Without a key, `run_eval.py` says so and drops to the offline path. `repeat.py`
and `lab_prompt_injection.py` print how to set one and stop — they have no
offline mode, because the whole point is what a live model does.

### The files

| file | what it is |
|---|---|
| `run_eval.py` | the golden-set harness — tier 1, and tier 2 behind `--judge` |
| `assertions.py` | the tier-1 checker. Assertions live as **data** in `../data/eval_golden_set.json` |
| `tracing.py` | the `@traced` decorator and the JSONL log everything else reads |
| `repeat.py` | runs one case N times and measures how much the *path* moved |
| `lab_prompt_injection.py` | the security lab: a poisoned alarm description |
| `solution_scope_guard.py` | the worked answer to **Your turn** below |

---

## Two tiers, cheapest first

**Tier 1 — deterministic assertions.** What did the agent *do*? Which tools it
called, in what order, what severity it asked for, which documents it retrieved.
Runs in microseconds, costs nothing, and is never wrong.

**Tier 2 — LLM-as-a-judge.** Only for what tier 1 cannot express: does the
recommended action actually follow from the stated cause.

> If a property can be expressed as an assertion, do not send it to a model to
> judge. The model is slower, costs money, and is occasionally wrong about
> something a two-line comparison gets right every time.

The ordering is the lesson, and `solution_scope_guard.py` is the proof: on the
EVAL-02 failure, tier 1 caught it and the judge scored the same answer top marks
against a rubric whose 5 reads "zero hallucination". The judge is shown the
agent's *text*, never its *trace* — and the text was excellent. **Tier 1 grades
what the agent did; tier 2 grades what it said.** Run it yourself rather than
quoting either score; both move with the model.

### The bar, and the exit code

The bar is set before you look at the score: **100% of tier-1 assertions on every
case** — not 90% — and ≥4/5 from the judge when it runs.

`run_eval.py` exits **0** when the bar is met and **1** when it is not, so
`python run_eval.py && deploy` means something. A suite that only prints is a
dashboard; wire it into CI and the build stays green through any regression you
ship.

---

## What the offline path does and does not mock

`--mock` replaces **the model**, and nothing else. The tool traces are real runs,
recorded verbatim — and every `create_ticket` in them is replayed through the
real `../data/guardrails.py` when the suite runs.

That distinction is the module in miniature. This file used to mock the
guardrails too, which meant a green offline run said nothing whatsoever about
whether the gate worked — the exact defect this course keeps teaching: **a safety
claim that does not trace to the path that executes.**

So a green `--mock` run tells you the *harness* works. Only a live run tells you
the *agent* does.

---

## Guardrails

`../data/guardrails.py` implements the containment layers from the lecture:

1. **Privilege separation** — `READ_ONLY_TOOLS` run autonomously; `MUTATING_TOOLS`
   (`create_ticket`, `set_tx_power`, `adjust_antenna_tilt`) require human approval.
2. **Deterministic schema bounds** — Pydantic validates every tool argument
   *before* dispatch. `set_tx_power` is hard-bounded to 10–46 dBm; no prompt
   wording talks its way past it.
3. **Scope** — a ticket's site must be the site under investigation. Reading a
   neighbour's KPIs does not authorise filing against it.
4. **Severity ceiling** — derived from the alarm feed, not chosen by the model. A
   ticket cannot be more severe than the worst active alarm on its site.
5. **Prompt-injection hardening** — `wrap_untrusted()` isolates alarm text and
   ticket bodies in tagged blocks so operator-supplied text reads as data.

```bash
python ../data/guardrails.py   # watch six calls, three of them blocked
```

Rules 3 and 4 run in `noc_assistant._dispatch_tool` **before** the human approval
prompt. A person should never be shown a proposal that code can already prove is
out of bounds — that is how an approval gate degrades into a rubber stamp.

---

## Your turn

### 1. Break the gate and watch the suite catch it

Confirm it is green first:

```bash
python run_eval.py ; echo "exit=$?"     # exit=0
```

Now open `../data/guardrails.py`, find the scope check in
`check_ticket_proposal()`, and comment it out. Run it again.

EVAL-02 goes red and the exit code becomes 1 — **with no API key**. Put the rule
back and it goes green.

That is a regression test. Note what did *not* change: the agent. It proposes the
same out-of-scope `CRITICAL` either way. Measured three runs in a row, it proposed
it every single time. The only thing standing between that proposal and a filed
ticket is two rules in code.

### 2. Read what the agent actually did

```bash
python repeat.py --runs 5
python tracing.py --show --run 2
```

Compare the paths. The conclusion is usually stable; the path is not. Then run
`--prompt naive` and `--mode chained` and watch which intervention buys a better
*number* and which buys a better *guarantee*.

**Do not quote a compliance rate you have not measured on your own key.** The
numbers move with the model.

### 3. Add a case of your own

Assertions are data. Add a case to `../data/eval_golden_set.json` — no Python —
and make it fail first. A case you have never seen fail is a case you have not
tested.

### 4. Run the security lab

```bash
python lab_prompt_injection.py
python lab_prompt_injection.py --clean
```

Every guardrail before this one defends against the model being *wrong*. This one
is about someone making it wrong. Tool output is untrusted input.

---

**Next:** Module 11 puts every piece together — and Failure Lab #4 is where the
capstone gets it wrong, and this harness catches it.
