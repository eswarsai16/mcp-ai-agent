import json
import re
from typing import Any


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


def find_first_key(obj: dict, candidates: set[str]):
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


def parse_decision(raw: str) -> dict | None:
    parsed = _extract_json_dict(raw)
    if parsed:
        container = _find_decision_container(parsed)
        return container or parsed
    return None


def _normalize_entity_token(text: str) -> str:
    token = re.sub(r"[^a-z]", "", (text or "").lower())
    if token.endswith("s") and len(token) > 3:
        token = token[:-1]
    return token


def _infer_tool_from_action(decision: dict, tool_names: list[str]) -> str | None:
    action_value = find_first_key(decision, {"action", "act", "type", "next_action"})
    action_raw = str(action_value or "").strip().lower()
    if not action_raw:
        return None

    # Handles forms like ADD_STUDENT / update_teacher / delete-marks.
    action_norm = re.sub(r"[^a-z0-9]+", "_", action_raw).strip("_")
    parts = [p for p in action_norm.split("_") if p]
    if not parts:
        return None

    op_token = parts[0]
    entity_token = parts[1] if len(parts) > 1 else ""

    op_map = {
        "add": "create",
        "create": "create",
        "insert": "create",
        "new": "create",
        "update": "update",
        "edit": "update",
        "change": "update",
        "modify": "update",
        "rename": "update",
        "set": "update",
        "delete": "delete",
        "remove": "delete",
        "drop": "delete",
    }
    op_prefix = op_map.get(op_token)
    if not op_prefix:
        return None

    entity_norm = _normalize_entity_token(entity_token)
    candidates = [t for t in tool_names if t.lower().startswith(op_prefix)]
    if not candidates:
        return None

    if not entity_norm:
        return candidates[0] if len(candidates) == 1 else None

    exact = []
    partial = []
    for tool in candidates:
        suffix = tool[len(op_prefix):]
        suffix_norm = _normalize_entity_token(suffix)
        if suffix_norm == entity_norm:
            exact.append(tool)
        elif entity_norm in suffix_norm:
            partial.append(tool)

    if len(exact) == 1:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


def extract_tool_name(decision: dict, tool_names: list[str], raw: str) -> str | None:
    tool_value = find_first_key(decision, {"tool", "tool_name", "function", "name"})
    if isinstance(tool_value, str):
        candidate = tool_value.strip()
        if candidate in tool_names:
            return candidate

    inferred = _infer_tool_from_action(decision, tool_names)
    if inferred:
        return inferred

    lowered = raw.lower()
    matched = [tool_name for tool_name in tool_names if tool_name.lower() in lowered]
    if len(matched) == 1:
        return matched[0]

    return None


def extract_arguments(decision: dict):
    args_value = find_first_key(
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

    direct_params = find_first_key(decision, {"params"})
    direct_query = find_first_key(decision, {"query"})
    direct_body = find_first_key(decision, {"body"})

    if any(v is not None for v in [direct_params, direct_query, direct_body]):
        return {
            "params": direct_params or {},
            "query": direct_query or {},
            "body": direct_body or {},
        }

    return {}


def extract_final_text(decision: dict) -> str:
    final_text = find_first_key(decision, {"response", "final", "answer", "message", "text"})
    if isinstance(final_text, str) and final_text.strip():
        return final_text.strip()
    return "Update completed."


def normalize_action(decision: dict, tool_name: str | None) -> str:
    action_value = find_first_key(decision, {"action", "act", "type", "next_action"})
    action_raw = str(action_value or "").strip().lower()

    if action_raw in {"tool", "call_tool", "call", "execute"}:
        return "tool"
    if action_raw in {"final", "done", "finish", "complete"}:
        return "final"
    if any(x in action_raw for x in ["add_", "create_", "insert_", "update_", "edit_", "delete_", "remove_"]):
        return "tool"

    if tool_name:
        return "tool"

    if find_first_key(decision, {"response", "final", "answer", "message", "text"}):
        return "final"

    return ""


def is_write_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return (
        lowered.startswith("create")
        or lowered.startswith("update")
        or lowered.startswith("delete")
        or lowered.startswith("remove")
    )


def call_signature(tool: str, args: dict) -> str:
    return f"{tool}|{json.dumps(args, sort_keys=True)}"


def looks_like_error(result: Any) -> bool:
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


def extract_error_message(result: Any) -> str:
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


def build_write_confirmation(tool: str, result: Any) -> str:
    payload = _extract_object_from_content(result)
    if isinstance(payload, dict):
        for key in ["student_id", "teacher_id", "class_id", "subject_id", "marks_id", "id", "name"]:
            if payload.get(key):
                return f"{tool} completed successfully for {key}={payload.get(key)}."

    return f"{tool} completed successfully."
