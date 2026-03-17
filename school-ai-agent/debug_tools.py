"""Debug script to list available tools from MCP server."""
import asyncio
from graph.core.mcp_client import MCPClient

async def main():
    client = MCPClient("http://localhost:4000/mcp")
    
    print("Attempting to discover tools from MCP server...")
    try:
        tools = await client.list_tools()
        print(f"\nFound {len(tools)} tools:")
        for tool in tools:
            print(f"\n  Tool: {tool}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
