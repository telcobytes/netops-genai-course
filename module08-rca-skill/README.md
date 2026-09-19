# Module 8 — The Telecom RCA Skill

A portable Skill bundle: instructions (`SKILL.md`) plus tools (`tools.py`),
packaged once so any compatible agent loads the procedure instead of re-deriving
it in every prompt.

The content is not new — it is Module 3's prompting and Module 6's tool calling.
**What is new is that it is a file rather than a paragraph somebody retypes.**

---

## How to run

```bash
export GEMINI_API_KEY="..."
cd module08-rca-skill

python run_skill.py              # CELL-031A, the congested cell
python run_skill.py CELL-022A    # a healthy cell
```

No offline mode: without a key it prints how to set one and stops. Set
`AUTO_APPROVE=1` to skip the interactive approval prompt.

**What you should see:** the agent works the 4-layer order from `SKILL.md` —
Physical/RF, then Transport, then Radio Access, then Core — and returns an RCA in
the Impact / Likely cause / Recommended action shape. The wording changes every
run; the *order* and the *shape* should not. Those are what the Skill is buying.

---

## What the file actually is

`SKILL.md` has YAML frontmatter (`name`, `description`) and a body. The
description is not decoration — it is how a host decides whether this Skill is
relevant to the conversation at all. A vague description is a Skill that never
loads.

```
---
name: telecom-rca
description: Diagnose a NetOps Co. cell/site performance issue and draft an RCA...
---
```

## Using it with Claude (Agent Skills)

Copy this folder into your Skills directory (see Claude's Agent Skills docs for
the current path) and reference it by name — `telecom-rca`. The host loads
`SKILL.md` when a conversation matches its `description`.

## Using it with your own agent code (any provider)

You do not need a platform Skills feature to get the benefit:

```python
# Read the procedure once, at agent startup
with open("SKILL.md") as f:
    rca_skill_instructions = f.read()

system_prompt = f"{your_base_system_prompt}\n\n{rca_skill_instructions}"

from tools import get_cell_kpis, get_active_alarms, lookup_topology, create_ticket
```

That is all `run_skill.py` does. Read it — it is 190 lines and there is no magic.

---

## The gate is here too, and that is the point

`run_skill.py` does **not** hand `create_ticket` straight to the tool. It runs the
same two checks Module 6 put in front of the human, in the same order:

1. `guardrails.validate_tool_args()` — the schema. Bad arguments are refused
   before anything is dispatched, returning `refused_by_schema`.
2. `guardrails.check_ticket_proposal()` — the policy: in scope, and no more severe
   than the alarm feed supports. Returns `refused_by_guardrail`.
3. Only then is a human asked.

This matters more than it looks. A later module must never quietly weaken an
earlier module's lesson, and a student who copies this dispatcher into their own
work inherits whatever it does here. **A person should never be asked to approve
something code can already prove is wrong** — that is how an approval gate decays
into a rubber stamp.

---

## Your turn

1. **Break the procedure and watch what survives.** Delete the 4-layer order from
   `SKILL.md`, keep everything else, and run `CELL-031A` three times. The RCA will
   still read well. Check whether it still checks neighbours before blaming the
   cell that is alarming — Module 11's `noc_copilot.py --no-skill` measures exactly
   this, and the answer there was 2 runs out of 3.
2. **Sharpen the `description`.** Rewrite it to be *narrower* and see whether a
   host still loads it for an RCA question. Discovery is the half of Skills that
   nobody tests.
3. **Add a fifth tool to `tools.py`** and reference it from `SKILL.md`. Notice that
   the Skill and the tool list are two separate things that must agree — and that
   nothing enforces the agreement.

---

**Next:** Module 9 — the same tools, exposed over a protocol instead of imported.
