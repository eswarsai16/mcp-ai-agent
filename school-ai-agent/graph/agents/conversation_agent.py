"""
Generic conversation agent - formats responses generically.
No domain knowledge, works with any MCP tool result.
Always includes actual data in responses.
"""

import json
import os
from typing import Any, Dict

try:
    from langchain_ollama import OllamaLLM
except ImportError:
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

            if "data" in data and isinstance(data["data"], dict):
                result = []
                for key, value in data["data"].items():
                    if isinstance(value, (dict, list)):
                        result.append(f"{prefix}{key}: {json.dumps(value, indent=2)}")
                    else:
                        result.append(f"{prefix}{key}: {value}")
                return "\n".join(result)

            if "data" in data and isinstance(data["data"], list):
                items = data["data"]
                if not items:
                    return "No data found"

                result = [f"{prefix}Found {len(items)} record(s):\n"]
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

            result = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    result.append(f"{prefix}{key}:")
                    result.append(self._format_data_readable(value, indent + 1))
                else:
                    result.append(f"{prefix}{key}: {value}")
            return "\n".join(result)

        if isinstance(data, list):
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

        return str(data)

    async def format_response(
        self,
        user_request: str,
        execution_result: Dict[str, Any],
    ) -> str:
        """
        Format execution result into a natural language response.
        Generic - works with any tool result. Always includes actual data.
        Differentiates between read/write operations and clarification prompts.
        """
        if execution_result.get("needs_clarification"):
            return execution_result.get("clarification_question", "What value should I use?")

        if not execution_result.get("success"):
            error = execution_result.get("error", "Unknown error")
            return f"Error: {error}"

        result_data = execution_result.get("result")
        tool_used = str(execution_result.get("tool_used") or "")
        operation_type = self._infer_operation_type(tool_used)

        if isinstance(result_data, str):
            return result_data

        if isinstance(result_data, dict) and result_data.get("structuredContent") is not None:
            data_to_format = result_data.get("structuredContent", result_data)
        else:
            data_to_format = result_data

        if isinstance(data_to_format, dict) and set(data_to_format.keys()) == {"items"}:
            data_to_format = data_to_format["items"]

        if isinstance(data_to_format, dict) and data_to_format.get("ok") is True and len(data_to_format) == 1:
            return self._format_simple_success(operation_type)

        if result_data is None:
            return self._format_simple_success(operation_type)

        try:
            formatted_data = self._format_data_readable(data_to_format)
            if operation_type == "delete" and self._has_displayable_payload(data_to_format):
                return f"Successfully deleted the following record:\n\n{formatted_data}"
            if operation_type == "create" and self._has_displayable_payload(data_to_format):
                return f"Successfully created:\n\n{formatted_data}"
            if operation_type == "update" and self._has_displayable_payload(data_to_format):
                return f"Successfully updated:\n\n{formatted_data}"
            return formatted_data
        except Exception:
            return json.dumps(result_data, indent=2)

    def _infer_operation_type(self, tool_name: str) -> str:
        """Infer operation type from tool name."""
        tool_lower = str(tool_name or "").lower()

        if any(token in tool_lower for token in ["delete", "remove", "drop"]):
            return "delete"
        if any(token in tool_lower for token in ["create", "add", "insert", "new"]):
            return "create"
        if any(token in tool_lower for token in ["update", "edit", "modify", "set", "change"]):
            return "update"
        return "read"

    def _format_simple_success(self, operation_type: str) -> str:
        if operation_type == "delete":
            return "Successfully deleted the record."
        if operation_type == "create":
            return "Successfully created the resource."
        if operation_type == "update":
            return "Successfully updated the record."
        return "Operation completed successfully."

    def _has_displayable_payload(self, data: Any) -> bool:
        if data is None:
            return False
        if isinstance(data, dict):
            return bool(data)
        if isinstance(data, list):
            return len(data) > 0
        return True

    async def summarize(self, data: Any) -> str:
        """Summarize data generically (no domain knowledge)."""
        if isinstance(data, list):
            return f"Retrieved {len(data)} items"
        if isinstance(data, dict):
            return f"Retrieved object with {len(data)} fields"
        return str(data)
