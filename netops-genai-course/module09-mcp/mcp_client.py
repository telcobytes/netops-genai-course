"""
mcp_client.py — Module 8 hands-on: connect to mcp_server.py as an MCP client

This plays the HOST + CLIENT side of the architecture: it starts mcp_server.py
as a subprocess, speaks MCP to it over stdio, lists the tools & resources it exposes,
and calls one — illustrating the "any compatible host can connect" idea from the lecture.

Requires: pip install mcp

Run:
    python mcp_client.py
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "mcp_server.py")


async def main():
    server_params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Inspect MCP Tools
            tools = await session.list_tools()
            print("--- Tools Exposed by MCP Server ---")
            for tool in tools.tools:
                print(f"  [Tool] {tool.name}: {tool.description.split('.')[0]}")

            # 2. Inspect MCP Resources
            resources = await session.list_resources()
            print("\n--- Resources Exposed by MCP Server ---")
            for res in resources.resources:
                print(f"  [Resource] {res.uri}: {res.name}")

            # 3. Execute an MCP Tool Call
            print("\n--- Executing Tool: get_cell_kpis_tool(cell_id='CELL-031A') ---")
            result = await session.call_tool(
                "get_cell_kpis_tool", arguments={"cell_id": "CELL-031A"}
            )
            print(result.content[0].text if result.content else result)


if __name__ == "__main__":
    asyncio.run(main())
