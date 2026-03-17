"""
Generic conversation agent - formats responses generically.
No school knowledge, works with any MCP tool result.
Always includes actual data in responses.
"""
import json
import os
from typing import Dict, Any
try:
    from langchain_ollama import OllamaLLM
except ImportError:
    # Fallback to old import if langchain-ollama not installed
    from langchain_community.llms import Ollama as OllamaLLM


class ConversationAgent:
    """Formats tool execution results into natural language responses."""
    
    def __init__(self, model: str = None, ollama_url: str = "http://localhost:11434"):
        if model is None:
            model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.llm = OllamaLLM(model=model, base_url=ollama_url, temperature=0)
    
    def _format_data_readable(self, data: Any, indent: int = 0) -> str:
        """Format data in a human-readable way."""
        prefix = "  " * indent
        
        if isinstance(data, dict):
            if not data:
                return "{}"
            
            # Check if it's a single data object (not a list)
            if "data" in data and isinstance(data["data"], dict):
                # Single record
                result = []
                for key, value in data["data"].items():
                    if isinstance(value, (dict, list)):
                        result.append(f"{prefix}{key}: {json.dumps(value, indent=2)}")
                    else:
                        result.append(f"{prefix}{key}: {value}")
                return "\n".join(result)
            
            elif "data" in data and isinstance(data["data"], list):
                # List of records
                items = data["data"]
                if not items:
                    return "No data found"
                
                result = []
                result.append(f"{prefix}Found {len(items)} record(s):\n")
                
                for idx, item in enumerate(items, 1):
                    if isinstance(item, dict):
                        result.append(f"{prefix}[{idx}]")
                        for key, value in item.items():
                            if isinstance(value, (dict, list)):
                                result.append(f"{prefix}  {key}: {json.dumps(value)}")
                            else:
                                result.append(f"{prefix}  {key}: {value}")
                    else:
                        result.append(f"{prefix}[{idx}] {item}")
                    
                    if idx < len(items):
                        result.append("")
                
                return "\n".join(result)
            else:
                # Generic dict formatting
                result = []
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        result.append(f"{prefix}{key}:")
                        result.append(self._format_data_readable(value, indent + 1))
                    else:
                        result.append(f"{prefix}{key}: {value}")
                return "\n".join(result)
        
        elif isinstance(data, list):
            if not data:
                return "No data found"
            
            result = [f"{prefix}Found {len(data)} item(s):\n"]
            for idx, item in enumerate(data, 1):
                if isinstance(item, dict):
                    result.append(f"{prefix}[{idx}]")
                    for key, value in item.items():
                        result.append(f"{prefix}  {key}: {value}")
                else:
                    result.append(f"{prefix}[{idx}] {item}")
                
                if idx < len(data):
                    result.append("")
            
            return "\n".join(result)
        
        else:
            return str(data)
    
    async def format_response(
        self,
        user_request: str,
        execution_result: Dict[str, Any]
    ) -> str:
        """
        Format execution result into a natural language response.
        Generic - works with any tool result. Always includes actual data.
        Differentiates between READ (GET), DELETE, CREATE, UPDATE operations.
        """
        
        if not execution_result.get("success"):
            error = execution_result.get("error", "Unknown error")
            return f"❌ Error: {error}"
        
        result_data = execution_result.get("result")
        tool_used = execution_result.get("tool_used", "").lower()
        
        # Determine operation type from tool name
        operation_type = self._infer_operation_type(tool_used)
        
        # Generic response formatting
        if result_data is None:
            if "delete" in operation_type:
                return f"✓ Successfully deleted the record."
            elif "create" in operation_type:
                return f"✓ Successfully created the resource."
            elif "update" in operation_type:
                return f"✓ Successfully updated the record."
            else:
                return "Operation completed successfully but returned no data."
        
        # If result is already a string, return it
        if isinstance(result_data, str):
            return result_data
        
        # Format based on operation type
        try:
            # Extract structured content if available
            if isinstance(result_data, dict) and "structuredContent" in result_data:
                data_to_format = result_data.get("structuredContent", result_data)
            else:
                data_to_format = result_data
            
            if "delete" in operation_type:
                # For delete operations, show what was deleted with a success note
                formatted_data = self._format_data_readable(data_to_format)
                return f"✓ Successfully deleted the following record:\n\n{formatted_data}"
            
            elif "create" in operation_type:
                # For create operations, show the created object
                formatted_data = self._format_data_readable(data_to_format)
                return f"✓ Successfully created:\n\n{formatted_data}"
            
            elif "update" in operation_type:
                # For update operations, show the updated object
                formatted_data = self._format_data_readable(data_to_format)
                return f"✓ Successfully updated:\n\n{formatted_data}"
            
            else:
                # For read operations, just show the data
                formatted_data = self._format_data_readable(data_to_format)
                return formatted_data
        
        except Exception as e:
            # Fallback to JSON
            return json.dumps(result_data, indent=2)
    
    def _infer_operation_type(self, tool_name: str) -> str:
        """Infer operation type from tool name."""
        tool_lower = tool_name.lower()
        
        if any(x in tool_lower for x in ["delete", "remove", "drop"]):
            return "delete"
        elif any(x in tool_lower for x in ["create", "add", "insert", "new"]):
            return "create"
        elif any(x in tool_lower for x in ["update", "edit", "modify", "set", "change"]):
            return "update"
        else:
            return "read"
    
    async def summarize(self, data: Any) -> str:
        """Summarize data generically (no domain knowledge)."""
        if isinstance(data, list):
            return f"Retrieved {len(data)} items"
        elif isinstance(data, dict):
            return f"Retrieved object with {len(data)} fields"
        else:
            return str(data)
