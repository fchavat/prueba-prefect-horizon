"""Minimal FastMCP server for Prefect Horizon.

This version is intended to be deployed on Prefect Horizon (https://prefect.io/horizon).
Horizon provides the HTTP transport, TLS, and OAuth 2.1 gateway, so this file
contains only the MCP server definition and tools.

Horizon entry point:
    horizon_server.py:mcp

Do not add `if __name__ == "__main__":` blocks or start a server manually —
Horizon manages the execution lifecycle.
"""

from fastmcp import FastMCP

mcp = FastMCP("sum-server")


@mcp.tool()
async def sum(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a + b
