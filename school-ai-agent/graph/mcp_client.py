import requests
import uuid

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