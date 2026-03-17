#!/usr/bin/env python
"""Debug script to see what tools are available from MCP server."""
import asyncio
import json
from graph.core.mcp_client import MCPClient
from graph.core.schema_discovery import SchemaDiscovery

async def main():
    # Create client and discovery
    mcp_client = MCPClient("http://localhost:4000/mcp")
    schema_discovery = SchemaDiscovery(mcp_client)
    
    # Get available tools
    print("Discovering tools from MCP server...")
    tools = await schema_discovery.get_available_tools()
    
    print(f"\nFound {len(tools)} tools")
    
    if tools:
        print("\n✓ Available tool names:")
        for tool in tools:
            name = tool.get('name', 'UNKNOWN')
            desc = tool.get('description', '')[:60]
            print(f"  - {name:20} | {desc}")
            # Show parameters if they exist
            if tool.get('parameters'):
                print(f"      Parameters: {list(tool['parameters'].keys())}")
    else:
        print("\n✗ No tools discovered!")

if __name__ == "__main__":
    asyncio.run(main())

