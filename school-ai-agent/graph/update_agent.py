from graph.mcp_client import list_tools, call_tool
from graph.state import AgentState
from langchain_ollama import ChatOllama
import json
import re
from typing import Any

llm = ChatOllama(model="qwen2.5:3b", temperature=0)

MAX_STEPS = 6
MAX_REPEAT_SAME_CALL = 2


# ===================================================
# Build Compact Tool Schema Summary
# ===================================================
def build_tool_schema_summary(tools):
    summary = ""

    for tool in tools:
        name = tool.get("name")
        description = tool.get("description", "")
        schema = tool.get("inputSchema", {})

        summary += f"\nTool: {name}\n"
        summary += f"Description: {description}\n"

        props = schema.get("properties", {})

        for section in ["params", "query", "body"]:
            section_schema = props.get(section)

            if isinstance(section_schema, dict):
                fields = section_schema.get("properties", {})
                if fields:
                    summary += f"{section} fields:\n"
                    for field, field_schema in fields.items():
                        ftype = field_schema.get("type", "unknown")
                        summary += f"- {field} ({ftype})\n"

        summary += "\n"

    return summary


def _extract_json_dict(raw: str):
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    if "```" in raw:
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            parsed = json.loads(brace_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    return None


def _find_first_key(obj: dict, candidates: set[str]):
    for key, value in obj.items():
        if str(key).lower() in candidates:
            return value
    return None


def _find_decision_container(payload: Any) -> dict | None:
    if isinstance(payload, dict):
        keys = {str(k).lower() for k in payload.keys()}
        if keys.intersection({"action", "tool", "tool_name", "response", "final", "answer", "message"}):
            return payload

        for value in payload.values():
            nested = _find_decision_container(value)
            if nested:
                return nested

    if isinstance(payload, list):
        for item in payload:
            nested = _find_decision_container(item)
            if nested:
                return nested

    return None


def _parse_decision(raw: str) -> dict | None:
    parsed = _extract_json_dict(raw)
    if parsed:
        container = _find_decision_container(parsed)
        return container or parsed
    return None


def _repair_to_json(raw: str) -> dict | None:
    repair_prompt = f"""
Convert the following content into ONE strict JSON object for an agent decision.

Allowed structures:
1) Tool call:
{{
  "action": "tool",
  "tool": "EXACT_TOOL_NAME",
  "arguments": {{
    "params": {{}},
    "query": {{}},
    "body": {{}}
  }}
}}

2) Final response:
{{
  "action": "final",
  "response": "message"
}}

Return JSON only.
Content:
{raw}
"""
    repaired_raw = llm.invoke(repair_prompt).content.strip()
    return _parse_decision(repaired_raw)


def _extract_tool_name(decision: dict, tool_names: list[str], raw: str) -> str | None:
    tool_value = _find_first_key(decision, {"tool", "tool_name", "function", "name"})
    if isinstance(tool_value, str):
        candidate = tool_value.strip()
        if candidate in tool_names:
            return candidate

    lowered = raw.lower()
    matched = [tool_name for tool_name in tool_names if tool_name.lower() in lowered]
    if len(matched) == 1:
        return matched[0]

    return None


def _extract_arguments(decision: dict):
    args_value = _find_first_key(
        decision,
        {"arguments", "args", "input", "payload", "parameters"},
    )

    if isinstance(args_value, str):
        try:
            args_value = json.loads(args_value)
        except Exception:
            args_value = {}

    if isinstance(args_value, dict):
        return args_value

    direct_params = _find_first_key(decision, {"params"})
    direct_query = _find_first_key(decision, {"query"})
    direct_body = _find_first_key(decision, {"body"})

    if any(v is not None for v in [direct_params, direct_query, direct_body]):
        return {
            "params": direct_params or {},
            "query": direct_query or {},
            "body": direct_body or {},
        }

    return {}


def _extract_final_text(decision: dict) -> str:
    final_text = _find_first_key(decision, {"response", "final", "answer", "message", "text"})
    if isinstance(final_text, str) and final_text.strip():
        return final_text.strip()
    return "Update completed."


def _is_write_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return (
        lowered.startswith("create")
        or lowered.startswith("update")
        or lowered.startswith("delete")
        or lowered.startswith("remove")
    )


def _call_signature(tool: str, args: dict) -> str:
    return f"{tool}|{json.dumps(args, sort_keys=True)}"


def _looks_like_error(result: Any) -> bool:
    if isinstance(result, dict):
        if result.get("isError") is True:
            return True
        if "error" in result:
            return True
        nested = result.get("structuredContent")
        if isinstance(nested, dict) and "error" in nested:
            return True
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).lower()
                    if "mcp error" in text or "invalid arguments" in text:
                        return True
    return False


