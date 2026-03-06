from __future__ import annotations
 
import json
import re
from langchain_ollama import ChatOllama
 
from graph.core.mcp_client import list_tools, call_tool
from graph.core.decision_parsing import extract_error_message, looks_like_error
from graph.core.prompt_loader import load_prompt
from graph.core.state import AgentState
 
    

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0,
    format="json",
    timeout=30,
)
 
 
def _safe_json_load(raw: str) -> dict:
    raw = (raw or "").strip()
 
    if not raw:
        raise ValueError("Empty model output")
 
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        raw = raw.replace("json", "", 1).strip()
 
    try:
        return json.loads(raw)
    except Exception:
        pass
 
    # Extract first {...}
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        return json.loads(m.group(0))
 
    raise ValueError(f"Non-JSON output from model: {raw[:200]}")
 
 
def _tool_catalog(tools: list[dict]) -> list[dict]:
    """
    COMPACT tool catalog to avoid giant prompts (prevents hangs on small models).
    We keep:
      - name
      - description (shortened)
      - required fields from params/query/body (if schema present)
    """
    catalog: list[dict] = []
 
    for t in tools:
        name = t.get("name")
        if not name:
            continue
 
        desc = (t.get("description") or "")
        if len(desc) > 240:
            desc = desc[:240] + "..."
 
        input_schema = t.get("inputSchema") or {}
        props = input_schema.get("properties") or {}
 
        def _required(section: str) -> list[str]:
            sec = props.get(section) or {}
            return list(sec.get("required") or [])
        
        def _fields(section: str) -> list[str]:
            sec = props.get(section) or {}
            return sorted((sec.get("properties") or {}).keys())
 
        required_params = _required("params")
        required_query = _required("query")
 
        # For body, include required fields if it is object-like
        required_body = []
        body_schema = props.get("body") or {}
        # if OpenAPI->Zod produced required list here
        required_body = list(body_schema.get("required") or [])
        # if not available, keep empty; do NOT explode prompt size
 
        catalog.append(
            {
                "name": name,
                "description": desc,
                "required": {
                    "params": sorted(set(required_params)),
                    "query": sorted(set(required_query)),
                    "body": sorted(set(required_body)),
                },
                "fields": {
                    "params": _fields("params"),
                    "query": _fields("query"),
                    "body": _fields("body"),
                },
            }
        )
 
    return catalog
 
 
def _llm_choose_tool_and_args(user_input: str, catalog: list, error: str | None = None) -> dict:
    guidance = load_prompt("base_read.txt")
 
    prompt = f"""
{guidance}
 
You must select EXACTLY ONE tool and provide arguments.
 
Return STRICT JSON only.
 
Valid outputs:
 
(1) Tool call:
{{
  "tool": "EXACT_TOOL_NAME",
  "arguments": {{
    "params": {{}},
    "query": {{}},
    "body": {{}}
  }}
}}
 
(2) Need clarification:
{{
  "need_clarification": "short question",
  "tool": null,
  "arguments": null
}}
 
Rules:
- Use ONLY the tools provided below.
- Prefer the MOST SPECIFIC tool.
- If an identifier is present in the user request, prefer tools that require params.
- If the user asks for "all" or "list", prefer list tools.
- Arguments must match required fields shown in the tool catalog.
 
User request:
{user_input}
 
Tools (compact):
{json.dumps(catalog, indent=2)}
 
{"Previous tool error (fix arguments accordingly): " + error if error else ""}
""".strip() + "\n"
 
    # This is where your run was hanging earlier.
    # Now it cannot hang forever due to timeout=30.
    try:
        raw = llm.invoke(prompt).content
    except Exception as e:
        raise RuntimeError(f"LLM call failed or timed out: {e}")
 
    return _safe_json_load(raw)


def _find_id_token(user_input: str, tool_name: str, field_name: str) -> str | None:
    text = user_input.lower()
    field = field_name.lower()
    tool = tool_name.lower()

    if field in {"id", "studentid", "student_id"} or "student" in tool:
        m = re.search(r"\bs\d+\b", text)
        if m:
            return m.group(0)
    if field in {"id", "teacherid", "teacher_id"} or "teacher" in tool:
        m = re.search(r"\bt\d+\b", text)
        if m:
            return m.group(0)
    if field in {"id", "classid", "class_id"} or "class" in tool:
        m = re.search(r"\bc\d+\b", text)
        if m:
            return m.group(0)
    if field in {"id", "subjectid", "subject_id"} or "subject" in tool:
        m = re.search(r"\b(?:eng|mat|sci)\d+\b", text)
        if m:
            return m.group(0)
    if field in {"id", "marksid", "marks_id"} or "marks" in tool:
        m = re.search(r"\bm\d+\b", text)
        if m:
            return m.group(0)
    return None


