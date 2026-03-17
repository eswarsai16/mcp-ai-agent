import requests
import uuid
import asyncio
from typing import Dict, Any, List

MCP_URL = "http://localhost:4000/mcp"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _rpc(method: str, params: dict | None = None):
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }

    if params:
        payload["params"] = params

    res = requests.post(MCP_URL, json=payload, headers=HEADERS, timeout=30)

    if res.status_code != 200:
         return {"error": f"MCP HTTP {res.status_code}: {res.text}"}

    data = res.json()

    if "error" in data:
        return {"error": data["error"]}

    return data["result"]


def list_tools():
    return _rpc("tools/list", {}).get("tools", [])


def call_tool(name: str, arguments: dict):
    return _rpc("tools/call", {"name": name, "arguments": arguments})


class MCPClient:
    """Client for communicating with MCP server."""
    
    def __init__(self, mcp_url: str = "http://localhost:4000/mcp"):
        self.mcp_url = mcp_url
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, list_tools)
        return result if isinstance(result, list) else []
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, call_tool, name, arguments)
        return result if isinstance(result, dict) else {"error": "Invalid response"}
    
    async def call_tool_direct(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool directly (alias for call_tool)."""
        return await self.call_tool(name, arguments)