"""
Generic MCP agent - behaves exactly like Copilot + mcp.json.
No school-specific logic. Works with any MCP server.
"""
import asyncio
import json
import os
from typing import Any, Dict, List
try:
    from langchain_ollama import OllamaLLM
except ImportError:
    # Fallback to old import if langchain-ollama not installed
    from langchain_community.llms import Ollama as OllamaLLM
from ..core.mcp_client import MCPClient
from ..core.schema_discovery import SchemaDiscovery
from ..core.decision_parsing import DecisionParser


class GenericMCPAgent:
    """
    Generic agent that mirrors Copilot + mcp.json behavior.
    
    1. Discover tools dynamically from MCP schema
    2. Let LLM choose tool + args
    3. Execute tool
    4. Repair only on validation errors
    5. Return result generically
    """
    
    def __init__(self, mcp_url: str = "http://localhost:4000/mcp", model: str = None, ollama_url: str = "http://localhost:11434"):
        if model is None:
            model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.mcp_client = MCPClient(mcp_url)
        self.schema_discovery = SchemaDiscovery(self.mcp_client)
        self.llm = OllamaLLM(model=model, base_url=ollama_url, temperature=0)
        self.parser = DecisionParser()
        self.max_retries = 2
    
    async def execute(self, user_request: str, context: Dict = None) -> Dict[str, Any]:
        """
        Execute user request by:
        1. Getting available tools from MCP schema
        2. Asking LLM to pick a tool
        3. Executing the tool
        4. Repairing on validation errors
        5. Returning generic result
        """
        # Step 1: Discover available tools
        available_tools = await self.schema_discovery.get_available_tools()
        
        if not available_tools:
            return {
                "success": False,
                "error": "No tools available from MCP server",
                "user_request": user_request
            }
        
        # Step 2: Generic prompt - LLM doesn't know about schools
        decision = await self._get_llm_decision(
            user_request=user_request,
            available_tools=available_tools,
            context=context or {}
        )
        
        # Check if decision contains an error
        if decision.get("error"):
            return {
                "success": False,
                "error": decision.get("error"),
                "user_request": user_request
            }
        
        # Validate tool name exists in available tools
        tool_name = decision.get("tool")
        available_tool_names = {t["name"] for t in available_tools}
        
        if not tool_name:
            return {
                "success": False,
                "error": f"No tool selected. Available tools: {', '.join(sorted(available_tool_names))}",
                "user_request": user_request
            }
        
        if tool_name not in available_tool_names:
            # Try fuzzy matching or suggest alternatives
            similar = [t for t in available_tool_names if tool_name.lower() in t.lower() or t.lower() in tool_name.lower()]
            if similar:
                tool_name = similar[0]  # Use the most similar tool
            else:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found. Available: {', '.join(sorted(available_tool_names))}",
                    "user_request": user_request
                }
        
        # Step 3: Execute tool
        tool_result = await self._execute_tool(
            tool=tool_name,
            args=decision.get("args", {}),
            retry_count=0
        )
        
        # Step 4: Generic summarization
        return {
            "success": tool_result.get("success", True),
            "result": tool_result.get("result"),
            "error": tool_result.get("error"),
            "tool_used": tool_name,
            "user_request": user_request
        }
    
    def _build_tool_schema_text(self, available_tools: List[Dict]) -> str:
        """Build detailed schema description for each tool."""
        schema_lines = []
        for tool in available_tools:
            schema_lines.append(f"Tool: {tool['name']}")
            schema_lines.append(f"  Description: {tool.get('description', 'N/A')}")
            
            params = tool.get('parameters', {})
            for section in ['params', 'query', 'body']:
                section_schema = params.get(section, {})
                if section_schema and isinstance(section_schema, dict):
                    section_props = section_schema.get('properties', {})
                    if section_props:
                        schema_lines.append(f"  {section}:")
                        for field_name, field_schema in section_props.items():
                            field_type = field_schema.get('type', 'unknown')
                            field_desc = field_schema.get('description', '')
                            schema_lines.append(f"    - {field_name} ({field_type}): {field_desc}")
            schema_lines.append("")
        
        return "\n".join(schema_lines)

    async def _get_llm_decision(
        self, 
        user_request: str, 
        available_tools: List[Dict],
        context: Dict
    ) -> Dict[str, Any]:
        """
        Generic LLM prompt - no school knowledge.
        LLM simply picks tool from schema + fills in args.
        """
        if not available_tools:
            return {"tool": None, "args": {}}
        
        # Build detailed schema text
        schema_text = self._build_tool_schema_text(available_tools)
        available_tool_names = [t['name'] for t in available_tools]
        
        prompt = f"""You are an API client. Analyze the request and pick the best matching tool, then fill in the required arguments.

AVAILABLE TOOLS AND THEIR PARAMETERS:
{schema_text}

USER REQUEST: "{user_request}"

INSTRUCTIONS:
1. Pick the tool name that EXACTLY matches one from the list above (case-sensitive)
2. Extract parameter values from the user request
3. Place parameters in the correct section (params/query/body) based on the schema above
4. Return the response in this JSON format ONLY:
{{"tool": "TOOL_NAME", "args": {{"params": {{}}, "query": {{}}, "body": {{}}}}}}

EXAMPLES:
- Request "get all items" → {{"tool": "listItems", "args": {{"params": {{}}, "query": {{}}, "body": {{}}}}}}
- Request "get item with id x101" → {{"tool": "getItemById", "args": {{"params": {{"id": "x101"}}, "query": {{}}, "body": {{}}}}}}
- Request "create a new thing with id x77 and name thing77" → {{"tool": "createThing", "args": {{"params": {{}}, "query": {{}}, "body": {{"id": "x77", "name": "thing77"}}}}}}
- Request "delete record with id rec456" → {{"tool": "deleteRecord", "args": {{"params": {{"id": "rec456"}}, "query": {{}}, "body": {{}}}}}}

Your response must be VALID JSON with NO other text."""

        # Call LLM
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None,
            lambda: self.llm.invoke(prompt)
        )
        
        # Parse response
        try:
            decision = json.loads(response_text)
            picked_tool = decision.get("tool", "")
            
            # Validate the tool name exists
            if picked_tool not in available_tool_names:
                # Try to find a close match
                close_matches = [t for t in available_tool_names if t.lower().startswith(picked_tool.lower())]
                if close_matches:
                    decision["tool"] = close_matches[0]
                else:
                    # Return error with available tools
                    return {
                        "tool": None,
                        "args": {},
                        "error": f"Tool '{picked_tool}' not found. Available: {', '.join(available_tool_names)}"
                    }
            
            return decision
        
        except json.JSONDecodeError:
            # Try to extract JSON from response
            parsed = self.parser.extract_json(response_text)
            if parsed and "tool" in parsed:
                picked_tool = parsed.get("tool", "")
                if picked_tool in available_tool_names:
                    return parsed
            
            # Last resort: return error
            return {
                "tool": None,
                "args": {},
                "error": f"Could not parse LLM response. Got: {response_text[:200]}"
            }
    
    async def _execute_tool(
        self,
        tool: str,
        args: Dict,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Execute tool via MCP client.
        Generic - doesn't care what tool or what domain.
        """
        try:
            # Call MCP server - it validates args
            result = await self.mcp_client.call_tool(tool, args)
            
            return {
                "success": True,
                "result": result
            }
        
        except ValueError as e:
            # Validation error - try to repair
            if retry_count < self.max_retries and "validation" in str(e).lower():
                repaired_args = await self._repair_args(tool, args, str(e))
                return await self._execute_tool(
                    tool=tool,
                    args=repaired_args,
                    retry_count=retry_count + 1
                )
            
            return {
                "success": False,
                "error": str(e)
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }
    
    async def _repair_args(
        self,
        tool: str,
        args: Dict,
        error: str
    ) -> Dict:
        """
        Generic repair - ask LLM to fix args based on validation error.
        No domain knowledge needed.
        """
        repair_prompt = f"""The tool '{tool}' rejected the arguments with this error:

{error}

Original arguments: {json.dumps(args)}

Fix the arguments to match what the error message says. Return ONLY the corrected JSON arguments, no explanation."""

        # Use invoke in executor (Ollama doesn't support ainvoke)
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None,
            lambda: self.llm.invoke(repair_prompt)
        )
        
        try:
            return json.loads(response_text)
        except:
            return args  # If repair fails, return original