def _normalize_args_for_schema(tool_def: dict, args: dict, user_input: str, tool_name: str) -> dict:
    properties = (tool_def.get("inputSchema") or {}).get("properties") or {}

    params = dict(args.get("params") or {})
    query = dict(args.get("query") or {})
    body = dict(args.get("body") or {})

    all_values = {}
    for section in (params, query, body):
        for key, value in section.items():
            if value is not None:
                all_values[key] = value

    sections = {"params": params, "query": query, "body": body}
    alias_map = {
        "id": ["student_id", "teacher_id", "class_id", "subject_id", "marks_id"],
        "studentId": ["student_id", "id"],
        "subjectId": ["subject_id", "id"],
        "teacherId": ["teacher_id", "id"],
        "classId": ["class_id", "id"],
        "marksId": ["marks_id", "id"],
    }

    for section_name, section_data in sections.items():
        schema = properties.get(section_name) or {}
        required_fields = list(schema.get("required") or [])
        allowed_fields = set((schema.get("properties") or {}).keys())

        for req in required_fields:
            if section_data.get(req) is not None:
                continue

            aliases = alias_map.get(req, [])
            for alias in aliases:
                if all_values.get(alias) is not None:
                    section_data[req] = all_values[alias]
                    break

            if section_data.get(req) is None:
                token = _find_id_token(user_input, tool_name, req)
                if token:
                    section_data[req] = token

        if allowed_fields:
            section_data = {k: v for k, v in section_data.items() if k in allowed_fields and v is not None}
        else:
            section_data = {k: v for k, v in section_data.items() if v is not None}
        sections[section_name] = section_data

    return {
        "params": sections["params"],
        "query": sections["query"],
        "body": sections["body"],
    }
 
 
def get_agent(state: AgentState) -> AgentState:
    tools = list_tools()
    if not tools:
        state["response"] = "Unable to fetch tools from MCP server."
        return state
 
    catalog = _tool_catalog(tools)
    tool_names = {t["name"] for t in tools if t.get("name")}
 
    # Decide tool + args
    try:
        decision = _llm_choose_tool_and_args(state["user_input"], catalog)
    except Exception as e:
        state["response"] = f"LLM decision error: {str(e)}"
        return state
 
    if decision.get("need_clarification"):
        state["response"] = decision["need_clarification"]
        return state
 
    tool = decision.get("tool")
    args = decision.get("arguments") or {}
 
    if tool not in tool_names:
        state["response"] = f"Selected tool is not valid: {tool}"
        return state
 
    # Normalize nulls
    params = args.get("params") or {}
    query = args.get("query") or {}
    body = args.get("body") or {}
 
    clean_args = {
        "params": {k: v for k, v in params.items() if v is not None},
        "query": {k: v for k, v in query.items() if v is not None},
        "body": {k: v for k, v in body.items() if v is not None},
    }
    tool_def = next((t for t in tools if t.get("name") == tool), {})
    clean_args = _normalize_args_for_schema(tool_def, clean_args, state["user_input"], tool)
 
    # Execute (1 repair attempt)
    first_result = call_tool(tool, clean_args)
    if not looks_like_error(first_result):
        state["result"] = {
            "tool": tool,
            "arguments": clean_args,
            "tool_result": first_result,
        }
        return state

    first_error = extract_error_message(first_result)

    # Ask LLM to repair args based on MCP validation error
    try:
        repaired = _llm_choose_tool_and_args(state["user_input"], catalog, error=first_error)
    except Exception as e2:
        state["response"] = f"Tool error: {first_error} | Repair failed: {str(e2)}"
        return state
 
    if repaired.get("need_clarification"):
        state["response"] = repaired["need_clarification"]
        return state
 
    tool2 = repaired.get("tool")
    args2 = repaired.get("arguments") or {}
 
    if tool2 not in tool_names:
        state["response"] = f"Tool error: {first_error}"
        return state
 
    params2 = args2.get("params") or {}
    query2 = args2.get("query") or {}
    body2 = args2.get("body") or {}
 
    clean_args2 = {
        "params": {k: v for k, v in params2.items() if v is not None},
        "query": {k: v for k, v in query2.items() if v is not None},
        "body": {k: v for k, v in body2.items() if v is not None},
    }
    tool_def2 = next((t for t in tools if t.get("name") == tool2), {})
    clean_args2 = _normalize_args_for_schema(tool_def2, clean_args2, state["user_input"], tool2)
 
    second_result = call_tool(tool2, clean_args2)
    if looks_like_error(second_result):
        state["response"] = f"Tool error after repair: {extract_error_message(second_result)}"
        return state

    state["result"] = {
        "tool": tool2,
        "arguments": clean_args2,
        "tool_result": second_result,
    }
    return state
