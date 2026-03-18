"""
Dynamically discover all available tools from an MCP server.
No hardcoded domain logic - works with any MCP API.
"""

import re
from typing import Any, Dict, List

from .mcp_client import MCPClient


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _split_identifier_tokens(value: str) -> List[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value or "")
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", spaced)
    return [token.lower() for token in cleaned.split() if token]


def _build_aliases(field_name: str) -> List[str]:
    tokens = _split_identifier_tokens(field_name)
    aliases = {
        field_name,
        field_name.lower(),
        _normalize_identifier(field_name),
    }

    if tokens:
        singular_tokens = [token[:-1] if token.endswith("s") and len(token) > 3 else token for token in tokens]
        aliases.update(
            {
                " ".join(tokens),
                "_".join(tokens),
                "-".join(tokens),
                "".join(tokens),
                tokens[0] + "".join(token.title() for token in tokens[1:]),
                "".join(token.title() for token in tokens),
                " ".join(singular_tokens),
                "_".join(singular_tokens),
                "-".join(singular_tokens),
                "".join(singular_tokens),
            }
        )

        if tokens[-1] == "id" and len(tokens) > 1:
            base_tokens = tokens[:-1]
            aliases.update(
                {
                    " ".join(base_tokens),
                    "_".join(base_tokens),
                    "-".join(base_tokens),
                    "".join(base_tokens),
                }
            )

    return sorted(alias for alias in aliases if alias)


class SchemaDiscovery:
    """Discovers available tools from an MCP server dynamically."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self._schema_cache = None

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get all available tools from the MCP server.
        Returns tool definitions enriched with section and field metadata.
        """
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            tools: List[Dict[str, Any]] = []

            if hasattr(self.mcp_client, "list_tools"):
                tools = await self.mcp_client.list_tools()
            elif hasattr(self.mcp_client, "call_tool_direct"):
                try:
                    response = await self.mcp_client.call_tool_direct("schema", {})
                    if isinstance(response, dict) and "tools" in response:
                        tools = response["tools"]
                except Exception:
                    pass

            if not tools:
                print("Warning: Could not discover tools via standard methods")
                tools = await self._infer_tools_from_server()

            formatted_tools = self._format_tools_for_llm(tools)
            self._schema_cache = formatted_tools
            return formatted_tools

        except Exception as e:
            print(f"Error discovering tools: {e}")
            return []

    async def _infer_tools_from_server(self) -> List[Dict[str, Any]]:
        """Try to infer tools by querying the server."""
        try:
            if hasattr(self.mcp_client, "call_tool"):
                result = await self.mcp_client.call_tool("_list", {})
                if isinstance(result, dict) and "tools" in result:
                    return result["tools"]
        except Exception:
            pass
        return []

    def _build_section_metadata(self, section_name: str, section_schema: Dict[str, Any]) -> Dict[str, Any]:
        section_schema = section_schema if isinstance(section_schema, dict) else {}
        field_schemas = section_schema.get("properties", {})
        required_fields = set(section_schema.get("required", []))

        fields: Dict[str, Any] = {}
        for field_name, field_schema in field_schemas.items():
            if not isinstance(field_schema, dict):
                field_schema = {}

            aliases = _build_aliases(field_name)
            fields[field_name] = {
                "name": field_name,
                "section": section_name,
                "type": field_schema.get("type", "unknown"),
                "description": field_schema.get("description", ""),
                "pattern": field_schema.get("pattern"),
                "format": field_schema.get("format"),
                "required": field_name in required_fields,
                "normalized_name": _normalize_identifier(field_name),
                "aliases": aliases,
            }

        return {
            "name": section_name,
            "required_fields": sorted(required_fields),
            "fields": fields,
        }

    def _build_field_index(self, sections: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
        field_index: Dict[str, List[Dict[str, str]]] = {}
        seen: set[tuple[str, str, str]] = set()

        for section_name, section_meta in sections.items():
            for field_name, field_meta in section_meta.get("fields", {}).items():
                for alias in field_meta.get("aliases", []):
                    normalized_alias = _normalize_identifier(alias)
                    if not normalized_alias:
                        continue
                    marker = (normalized_alias, section_name, field_name)
                    if marker in seen:
                        continue
                    seen.add(marker)
                    field_index.setdefault(normalized_alias, []).append({"section": section_name, "name": field_name})

        return field_index

    def _format_tools_for_llm(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert MCP tool definitions to a richer internal format.
        Generic - works for any MCP server.
        """
        tools: List[Dict[str, Any]] = []

        for tool in mcp_tools:
            input_schema = tool.get("inputSchema", {}) if isinstance(tool, dict) else {}
            properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}

            sections = {
                section_name: self._build_section_metadata(section_name, properties.get(section_name, {}))
                for section_name in ("params", "query", "body")
            }

            formatted_tool = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "inputSchema": input_schema,
                "parameters": properties,
                "required": input_schema.get("required", []) if isinstance(input_schema, dict) else [],
                "sections": sections,
                "field_index": self._build_field_index(sections),
            }
            tools.append(formatted_tool)

        return tools

    def clear_cache(self):
        """Clear the schema cache to force fresh discovery."""
        self._schema_cache = None