def _extract_error_message(result: Any) -> str:
    if not isinstance(result, dict):
        return "Tool call failed."

    if isinstance(result.get("error"), str):
        return result["error"]

    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    return text

    nested = result.get("structuredContent")
    if isinstance(nested, dict):
        err = nested.get("error")
        if isinstance(err, str) and err.strip():
            return err.strip()

    return "Tool call failed."


def _extract_object_from_content(result: Any) -> dict | None:
    if isinstance(result, dict):
        payload = result.get("structuredContent")
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            for value in payload.values():
                if isinstance(value, dict):
                    return value
            return payload

        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                text = text.strip()
                if text.startswith("{") and text.endswith("}"):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        continue
    return None


def _build_write_confirmation(tool: str, args: dict, result: Any) -> str:
    payload = _extract_object_from_content(result)
    if isinstance(payload, dict):
        for key in ["student_id", "teacher_id", "class_id", "subject_id", "marks_id", "id", "name"]:
            if payload.get(key):
                return f"{tool} completed successfully for {key}={payload.get(key)}."

    return f"{tool} completed successfully."


def _matches_pattern(value: Any, pattern: str | None) -> bool:
    if not isinstance(value, str) or not pattern:
        return False
    try:
        return re.fullmatch(pattern, value) is not None
    except re.error:
        return False


def _extract_name_from_user(user_text: str, entity: str) -> str | None:
    pattern = rf"\b(?:add|create|insert)\s+{re.escape(entity)}\s+(.+?)(?:\s+in\b|\s+for\b|\s+with\b|$)"
    match = re.search(pattern, user_text, re.IGNORECASE)
    if not match:
        return None
    name = match.group(1).strip().strip("\"'")
    return name if name else None


def _extract_class_id_from_user(user_text: str) -> str | None:
    match = re.search(r"\bclass\s+(c?\d+)\b", user_text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).lower()
    return raw if raw.startswith("c") else f"c{raw}"


