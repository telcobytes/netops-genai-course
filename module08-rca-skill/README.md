# Module 8 — The Telecom RCA Skill

This folder is a portable "Skill" bundle: instructions (`SKILL.md`) + tools
(`tools.py`), packaged once so any compatible agent can load it instead of
re-deriving the same RCA procedure from scratch every time.

## Using this with Claude (Agent Skills)

Copy this folder into your Skills directory (see Claude's Agent Skills docs for
the current path) and reference it by name (`telecom-rca`). Claude will load
`SKILL.md`'s instructions automatically whenever a conversation matches its
`description` field.

## Using this with your own agent code (any provider)

You don't need a platform-specific "Skills" feature to benefit from the pattern:

```python
# Read the procedure once, at agent startup
with open("SKILL.md") as f:
    rca_skill_instructions = f.read()

# Feed it into your agent's system prompt, then use the tools it references
from tools import get_cell_kpis, get_active_alarms, lookup_topology, create_ticket

system_prompt = f"{your_base_system_prompt}\n\n{rca_skill_instructions}"
```

## Running the Skill in Python

You can run this skill directly:

```bash
export GEMINI_API_KEY="..."

# Run on the congested cell:
python run_skill.py CELL-031A

# Run on a healthy cell:
python run_skill.py CELL-022A
```

`run_skill.py` reads `SKILL.md`, injects the 4-layer diagnostic order into the agent's prompt, and invokes the tools defined in `tools.py` via native function calling. Notice how the final RCA strictly conforms to the 3-part layout (Impact, Likely cause, Recommended action) specified in `SKILL.md`.

