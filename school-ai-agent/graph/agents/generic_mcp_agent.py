import asyncio
import json
import os
import re
from typing import Any, Dict, List

try:
    from langchain_ollama import OllamaLLM
except ImportError:
    from langchain_community.llms import Ollama as OllamaLLM

from ..core.decision_parsing import (
    DecisionParser,
    extract_arguments,
    extract_error_message,
    extract_final_text,
    extract_tool_name,
    looks_like_error,
    normalize_action,
)
from ..core.mcp_client import MCPClient
from ..core.schema_discovery import SchemaDiscovery


class GenericMCPAgent:
    def __init__(
        self,
        mcp_url: str = "http://localhost:4000/mcp",
        model: str = None,
        ollama_url: str = "http://localhost:11434",
    ):
        if model is None:
            model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.mcp_client = MCPClient(mcp_url)
        self.schema_discovery = SchemaDiscovery(self.mcp_client)
        self.llm = OllamaLLM(model=model, base_url=ollama_url, temperature=0)
        self.parser = DecisionParser()
        self.max_retries = 2

    async def execute(self, user_request: str, context: Dict = None) -> Dict[str, Any]:
        """
        Execute a user request by:
        1. Discovering available tools from MCP
        2. Selecting a tool with the LLM
        3. Normalizing and validating arguments against the schema
        4. Executing the tool and repairing validation errors when possible
        5. Returning a generic result or clarification
        """
        available_tools = await self.schema_discovery.get_available_tools()

        if not available_tools:
            return {
                "success": False,
                "error": "No tools available from MCP server",
                "user_request": user_request,
            }

        decision = await self._get_llm_decision(
            user_request=user_request,
            available_tools=available_tools,
            context=context or {},
        )

        action = decision.get("action", "tool")
        if action == "final":
            return {
                "success": True,
                "result": decision.get("response", ""),
                "tool_used": decision.get("tool"),
                "user_request": user_request,
            }

        if action == "clarify":
            return {
                "success": False,
                "needs_clarification": True,
                "clarification_question": decision.get("question") or "What information should I use?",
                "tool_used": decision.get("tool"),
                "user_request": user_request,
            }

        if decision.get("error"):
            return {
                "success": False,
                "error": decision.get("error"),
                "user_request": user_request,
            }

        tool_name = decision.get("tool")
        available_tool_names = {tool["name"] for tool in available_tools}

        if not tool_name:
            return {
                "success": False,
                "error": f"No tool selected. Available tools: {', '.join(sorted(available_tool_names))}",
                "user_request": user_request,
            }

        if tool_name not in available_tool_names:
            similar = [
                tool
                for tool in available_tool_names
                if tool_name.lower() in tool.lower() or tool.lower() in tool_name.lower()
            ]
            if similar:
                tool_name = similar[0]
            else:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found. Available: {', '.join(sorted(available_tool_names))}",
                    "user_request": user_request,
                }

        tool_meta = self._find_tool_metadata(tool_name, available_tools)
        if tool_meta is None:
            return {
                "success": False,
                "error": f"Tool metadata for '{tool_name}' was not found.",
                "user_request": user_request,
            }

        normalized_args, clarification = await self._resolve_arguments(
            user_request=user_request,
            tool_meta=tool_meta,
            proposed_args=decision.get("args", {}),
        )

        if clarification:
            return {
                "success": False,
                "needs_clarification": True,
                "clarification_question": clarification,
                "tool_used": tool_name,
                "user_request": user_request,
            }

        tool_result = await self._execute_tool(
            user_request=user_request,
            tool_meta=tool_meta,
            args=normalized_args,
            retry_count=0,
        )

        return {
            "success": tool_result.get("success", True),
            "result": tool_result.get("result"),
            "error": tool_result.get("error"),
            "tool_used": tool_name,
            "user_request": user_request,
            "needs_clarification": tool_result.get("needs_clarification", False),
            "clarification_question": tool_result.get("clarification_question"),
        }

    def _find_tool_metadata(self, tool_name: str, available_tools: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        for tool in available_tools:
            if tool.get("name") == tool_name:
                return tool
        return None

    def _build_tool_schema_text(self, available_tools: List[Dict[str, Any]]) -> str:
        """Build a compact schema description for each tool."""
        schema_lines: List[str] = []

        for tool in available_tools:
            schema_lines.append(f"Tool: {tool['name']}")
            schema_lines.append(f"  Description: {tool.get('description', 'N/A')}")

            for section_name in ("params", "query", "body"):
                section_meta = tool.get("sections", {}).get(section_name, {})
                fields = section_meta.get("fields", {})
                if not fields:
                    continue

                schema_lines.append(f"  {section_name}:")
                for field_name, field_meta in fields.items():
                    required_label = "required" if field_meta.get("required") else "optional"
                    field_type = field_meta.get("type", "unknown")
                    field_desc = field_meta.get("description", "")
                    line = f"    - {field_name} ({field_type}, {required_label})"
                    if field_meta.get("pattern"):
                        line += f", pattern={field_meta['pattern']}"
                    if field_desc:
                        line += f": {field_desc}"
                    schema_lines.append(line)

            schema_lines.append("")

        return "\n".join(schema_lines)

    def _split_identifier_tokens(self, value: str) -> List[str]:
        spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value or "")
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", spaced)
        return [token.lower() for token in cleaned.split() if token]

    def _request_tokens(self, user_request: str) -> List[str]:
        return [token.lower() for token in re.findall(r"[A-Za-z]+[0-9]*|[0-9]+", user_request or "")]

    def _request_identifier_tokens(self, user_request: str) -> List[str]:
        return [token.lower() for token in re.findall(r"\b[A-Za-z]+[0-9]+\b", user_request or "")]

    def _request_context_tokens(self, user_request: str) -> set[str]:
        pairs = re.findall(r"\b([A-Za-z]+)\s+([A-Za-z]+[0-9]+|[0-9]+)\b", user_request or "", re.IGNORECASE)
        return {word.lower() for word, _ in pairs if word}

    def _tool_action_category(self, tool_name: str) -> str:
        lowered = (tool_name or "").lower()
        if any(token in lowered for token in ("average", "avg", "count", "summary", "total")):
            return "aggregate"
        if lowered.startswith(("create", "add", "insert", "new")):
            return "create"
        if lowered.startswith(("update", "edit", "modify", "change", "set")):
            return "update"
        if lowered.startswith(("delete", "remove", "drop")):
            return "delete"
        return "read"

    def _request_action_category(self, user_request: str) -> str:
        tokens = set(self._request_tokens(user_request))
        if tokens.intersection({"create", "add", "insert", "new"}):
            return "create"
        if tokens.intersection({"update", "edit", "modify", "change", "set", "rename"}):
            return "update"
        if tokens.intersection({"delete", "remove", "drop"}):
            return "delete"
        if tokens.intersection({"average", "avg", "mean", "count", "total", "summary"}):
            return "aggregate"
        return "read"

    def _tool_required_field_count(self, tool_meta: Dict[str, Any]) -> int:
        return sum(len(section_meta.get("required_fields", [])) for section_meta in tool_meta.get("sections", {}).values())

    def _tool_tokens(self, tool_meta: Dict[str, Any]) -> set[str]:
        tokens = set(self._split_identifier_tokens(tool_meta.get("name", "")))
        tokens.update(self._split_identifier_tokens(tool_meta.get("description", "")))
        for section_meta in tool_meta.get("sections", {}).values():
            for field_name, field_meta in section_meta.get("fields", {}).items():
                tokens.update(self._split_identifier_tokens(field_name))
                for alias in field_meta.get("aliases", []):
                    tokens.update(self._split_identifier_tokens(alias))
        return {token for token in tokens if token}

    def _tool_entity_tokens(self, tool_meta: Dict[str, Any]) -> List[str]:
        stop = {
            "get",
            "create",
            "update",
            "delete",
            "remove",
            "add",
            "insert",
            "new",
            "edit",
            "modify",
            "change",
            "set",
            "by",
            "for",
            "and",
            "or",
            "id",
            "average",
            "avg",
            "count",
            "summary",
            "total",
        }
        return [token for token in self._split_identifier_tokens(tool_meta.get("name", "")) if token not in stop]

    def _tool_filter_tokens(self, tool_meta: Dict[str, Any]) -> List[str]:
        tokens = self._split_identifier_tokens(tool_meta.get("name", ""))
        if "by" not in tokens:
            return []

        by_index = tokens.index("by")
        return [token for token in tokens[by_index + 1 :] if token not in {"and", "or", "id"}]

    def _score_tool_for_request(self, user_request: str, tool_meta: Dict[str, Any]) -> int:
        request_tokens = set(self._request_tokens(user_request))
        identifier_tokens = self._request_identifier_tokens(user_request)
        request_context_tokens = self._request_context_tokens(user_request)
        tool_tokens = self._tool_tokens(tool_meta)
        tool_name = tool_meta.get("name", "")
        tool_action = self._tool_action_category(tool_name)
        request_action = self._request_action_category(user_request)
        required_count = self._tool_required_field_count(tool_meta)
        score = 0

        if request_action == tool_action:
            score += 60
        elif request_action == "aggregate" and tool_action == "read":
            score -= 20
        elif request_action != tool_action:
            score -= 45

        stop = {
            "get",
            "create",
            "update",
            "delete",
            "remove",
            "add",
            "insert",
            "new",
            "edit",
            "modify",
            "change",
            "set",
            "show",
            "fetch",
            "pull",
            "give",
            "details",
            "detail",
            "profile",
            "record",
            "all",
            "list",
            "only",
            "with",
            "for",
            "the",
            "a",
            "an",
            "to",
            "of",
            "in",
            "on",
            "by",
        }
        overlap = (request_tokens & tool_tokens) - stop
        score += 12 * len(overlap)

        request_has_list_hint = bool(request_tokens.intersection({"all", "list", "every"}))
        request_has_detail_hint = bool(
            request_tokens.intersection({"detail", "details", "profile", "fetch", "show", "get", "pull", "record", "only"})
        )

        if tool_action == "read":
            if request_has_list_hint:
                score += 25 if required_count == 0 else -10
            if request_has_detail_hint:
                score += 25 if required_count > 0 else -12
            if identifier_tokens:
                score += 18 if required_count > 0 else -8

        entity_tokens = set(self._tool_entity_tokens(tool_meta))
        score += 8 * len((request_tokens & entity_tokens) - stop)

        filter_tokens = self._tool_filter_tokens(tool_meta)
        if filter_tokens:
            present_filters = len(set(filter_tokens) & request_tokens)
            absent_filters = len(set(filter_tokens) - request_tokens)
            score += 14 * present_filters
            score -= 10 * absent_filters

        if "id" in self._split_identifier_tokens(tool_name) and request_has_detail_hint and identifier_tokens:
            score += 20

        if request_context_tokens:
            tool_context_tokens = entity_tokens | set(filter_tokens)
            score += 16 * len(request_context_tokens & tool_context_tokens)
            if tool_action == "read":
                score -= 12 * len(request_context_tokens - tool_context_tokens)
                if len(request_context_tokens) > 1 and request_context_tokens.issubset(tool_context_tokens):
                    score += 40

        if any(token in tool_tokens for token in {"average", "avg"}) and request_tokens.intersection({"average", "avg", "mean"}):
            score += 45

        return score

    def _select_tool_name(
        self,
        user_request: str,
        available_tools: List[Dict[str, Any]],
        llm_tool_name: str | None,
    ) -> str | None:
        if not available_tools:
            return llm_tool_name

        scored_tools = sorted(
            (
                (self._score_tool_for_request(user_request, tool), tool.get("name"))
                for tool in available_tools
                if tool.get("name")
            ),
            key=lambda item: item[0],
            reverse=True,
        )

        heuristic_tool = scored_tools[0][1] if scored_tools else None
        heuristic_score = scored_tools[0][0] if scored_tools else float("-inf")

        if llm_tool_name:
            llm_score = next(
                (score for score, name in scored_tools if name == llm_tool_name),
                float("-inf"),
            )
            if heuristic_tool and heuristic_tool != llm_tool_name and heuristic_score >= llm_score + 15:
                return heuristic_tool
            return llm_tool_name

        if heuristic_tool and heuristic_score > 0:
            return heuristic_tool

        return None

    def _is_id_like_field(self, field_name: str, field_meta: Dict[str, Any]) -> bool:
        normalized_name = field_meta.get("normalized_name") or self._normalize_key(field_name)
        return normalized_name == "id" or normalized_name.endswith("id") or bool(field_meta.get("pattern"))

    def _coerce_number_value(self, value: Any, integer_only: bool) -> Any:
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            if integer_only:
                return int(value) if float(value).is_integer() else value
            return value

        if isinstance(value, str):
            number_text = value.strip().strip(",")
            if integer_only:
                if re.fullmatch(r"[-+]?\d+", number_text):
                    return int(number_text)
                return value

            if re.fullmatch(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)", number_text):
                return float(number_text) if "." in number_text else int(number_text)

        return value

    def _coerce_boolean_value(self, value: Any) -> Any:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "1"}:
                return True
            if lowered in {"false", "no", "0"}:
                return False

        return value

    def _coerce_value_for_field(self, field_meta: Dict[str, Any], candidate: Any) -> Any:
        if candidate is None:
            return None

        value = candidate
        if isinstance(value, str):
            value = value.strip().strip(".,")
            if not value:
                return None

        field_type = str(field_meta.get("type") or "").lower()
        if field_type == "integer":
            return self._coerce_number_value(value, integer_only=True)
        if field_type == "number":
            return self._coerce_number_value(value, integer_only=False)
        if field_type == "boolean":
            return self._coerce_boolean_value(value)

        if not isinstance(value, str):
            value = str(value)

        pattern = field_meta.get("pattern")
        if not pattern:
            return value

        try:
            if re.fullmatch(pattern, value):
                return value
        except re.error:
            return value

        return value

    def _extract_value_after_alias(self, user_request: str, aliases: List[str]) -> str | None:
        lowered = user_request.lower()
        ordered_aliases = sorted(
            {alias.lower() for alias in aliases if alias},
            key=lambda alias: (len(alias.split()), len(alias)),
            reverse=True,
        )

        for alias in ordered_aliases:
            match = re.search(rf"\b{re.escape(alias)}\b", lowered)
            if not match:
                continue
            tail = user_request[match.end():]
            candidate_match = re.match(r"\s*(?:(?:is|=|:)\s*)?([A-Za-z]+[0-9]+)\b", tail, re.IGNORECASE)
            if candidate_match:
                return candidate_match.group(1)

        return None

    def _apply_request_hints(
        self,
        user_request: str,
        tool_meta: Dict[str, Any],
        args: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        augmented_args = {
            "params": dict(args.get("params", {})),
            "query": dict(args.get("query", {})),
            "body": dict(args.get("body", {})),
        }

        for section_name, section_values in augmented_args.items():
            fields = tool_meta.get("sections", {}).get(section_name, {}).get("fields", {})
            for field_name, value in list(section_values.items()):
                field_meta = fields.get(field_name, {})
                coerced_existing = self._coerce_value_for_field(field_meta, value)
                if coerced_existing is not None:
                    section_values[field_name] = coerced_existing

        identifier_tokens = self._request_identifier_tokens(user_request)
        missing_fields = self._find_missing_required_fields(tool_meta, augmented_args)
        missing_id_like_count = sum(
            1
            for missing in missing_fields
            if self._is_id_like_field(
                missing["field"],
                tool_meta.get("sections", {}).get(missing["section"], {}).get("fields", {}).get(missing["field"], {}),
            )
        )

        for missing in missing_fields:
            section_name = missing["section"]
            field_name = missing["field"]
            field_meta = tool_meta.get("sections", {}).get(section_name, {}).get("fields", {}).get(field_name, {})
            aliases = list(field_meta.get("aliases", []))

            if self._is_id_like_field(field_name, field_meta) and field_name == "id":
                aliases.extend(self._tool_entity_tokens(tool_meta))

            candidate = None
            if self._is_id_like_field(field_name, field_meta):
                candidate = self._extract_value_after_alias(user_request, aliases)
                if candidate is None and len(identifier_tokens) == 1 and missing_id_like_count == 1:
                    candidate = identifier_tokens[0]

            coerced = self._coerce_value_for_field(field_meta, candidate)
            if coerced is not None:
                augmented_args[section_name][field_name] = coerced

        return augmented_args

    def _normalize_arguments(self, tool_meta: Dict[str, Any], proposed_args: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        normalized_args: Dict[str, Dict[str, Any]] = {
            "params": {},
            "query": {},
            "body": {},
        }

        if not isinstance(proposed_args, dict):
            return normalized_args

        for key, value in proposed_args.items():
            if key in normalized_args and isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    if not self._assign_argument(
                        target_args=normalized_args,
                        tool_meta=tool_meta,
                        key=nested_key,
                        value=nested_value,
                        source_section=key,
                    ):
                        normalized_args[key][nested_key] = nested_value
            else:
                if not self._assign_argument(
                    target_args=normalized_args,
                    tool_meta=tool_meta,
                    key=key,
                    value=value,
                    source_section=None,
                ):
                    normalized_args["body"][key] = value

        return normalized_args

    def _assign_argument(
        self,
        target_args: Dict[str, Dict[str, Any]],
        tool_meta: Dict[str, Any],
        key: str,
        value: Any,
        source_section: str | None,
    ) -> bool:
        if value is None:
            return False

        sections = tool_meta.get("sections", {})
        if source_section and key in sections.get(source_section, {}).get("fields", {}):
            target_args[source_section][key] = value
            return True

        exact_matches = [
            {"section": section_name, "name": key}
            for section_name, section_meta in sections.items()
            if key in section_meta.get("fields", {})
        ]
        chosen = self._choose_candidate(tool_meta, exact_matches, source_section)
        if chosen:
            target_args[chosen["section"]][chosen["name"]] = value
            return True

        normalized_key = self._normalize_key(key)
        alias_matches = tool_meta.get("field_index", {}).get(normalized_key, [])
        chosen = self._choose_candidate(tool_meta, alias_matches, source_section)
        if chosen:
            target_args[chosen["section"]][chosen["name"]] = value
            return True

        return False

    def _choose_candidate(
        self,
        tool_meta: Dict[str, Any],
        candidates: List[Dict[str, str]],
        source_section: str | None,
    ) -> Dict[str, str] | None:
        if not candidates:
            return None

        if source_section:
            same_section = [candidate for candidate in candidates if candidate["section"] == source_section]
            if len(same_section) == 1:
                return same_section[0]

        if len(candidates) == 1:
            return candidates[0]

        sections = tool_meta.get("sections", {})
        required = [
            candidate
            for candidate in candidates
            if sections.get(candidate["section"], {})
            .get("fields", {})
            .get(candidate["name"], {})
            .get("required")
        ]
        if len(required) == 1:
            return required[0]

        for preferred_section in ("params", "query", "body"):
            section_candidates = [
                candidate for candidate in candidates if candidate["section"] == preferred_section
            ]
            if len(section_candidates) == 1:
                return section_candidates[0]

        return None

    def _normalize_key(self, key: str) -> str:
        return "".join(ch for ch in (key or "").lower() if ch.isalnum())

    def _find_missing_required_fields(
        self,
        tool_meta: Dict[str, Any],
        args: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        missing: List[Dict[str, Any]] = []

        for section_name, section_meta in tool_meta.get("sections", {}).items():
            for field_name in section_meta.get("required_fields", []):
                value = args.get(section_name, {}).get(field_name)
                if value is None or (isinstance(value, str) and not value.strip()):
                    field_meta = section_meta.get("fields", {}).get(field_name, {})
                    missing.append(
                        {
                            "section": section_name,
                            "field": field_name,
                            "type": field_meta.get("type", "unknown"),
                            "description": field_meta.get("description", ""),
                        }
                    )

        return missing

    def _build_missing_fields_error(self, missing_fields: List[Dict[str, Any]]) -> str:
        labels = [f"{item['section']}.{item['field']}" for item in missing_fields]
        return f"Missing required fields: {', '.join(labels)}"

    def _build_clarification_question(
        self,
        tool_name: str,
        missing_fields: List[Dict[str, Any]],
    ) -> str:
        labels = [f"{item['section']}.{item['field']}" for item in missing_fields]

        if len(labels) == 1:
            return f"I can use {tool_name}, but I still need {labels[0]}. What value should I use?"

        joined = ", ".join(labels)
        return f"I can use {tool_name}, but I still need these values: {joined}. What should I use?"

    async def _resolve_arguments(
        self,
        user_request: str,
        tool_meta: Dict[str, Any],
        proposed_args: Dict[str, Any],
        error_message: str | None = None,
        retry_count: int = 0,
    ) -> tuple[Dict[str, Dict[str, Any]], str | None]:
        normalized_args = self._normalize_arguments(tool_meta, proposed_args)
        normalized_args = self._apply_request_hints(user_request, tool_meta, normalized_args)
        missing_fields = self._find_missing_required_fields(tool_meta, normalized_args)

        if not missing_fields:
            return normalized_args, None

        if retry_count >= self.max_retries:
            return normalized_args, self._build_clarification_question(tool_meta["name"], missing_fields)

        repair_reason = error_message or self._build_missing_fields_error(missing_fields)
        repaired_args = await self._repair_args(
            tool_meta=tool_meta,
            user_request=user_request,
            args=normalized_args,
            error=repair_reason,
        )
        repaired_normalized = self._normalize_arguments(tool_meta, repaired_args)
        repaired_normalized = self._apply_request_hints(user_request, tool_meta, repaired_normalized)

        if repaired_normalized == normalized_args:
            return normalized_args, self._build_clarification_question(tool_meta["name"], missing_fields)

        return await self._resolve_arguments(
            user_request=user_request,
            tool_meta=tool_meta,
            proposed_args=repaired_normalized,
            retry_count=retry_count + 1,
        )

    async def _get_llm_decision(
        self,
        user_request: str,
        available_tools: List[Dict[str, Any]],
        context: Dict,
    ) -> Dict[str, Any]:
        """
        Generic LLM prompt - no domain knowledge.
        The model selects a tool and proposes raw fields.
        Deterministic normalization happens after this step.
        """
        if not available_tools:
            return {"tool": None, "args": {}}

        schema_text = self._build_tool_schema_text(available_tools)
        available_tool_names = [tool["name"] for tool in available_tools]

        prompt = f"""You are an API client. Pick the best matching tool and extract only the values that are clearly present in the request.

AVAILABLE TOOLS:
{schema_text}

USER REQUEST: "{user_request}"

Return VALID JSON ONLY in one of these forms:
{{"action": "tool", "tool": "EXACT_TOOL_NAME", "arguments": {{"field_name": "value"}}}}
{{"action": "tool", "tool": "EXACT_TOOL_NAME", "arguments": {{"params": {{}}, "query": {{}}, "body": {{}}}}}}
{{"action": "clarify", "tool": "EXACT_TOOL_NAME", "question": "short follow-up question", "missing_required": ["field_name"]}}
{{"action": "final", "response": "message to the user"}}

Rules:
1. The tool name must EXACTLY match one from the list above.
2. Only extract values that are explicitly present in the user request.
3. You may return arguments as flat fields or grouped under params/query/body.
4. If a required value is not present, prefer omitting it instead of guessing.
5. For identifier-like fields (for example id, class_id, studentId), only use a value if the full identifier appears explicitly in the request. Do not invent prefixes or expand partial numeric values.
6. If no tool fits, return action "final" with a short explanation.
"""

        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, lambda: self.llm.invoke(prompt))

        decision = self.parser.parse_decision(response_text)
        if not isinstance(decision, dict):
            decision = {}

        tool_name = extract_tool_name(decision, available_tool_names, response_text)
        tool_name = self._select_tool_name(user_request, available_tools, tool_name)
        raw_action = str(
            decision.get("action")
            or decision.get("act")
            or decision.get("type")
            or decision.get("next_action")
            or ""
        ).strip().lower()

        if raw_action in {"clarify", "question", "ask"} and not tool_name:
            action = "clarify"
        else:
            action = normalize_action(decision, tool_name)

        if action == "final":
            return {
                "action": "final",
                "tool": tool_name,
                "response": extract_final_text(decision),
            }

        if action == "clarify":
            question = str(decision.get("question") or extract_final_text(decision)).strip()
            if not question or question.lower() == "short follow-up question":
                question = "What information should I use?"
            return {
                "action": "clarify",
                "tool": tool_name,
                "question": question,
                "args": extract_arguments(decision),
            }

        if tool_name and tool_name in available_tool_names:
            return {
                "action": "tool",
                "tool": tool_name,
                "args": extract_arguments(decision),
            }

        return {
            "action": "final",
            "tool": None,
            "response": f"I couldn't match that request to a known tool. Available tools: {', '.join(available_tool_names)}",
        }

    async def _execute_tool(
        self,
        user_request: str,
        tool_meta: Dict[str, Any],
        args: Dict[str, Dict[str, Any]],
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Execute a tool via the MCP client and repair validation-style errors when possible.
        """
        tool_name = tool_meta["name"]

        try:
            result = await self.mcp_client.call_tool(tool_name, args)
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
            }

        if looks_like_error(result):
            error_message = extract_error_message(result)

            if retry_count < self.max_retries and self._should_retry_error(error_message):
                repaired_args, clarification = await self._resolve_arguments(
                    user_request=user_request,
                    tool_meta=tool_meta,
                    proposed_args=args,
                    error_message=error_message,
                    retry_count=retry_count,
                )

                if clarification:
                    return {
                        "success": False,
                        "needs_clarification": True,
                        "clarification_question": clarification,
                    }

                if repaired_args != args:
                    return await self._execute_tool(
                        user_request=user_request,
                        tool_meta=tool_meta,
                        args=repaired_args,
                        retry_count=retry_count + 1,
                    )

            return {
                "success": False,
                "error": error_message,
            }

        return {
            "success": True,
            "result": result,
        }

    def _should_retry_error(self, error_message: str) -> bool:
        lowered = (error_message or "").lower()
        return any(
            token in lowered
            for token in (
                "invalid arguments",
                "validation",
                "invalid string",
                "must match pattern",
                "expected",
                "required",
                "received undefined",
                "missing required",
                "params",
                "query",
                "body",
            )
        )

    async def _repair_args(
        self,
        tool_meta: Dict[str, Any],
        user_request: str,
        args: Dict[str, Dict[str, Any]],
        error: str,
    ) -> Dict[str, Any]:
        """
        Generic repair - ask the LLM to fix args using the original request,
        tool schema, current arguments, and validation error.
        """
        schema_text = self._build_tool_schema_text([tool_meta])
        repair_prompt = f"""The tool '{tool_meta['name']}' needs corrected arguments.

USER REQUEST:
{user_request}

TOOL SCHEMA:
{schema_text}

CURRENT ARGUMENTS:
{json.dumps(args)}

ERROR:
{error}

Return ONLY JSON for the corrected arguments.
You may return flat fields or grouped params/query/body.
Do not invent identifier prefixes or expand partial numeric IDs.
Do not add explanations.
"""

        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, lambda: self.llm.invoke(repair_prompt))

        parsed = self.parser.parse_decision(response_text)
        if isinstance(parsed, dict):
            parsed_args = extract_arguments(parsed)
            if isinstance(parsed_args, dict) and parsed_args:
                return parsed_args
            if parsed:
                return parsed

        try:
            raw = json.loads(response_text)
            return raw if isinstance(raw, dict) else args
        except Exception:
            return args
