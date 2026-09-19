"""
mcp_server.py — Module 9 hands-on: expose the NOC tools via MCP

Requires the official MCP Python SDK:
    pip install mcp

This is the SERVER half of MCP's host/client/server architecture: it exposes
get_cell_kpis, get_active_alarms, lookup_topology, and create_ticket as MCP
tools, plus topology as an MCP Resource — so ANY MCP-compatible host
(Claude Desktop, an IDE, your own agent code) can connect to them.

Supports both modern mcp 2.x (`MCPServer`) and legacy mcp 1.x (`FastMCP`).

Run directly (for a quick manual check):
    python mcp_server.py

Connect it to Claude Desktop by adding to your claude_desktop_config.json:
    {
      "mcpServers": {
        "netops-noc-tools": {
          "command": "python",
          "args": ["/absolute/path/to/mcp_server.py"]
        }
      }
    }
Then restart Claude Desktop — the tools and resources below become available in any chat.
"""

from __future__ import annotations
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
import guardrails  # noqa: E402
from mock_tools import (  # noqa: E402
    get_cell_kpis,
    get_active_alarms,
    lookup_topology,
    create_ticket,
    _load_json,
)

try:
    # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    try:
        # mcp 1.x
        from mcp.server.fastmcp import FastMCP
    except (ImportError, ModuleNotFoundError):
        print("The 'mcp' package isn't installed. Run: pip install mcp")
        raise

mcp = FastMCP("netops-noc-tools")


# --- MCP Primitives: Tools (Executable Actions) ---

@mcp.tool()
def get_cell_kpis_tool(cell_id: str, window_minutes: int = 60) -> dict:
    """Get a COMPUTED KPI summary for a cell: rolling averages, deltas, and which
    operational thresholds are currently crossed. The tool does the arithmetic."""
    return get_cell_kpis(cell_id, window_minutes)


@mcp.tool()
def get_active_alarms_tool(site_id: str = "") -> list:
    """Get active alarms, optionally filtered to one site."""
    return get_active_alarms(site_id or None)


@mcp.tool()
def lookup_topology_tool(node_id: str) -> dict:
    """Get topology info (neighbors, vendor, planned capacity) for a site or cell."""
    result = lookup_topology(node_id)
    return result or {"error": f"No topology entry found for {node_id}"}


@mcp.tool()
def create_ticket_tool(summary: str, site_id: str = "", category: str = "Uncategorized",
                       severity: str = "MINOR") -> dict:
    """Open a trouble ticket. MOCK — no real side effect in this course repo.

    The argument schema is enforced HERE, in the server, and that is the point of
    the module: once a tool is exposed over a protocol, any compatible host can
    call it — Claude Desktop, someone else's agent, a script. The guard has to
    travel with the tool, because you no longer control the caller.

    Approval is the part that cannot live here: this process is a subprocess
    speaking stdio, with no human attached. In a real deployment the host owns
    the approval gate (Module 6) and the server owns the schema.
    """
    try:
        args = guardrails.validate_tool_args("create_ticket", {
            "summary": summary, "site_id": site_id,
            "category": category, "severity": severity})
    except guardrails.GuardrailError as err:
        return {"status": "refused_by_schema", "reason": str(err)}
    return create_ticket(**args)


# --- MCP Primitives: Resources (Read-Only Context Streams) ---

@mcp.resource("telecom://topology")
def get_network_topology() -> str:
    """Provides full network topology graph as a readable MCP Resource stream."""
    return json.dumps(_load_json("topology.json"), indent=2)


if __name__ == "__main__":
    mcp.run()
