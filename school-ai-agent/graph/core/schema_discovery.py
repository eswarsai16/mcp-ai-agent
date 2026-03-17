"""
Dynamically discover all available tools from MCP server.
No hardcoded school logic - works with any MCP API.
"""
import asyncio
import json
from typing import Dict, List, Any
from .mcp_client import MCPClient


class SchemaDiscovery:
    """Discovers available tools from MCP server dynamically."""
    
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self._schema_cache = None
    
    async def get_available_tools(self) -> Dict[str, Any]:
        """
        Get all available tools from MCP server.
        Returns tool definitions that the LLM can choose from.
        """
        if self._schema_cache is not None:
            return self._schema_cache
        
        try:
            # Try to get tools from MCP server
            tools = []
            
            # Method 1: Try list_tools (standard MCP method)
            if hasattr(self.mcp_client, 'list_tools'):
                tools = await self.mcp_client.list_tools()
            
            # Method 2: Try call_tool_direct (if available)
            elif hasattr(self.mcp_client, 'call_tool_direct'):
                # Try to get schema via introspection
                try:
                    response = await self.mcp_client.call_tool_direct("schema", {})
                    if isinstance(response, dict) and "tools" in response:
                        tools = response["tools"]
                except:
                    pass
            
            # If still no tools, try to infer from error messages
            if not tools:
                print("Warning: Could not discover tools via standard methods")
                tools = await self._infer_tools_from_server()
            
            # Convert MCP format to LLM tool format
            formatted_tools = self._format_tools_for_llm(tools)
            self._schema_cache = formatted_tools
            
            return formatted_tools
            
        except Exception as e:
            print(f"Error discovering tools: {e}")
            return []
    
    async def _infer_tools_from_server(self) -> List[Dict]:
        """Try to infer tools by querying the server."""
        try:
            # Some MCP servers respond to a list request
            if hasattr(self.mcp_client, 'call_tool'):
                # Try generic list call
                result = await self.mcp_client.call_tool("_list", {})
                if isinstance(result, dict) and "tools" in result:
                    return result["tools"]
        except:
            pass
        return []
    
    def _format_tools_for_llm(self, mcp_tools: List[Dict]) -> List[Dict]:
        """
        Convert MCP tool definitions to LLM tool format.
        Generic - works for any MCP server.
        """
        tools = []
        for tool in mcp_tools:
            formatted_tool = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {}).get("properties", {}),
                "required": tool.get("inputSchema", {}).get("required", []),
            }
            tools.append(formatted_tool)
        
        return tools
    
    def clear_cache(self):
        """Clear the schema cache to force fresh discovery."""
        self._schema_cache = None
