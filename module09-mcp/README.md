# Module 9 — Model Context Protocol (MCP)

This module implements the Model Context Protocol (MCP) using the official MCP Python SDK.

---

## The 3 MCP Primitives Demonstrated Here

1. **Tools (`@mcp.tool()`):** Executable functions that take parameters and perform operations:
   - `get_cell_kpis_tool`
   - `get_active_alarms_tool`
   - `lookup_topology_tool`
   - `create_ticket_tool` (gated in production)
2. **Resources (`@mcp.resource()`):** Read-only URI-addressable telemetry streams:
   - `telecom://topology` — exposes the live network topology graph without custom parsing code.
3. **Prompts:** Standardized, server-managed interaction templates (e.g. NetOps Co.'s RCA template).

---

## How to Run

### 1. Test Client + Server over stdio:
```bash
python mcp_client.py
```
This automatically boots `mcp_server.py` as a subprocess, inspects exposed tools and resources over JSON-RPC, and calls `get_cell_kpis_tool`.

### 2. Connect to Claude Desktop or Antigravity IDE:
Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "netops-noc-tools": {
      "command": "python",
      "args": ["/absolute/path/to/repo/module09-mcp/mcp_server.py"]
    }
  }
}
```
Restart your client. All four tools and the topology resource become instantly available to your agent!