def _extract_class_token_from_user(user_text: str) -> str | None:
    match = re.search(r"\bclass\s+([a-zA-Z0-9_]+)\b", user_text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _is_valid_class_token(token: str) -> bool:
    return re.fullmatch(r"c?\d+", token.strip().lower()) is not None


def _extract_id_from_user_by_pattern(user_text: str, pattern: str | None) -> str | None:
    if not pattern:
        return None

    try:
        search_pattern = pattern
        if search_pattern.startswith("^"):
            search_pattern = search_pattern[1:]
        if search_pattern.endswith("$"):
            search_pattern = search_pattern[:-1]
        match = re.search(search_pattern, user_text, re.IGNORECASE)
        if match:
            return match.group(0)
    except re.error:
        return None

    return None


def _coerce_pattern_value(field: str, value: Any, pattern: str | None, user_text: str, body: dict) -> str | None:
    if pattern is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    # Common single-prefix ID patterns like ^c[0-9]+$ / ^s[0-9]+$ / ^t[0-9]+$ / ^m[0-9]+$
    single_prefix = re.match(r"^\^([a-z])[0-9]\+\$$", pattern)
    if single_prefix:
        prefix = single_prefix.group(1)
        digits = re.search(r"\d+", text)
        if digits:
            return f"{prefix}{digits.group(0)}"
        return None

    # Choice-prefix pattern like ^(eng|mat|sci)[0-9]+$
    choice_prefix = re.match(r"^\^\(([^)]+)\)\[0-9\]\+\$$", pattern)
    if choice_prefix:
        choices = [c.strip().lower() for c in choice_prefix.group(1).split("|")]
        digits_match = re.search(r"\d+", text)
        digits = digits_match.group(0) if digits_match else None

        pick = None
        user_l = user_text.lower()
        for c in choices:
            if c in text or c in user_l or c in str(body.get("subject_name", "")).lower():
                pick = c
                break
        if not pick and choices:
            pick = choices[0]

        if pick and digits:
            return f"{pick}{digits}"

    # Special case class_id often arrives as "5" / "class 5"
    if field == "class_id":
        extracted = _extract_class_id_from_user(user_text)
        if extracted:
            return extracted
        digits = re.search(r"\d+", text)
        if digits:
            return f"c{digits.group(0)}"

    return None


def _guess_get_by_id_tool(update_tool: str, tool_names: list[str]) -> str | None:
    suffix = update_tool.replace("update", "", 1)
    candidates = [
        f"get{suffix}ById",
        f"get{suffix}byid",
    ]
    for candidate in candidates:
        if candidate in tool_names:
            return candidate
    return None


def _coerce_typed_value(raw_value: str, field_schema: dict):
    ftype = field_schema.get("type")
    value = raw_value.strip().strip("\"'")
    if ftype == "number":
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    return value


def _extract_field_updates_from_user(user_text: str, body_props: dict) -> dict:
    updates = {}
    lower = user_text.lower()

    # Generic "<field> to <value>" parser for schema fields.
    for field, schema in body_props.items():
        field_label = field.replace("_", " ")
        pattern = rf"\b{re.escape(field_label)}\b\s+to\s+(.+?)(?:\s+\band\b|,|$)"
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            updates[field] = _coerce_typed_value(match.group(1), schema)

    # Friendly natural-language aliases.
    if "name to" in lower:
        match = re.search(r"\bname\s+to\s+(.+?)(?:\s+\band\b|,|$)", user_text, re.IGNORECASE)
        if match:
            for field, schema in body_props.items():
                if field.endswith("name") and schema.get("type") == "string":
                    updates[field] = match.group(1).strip().strip("\"'")
                    break

    if "class" in lower and "class_id" in body_props:
        class_id = _extract_class_id_from_user(user_text)
        if class_id:
            updates["class_id"] = class_id

    return updates


def _extract_prefix_from_pattern(pattern: str | None, user_text: str, body: dict, id_field: str) -> str | None:
    if not pattern:
        return None
    choice_match = re.match(r"^\^\(([^)]+)\)\[0-9\]\+\$$", pattern)
    if choice_match:
        choices = [c.strip() for c in choice_match.group(1).split("|")]
        text = user_text.lower()
        subject_name = str(body.get("subject_name", "")).lower()
        for c in choices:
            if c in text or c in subject_name:
                return c
        existing = body.get(id_field)
        if isinstance(existing, str):
            for c in choices:
                if existing.lower().startswith(c):
                    return c
        return choices[0] if choices else None

    simple_match = re.match(r"^\^([a-z]+)\[0-9\]\+\$$", pattern)
    if simple_match:
        return simple_match.group(1)
    return None


def _guess_list_tool(create_tool: str, tool_names: list[str]) -> str | None:
    special = {
        "createMarks": "getByStudentAndSubject",
    }
    if create_tool in special and special[create_tool] in tool_names:
        return special[create_tool]

    suffix = create_tool.replace("create", "", 1)
    candidates = [f"get{suffix}s", f"get{suffix}es", f"get{suffix}"]
    for candidate in candidates:
        if candidate in tool_names:
            return candidate
    return None


def _extract_rows(result: Any) -> list[dict]:
    if not isinstance(result, dict):
        return []
    if _looks_like_error(result):
        return []
    payload = result.get("structuredContent", result)
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _generate_next_id(
    create_tool: str,
    id_field: str,
    id_pattern: str | None,
    body: dict,
    user_text: str,
    tool_names: list[str],
) -> str | None:
    prefix = _extract_prefix_from_pattern(id_pattern, user_text, body, id_field)
    if not prefix:
        return None

    list_tool = _guess_list_tool(create_tool, tool_names)
    if not list_tool:
        return None

    list_result = call_tool(list_tool, {"params": {}, "query": {}, "body": {}})
    rows = _extract_rows(list_result)
    nums = []
    for row in rows:
        raw = row.get(id_field)
        if not isinstance(raw, str):
            continue
        match = re.match(rf"^{re.escape(prefix)}(\d+)$", raw, re.IGNORECASE)
        if match:
            nums.append(int(match.group(1)))

    if not nums:
        return f"{prefix}1"

    nums = sorted(set(nums))
    # Ignore tiny high-ID tails separated by a huge gap (bad historical inserts).
    if len(nums) >= 3:
        for i in range(len(nums) - 2, -1, -1):
            gap = nums[i + 1] - nums[i]
            tail_count = len(nums) - (i + 1)
            if gap > 1000 and tail_count <= 5:
                return f"{prefix}{nums[i] + 1}"

    return f"{prefix}{nums[-1] + 1}"


def _apply_schema_fixes(
    tool: str,
    clean_args: dict,
    tools_by_name: dict,
    user_text: str,
    tool_names: list[str],
) -> dict:
    lowered_tool = tool.lower()
    if not (
        lowered_tool.startswith("create")
        or lowered_tool.startswith("update")
        or lowered_tool.startswith("delete")
        or lowered_tool.startswith("remove")
    ):
        return clean_args

    tool_def = tools_by_name.get(tool) or {}
    input_schema = tool_def.get("inputSchema", {})
    params_schema = ((input_schema.get("properties") or {}).get("params") or {})
    params_props = params_schema.get("properties") or {}
    body_schema = ((input_schema.get("properties") or {}).get("body") or {})
    body_props = body_schema.get("properties") or {}
    if not body_props and not params_props:
        return clean_args

    fixed = {
        "params": dict(clean_args.get("params") or {}),
        "query": dict(clean_args.get("query") or {}),
        "body": dict(clean_args.get("body") or {}),
    }
    params = fixed["params"]
    body = fixed["body"]

    entity = tool.replace("create", "", 1).replace("update", "", 1).lower()
    id_field = f"{entity}_id" if f"{entity}_id" in body_props else None
    if not id_field:
        id_candidates = [k for k in body_props.keys() if k.endswith("_id")]
        if id_candidates:
            id_field = id_candidates[0]

    name_fields = [k for k, v in body_props.items() if k.endswith("name") and v.get("type") == "string"]
    name_field = name_fields[0] if name_fields else None

    if id_field and lowered_tool.startswith("create"):
        id_pattern = (body_props.get(id_field) or {}).get("pattern")
        current_id = body.get(id_field)

        # If model put person-name into *_id, move it to name when possible.
        if current_id and isinstance(current_id, str) and id_pattern and not _matches_pattern(current_id, id_pattern):
            if name_field and not body.get(name_field):
                body[name_field] = current_id
            body.pop(id_field, None)

        if not body.get(id_field):
            generated = _generate_next_id(tool, id_field, id_pattern, body, user_text, tool_names)
            if generated:
                body[id_field] = generated

    if lowered_tool.startswith("update"):
        params_id_pattern = (params_props.get("id") or {}).get("pattern")
        params_id = params.get("id")

        if params_id and params_id_pattern and not _matches_pattern(params_id, params_id_pattern):
            coerced = _coerce_pattern_value("id", params_id, params_id_pattern, user_text, body)
            if coerced:
                params["id"] = coerced

        if not params.get("id"):
            candidate_id = None
            if id_field and body.get(id_field):
                candidate_id = str(body.get(id_field))
            if (not candidate_id) and params_id_pattern:
                candidate_id = _extract_id_from_user_by_pattern(user_text, params_id_pattern)
            if candidate_id:
                params["id"] = candidate_id

        if id_field and params.get("id") and not body.get(id_field):
            body[id_field] = params["id"]

        # Parse requested field changes from user text.
        updates = _extract_field_updates_from_user(user_text, body_props)
        if updates:
            body.update(updates)

        # PUT endpoints require full payload: fetch current row by id and merge.
        required_fields = body_schema.get("required") or []
        if required_fields and params.get("id"):
            missing_required = [f for f in required_fields if body.get(f) is None]
            if missing_required:
                get_tool = _guess_get_by_id_tool(tool, tool_names)
                if get_tool:
                    current_res = call_tool(
                        get_tool,
                        {"params": {"id": params["id"]}, "query": {}, "body": {}},
                    )
                    current_obj = _extract_object_from_content(current_res) or {}
                    if isinstance(current_obj, dict):
                        merged = dict(current_obj)
                        merged.update(body)
                        body.clear()
                        body.update(merged)

    if lowered_tool.startswith("delete") or lowered_tool.startswith("remove"):
        params_id_pattern = (params_props.get("id") or {}).get("pattern")

        if params.get("id") and params_id_pattern and not _matches_pattern(params.get("id"), params_id_pattern):
            coerced = _coerce_pattern_value("id", params.get("id"), params_id_pattern, user_text, body)
            if coerced:
                params["id"] = coerced

        if not params.get("id"):
            candidate_id = None
            if id_field and body.get(id_field):
                candidate_id = str(body.get(id_field))
            if (not candidate_id) and params_id_pattern:
                candidate_id = _extract_id_from_user_by_pattern(user_text, params_id_pattern)
            if candidate_id:
                params["id"] = candidate_id

    # Normalize/fix invalid patterned fields dynamically from schema.
    for field, field_schema in body_props.items():
        pattern = field_schema.get("pattern")
        if not pattern or field not in body:
            continue
        current = body.get(field)
        if _matches_pattern(current, pattern):
            continue
        coerced = _coerce_pattern_value(field, current, pattern, user_text, body)
        if coerced and _matches_pattern(coerced, pattern):
            body[field] = coerced

    if "class_id" in body_props and not body.get("class_id"):
        class_id = _extract_class_id_from_user(user_text)
        if class_id:
            body["class_id"] = class_id

    if name_field and not body.get(name_field):
        inferred_name = _extract_name_from_user(user_text, entity)
        if inferred_name:
            body[name_field] = inferred_name

    if lowered_tool.startswith("update") and id_field and params.get("id"):
        body[id_field] = params["id"]

    return fixed


def _normalize_action(decision: dict, tool_name: str | None) -> str:
    action_value = _find_first_key(decision, {"action", "act", "type", "next_action"})
    action_raw = str(action_value or "").strip().lower()

    if action_raw in {"tool", "call_tool", "call", "execute"}:
        return "tool"
    if action_raw in {"final", "done", "finish", "complete"}:
        return "final"

    if tool_name:
        return "tool"

    if _find_first_key(decision, {"response", "final", "answer", "message", "text"}):
        return "final"

    return ""


# ===================================================
# Autonomous Update Agent
# ===================================================
def update_agent(state: AgentState) -> AgentState:

    tools = list_tools()

    if not tools:
        state["response"] = "Unable to fetch tools from MCP server."
        return state

    tool_names = [t["name"] for t in tools if t.get("name")]
    tools_by_name = {t.get("name"): t for t in tools if t.get("name")}
    tool_summary = build_tool_schema_summary(tools)

    scratchpad = []
    call_counts = {}

    for _step in range(MAX_STEPS):

        history_block = "\n".join(scratchpad)

        prompt = f"""
You are an autonomous School Database Update Agent.

You MUST use MCP tools to complete the task.

Available tools and schemas:
{tool_summary}

Rules:
- Understand natural English.
- If creating a new record and ID is required:
    1) First call the appropriate GET list tool.
    2) Determine the next unique ID.
    3) Then call the CREATE tool.
- Validate foreign keys if needed by checking relevant GET tools.
- Never guess field names - use schema above.
- Never output explanation text.
- Return STRICT JSON only.

Response format:

If you want to call a tool:
{{
  "action": "tool",
  "tool": "EXACT_TOOL_NAME",
  "arguments": {{
      "params": {{ }},
      "query": {{ }},
      "body": {{ }}
  }}
}}

If task is complete:
{{
  "action": "final",
  "response": "Final message to user"
}}

Previous tool results:
{history_block}

User request:
{state["user_input"]}
"""

        raw = llm.invoke(prompt).content.strip()
        decision = _parse_decision(raw)

        if not decision:
            decision = _repair_to_json(raw)
            if not decision:
                state["response"] = f"Invalid agent response format: {raw}"
                return state

        tool = _extract_tool_name(decision, tool_names, raw)
        action = _normalize_action(decision, tool)

        # ------------------------------------------------
        # TOOL CALL
        # ------------------------------------------------
        if action == "tool":

            args = _extract_arguments(decision)

            if tool not in tool_names:
                state["response"] = f"Invalid tool selected: {tool}"
                return state

            params = args.get("params") or {}
            query = args.get("query") or {}
            body = args.get("body") or {}

            clean_args = {
                "params": {k: v for k, v in params.items() if v is not None},
                "query": {k: v for k, v in query.items() if v is not None},
                "body": {k: v for k, v in body.items() if v is not None},
            }
            clean_args = _apply_schema_fixes(tool, clean_args, tools_by_name, state["user_input"], tool_names)

            # Guardrail: reject invalid class phrases like "class xyz".
            tool_def = tools_by_name.get(tool) or {}
            input_schema = tool_def.get("inputSchema", {})
            body_schema = ((input_schema.get("properties") or {}).get("body") or {})
            body_props = body_schema.get("properties") or {}
            if "class_id" in body_props:
                class_token = _extract_class_token_from_user(state["user_input"])
                if class_token and not _is_valid_class_token(class_token):
                    state["response"] = (
                        f"Invalid class reference: '{class_token}'. "
                        "Use class number like 'class 5' or class_id like 'c5'."
                    )
                    return state

            signature = _call_signature(tool, clean_args)
            call_counts[signature] = call_counts.get(signature, 0) + 1
            if call_counts[signature] > MAX_REPEAT_SAME_CALL:
                state["response"] = (
                    f"Stopped to avoid repeated loop on tool {tool}. "
                    "Please rephrase with specific fields if needed."
                )
                return state

            try:
                result = call_tool(tool, clean_args)
            except Exception as e:
                state["response"] = f"Tool execution error: {str(e)}"
                return state

            scratchpad.append(f"Tool: {tool}\nResult: {json.dumps(result)}")

            # If a write tool succeeded, finish immediately instead of waiting
            # for the model to produce a separate final action.
            if _is_write_tool(tool) and not _looks_like_error(result):
                state["response"] = _build_write_confirmation(tool, clean_args, result)
                return state
            if _is_write_tool(tool) and _looks_like_error(result):
                state["response"] = _extract_error_message(result)
                return state

            continue

        # ------------------------------------------------
        # FINAL RESPONSE
        # ------------------------------------------------
        if action == "final":
            state["response"] = _extract_final_text(decision)
            return state

        state["response"] = f"Invalid agent action: {_find_first_key(decision, {'action', 'act', 'type', 'next_action'})}"
        return state

    # Best-effort fallback: if we executed a successful write, report it.
    for entry in reversed(scratchpad):
        if not entry.startswith("Tool: "):
            continue
        first_line = entry.splitlines()[0]
        tool_name = first_line.replace("Tool: ", "").strip()
        if _is_write_tool(tool_name):
            state["response"] = f"{tool_name} completed successfully."
            return state

    state["response"] = "Agent stopped after maximum reasoning steps."
    return state
