"""
tools.py — the tools this Skill bundle expects to have access to.

Re-exports the four mock tools from data/mock_tools.py so an agent loading this
Skill folder has everything referenced in SKILL.md in one place, without having
to know where the shared data lives.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from mock_tools import (  # noqa: F401,E402
    get_cell_kpis,
    get_active_alarms,
    lookup_topology,
    create_ticket,
)

__all__ = ["get_cell_kpis", "get_active_alarms", "lookup_topology", "create_ticket"]
