from graph.core.mcp_client import call_tool
from graph.core.decision_parsing import looks_like_error
import re
from typing import Any


def extract_class_id_from_user(user_text: str) -> str | None:
    match = re.search(r"\bclass\s+(c?\d+)\b", user_text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).lower()
    return raw if raw.startswith("c") else f"c{raw}"


def extract_class_token_from_user(user_text: str) -> str | None:
    match = re.search(r"\bclass\s+([a-zA-Z0-9_]+)\b", user_text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def is_valid_class_token(token: str) -> bool:
    return re.fullmatch(r"c?\d+", token.strip().lower()) is not None


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

    single_prefix = re.match(r"^\^([a-z])[0-9]\+\$$", pattern)
    if single_prefix:
        prefix = single_prefix.group(1)
        digits = re.search(r"\d+", text)
        if digits:
            return f"{prefix}{digits.group(0)}"
        return None

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

    if field == "class_id":
        extracted = extract_class_id_from_user(user_text)
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

    for field, schema in body_props.items():
        field_label = field.replace("_", " ")
        pattern = rf"\b{re.escape(field_label)}\b\s+to\s+(.+?)(?:\s+\band\b|,|$)"
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            updates[field] = _coerce_typed_value(match.group(1), schema)

    if "name to" in lower:
        match = re.search(r"\bname\s+to\s+(.+?)(?:\s+\band\b|,|$)", user_text, re.IGNORECASE)
        if match:
            for field, schema in body_props.items():
                if field.endswith("name") and schema.get("type") == "string":
                    updates[field] = match.group(1).strip().strip("\"'")
                    break

    if "class" in lower and "class_id" in body_props:
        class_id = extract_class_id_from_user(user_text)
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
    if looks_like_error(result):
        return []
    payload = result.get("structuredContent", result)
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


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
    return None


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
    if len(nums) >= 3:
        for i in range(len(nums) - 2, -1, -1):
            gap = nums[i + 1] - nums[i]
            tail_count = len(nums) - (i + 1)
            if gap > 1000 and tail_count <= 5:
                return f"{prefix}{nums[i] + 1}"

    return f"{prefix}{nums[-1] + 1}"


def apply_schema_fixes(
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

        updates = _extract_field_updates_from_user(user_text, body_props)
        if updates:
            body.update(updates)

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
        class_id = extract_class_id_from_user(user_text)
        if class_id:
            body["class_id"] = class_id

    if name_field and not body.get(name_field):
        inferred_name = _extract_name_from_user(user_text, entity)
        if inferred_name:
            body[name_field] = inferred_name

    if lowered_tool.startswith("update") and id_field and params.get("id"):
        body[id_field] = params["id"]

    return fixed
