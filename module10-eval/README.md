# Module 10 — Evaluation, Observability & Tracing

This module implements quantitative regression testing and observability for telecom AI agents before they touch live alarms.

---

## 3-Tier Evaluation Architecture

1. **Deterministic Trace Assertions:** Verifies operational order (e.g. verifying that `lookup_topology` was called before `create_ticket`).
2. **Heuristic Smoke Tests:** Fast keyword checks for quick regression catching during local development.
3. **LLM-as-a-Judge Scoring:** Uses a secondary model with structured 1–5 rubrics to evaluate semantic root-cause accuracy without brittle regex.

---

## How to Run

### Tier 1: Deterministic Trace Assertions & Observability
Instruments tools with the `@traced` decorator, writes microsecond-precision execution logs to `trace_log.jsonl`, and programmatically asserts that diagnostic read tools precede mutating action tools:
```bash
python tracing.py
```

### Tier 2: Heuristic Smoke Tests
Fast keyword and logic assertions on golden-set incident scenarios:
```bash
export GEMINI_API_KEY="..."
python run_eval.py
```
*(Runs automatically in offline `--mock` mode if `GEMINI_API_KEY` is not yet configured).*

### Tier 3: Quantitative LLM-as-a-Judge Benchmark
Uses an automated auditor model with 1–5 rubrics to grade technical root cause accuracy, neighbor check compliance, and safety:
```bash
python run_eval.py --judge
```

### Explicit Offline Testing
```bash
python run_eval.py --mock
python run_eval.py --judge --mock
```


---

## Two tiers, cheapest first

This module now grades in two explicit tiers, and the ordering is the lesson.

**Tier 1 — deterministic assertions (`assertions.py`).** What did the agent *do*?
Which tools it called, in what order, what severity it asked for, which documents
it retrieved. Runs in microseconds, costs nothing, and is never wrong. The
assertions live as **data** in `../data/eval_golden_set.json`, so adding a case
means editing JSON — not Python.

**Tier 2 — LLM-as-a-judge.** Only for what tier 1 cannot express: does the
recommended action actually follow from the stated cause.

> If a property can be expressed as an assertion, do not send it to a model to
> judge. The model is slower, costs money, and is occasionally wrong about
> something a two-line comparison gets right every time.

```bash
python run_eval.py            # tier 1 only — no API key needed
python run_eval.py --judge    # both tiers
```

## Guardrails

`../data/guardrails.py` implements the three containment layers from the lecture:

1. **Privilege separation** — `READ_ONLY_TOOLS` run autonomously; `MUTATING_TOOLS`
   (`create_ticket`, `set_tx_power`, `adjust_antenna_tilt`) require human approval.
2. **Deterministic schema bounds** — Pydantic models validate every tool argument
   *before* dispatch. `set_tx_power` is hard-bounded to 10–46 dBm; no prompt
   wording can talk its way past it.
3. **Prompt-injection hardening** — `wrap_untrusted()` isolates alarm text and
   ticket bodies in tagged blocks so operator-supplied text reads as data.

```bash
python ../data/guardrails.py   # watch six calls, three of them blocked
```
