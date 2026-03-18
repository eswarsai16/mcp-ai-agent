import asyncio
import uuid
from typing import Any, Dict, List

import requests

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _format_rpc_error(error: Any) -> str:
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message") or str(error)
        if code is not None:
            return f"MCP error {code}: {message}"
        return f"MCP error: {message}"
    return str(error)


def _rpc(mcp_url: str, method: str, params: dict | None = None):
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }

    if params is not None:
        payload["params"] = params

    res = requests.post(mcp_url, json=payload, headers=HEADERS, timeout=30)

    if res.status_code != 200:
        return {"error": f"MCP HTTP {res.status_code}: {res.text}"}

    data = res.json()

    if "error" in data:
        return {"error": _format_rpc_error(data["error"])}

    return data.get("result", {})


def list_tools(mcp_url: str):
    result = _rpc(mcp_url, "tools/list", {})
    return result.get("tools", []) if isinstance(result, dict) else []


def call_tool(mcp_url: str, name: str, arguments: dict):
    return _rpc(mcp_url, "tools/call", {"name": name, "arguments": arguments})


class MCPClient:
    """Client for communicating with an MCP server."""

    def __init__(self, mcp_url: str = "http://localhost:4000/mcp"):
        self.mcp_url = mcp_url

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the configured MCP server."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, list_tools, self.mcp_url)
        return result if isinstance(result, list) else []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the configured MCP server."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, call_tool, self.mcp_url, name, arguments)
        return result if isinstance(result, dict) else {"error": "Invalid response"}

    async def call_tool_direct(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool directly (alias for call_tool)."""
        return await self.call_tool(name, arguments)
