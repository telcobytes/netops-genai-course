# Module 9 — Model Context Protocol (MCP)

This module implements the Model Context Protocol (MCP) using the official MCP Python SDK.

---

## The two primitives this server implements

MCP defines three: Tools, Resources and Prompts. This server implements the first
two, which is enough to make the point — and the third is left out deliberately
rather than forgotten.

1. **Tools (`@mcp.tool()`)** — executable functions the agent *chooses* to call:
   - `get_cell_kpis_tool`
   - `get_active_alarms_tool`
   - `lookup_topology_tool`
   - `create_ticket_tool` — validates its arguments against `data/guardrails.py`
     and returns `refused_by_schema` on a bad call. **The server owns the schema;
     the host owns the approval.** A server cannot ask your user anything.
2. **Resources (`@mcp.resource()`)** — read-only, URI-addressable context the host
   can pull without the agent deciding anything:
   - `telecom://topology` — the network topology graph, no custom parsing code.

**Prompts** are the third primitive: server-managed templates a host can offer to
a user. NetOps Co.'s RCA template is exactly that shape — and it already lives in
`module08-rca-skill/SKILL.md`, loaded as a Skill. Exposing the same text twice
would teach packaging, not protocol. Adding it is the exercise below.

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
Restart your client. The four tools and the topology resource become available
to that host — and to any other compliant host, without writing a second adapter.
That is the M×N → M+N argument, made concrete.

---

## Your turn

1. **Call a tool with the wrong argument type** and read the protocol-level error.
   Seeing the schema enforced at the boundary is worth more than another
   explanation of it.
2. **Add the third primitive.** Expose `module08-rca-skill/SKILL.md` as an
   `@mcp.prompt()` and call it from `mcp_client.py`. Then ask the question that
   matters: is this better delivered as an MCP Prompt or as a Skill file, and
   who has to agree for each one to work?
