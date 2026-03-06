from graph.core.mcp_client import list_tools, call_tool
from graph.core.state import AgentState
from langchain_ollama import ChatOllama
from graph.core.decision_parsing import (
    build_tool_schema_summary,
    call_signature,
    extract_arguments,
    extract_final_text,
    extract_tool_name,
    find_first_key,
    is_write_tool,
    looks_like_error,
    normalize_action,
    parse_decision,
)
from graph.core.schema_fixups import (
    apply_schema_fixes,
    extract_class_token_from_user,
    is_valid_class_token,
)

llm = ChatOllama(model="qwen2.5:3b", temperature=0)

MAX_STEPS = 6
MAX_REPEAT_SAME_CALL = 2


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
    return parse_decision(repaired_raw)


def _is_tool_allowed(tool_name: str, allowed_prefixes: tuple[str, ...]) -> bool:
    lowered = tool_name.lower()
    # Allow read/list tools for planning, validation, and ID generation.
    if lowered.startswith("get"):
        return True
    return any(lowered.startswith(prefix.lower()) for prefix in allowed_prefixes)


def run_mutation_agent(
    state: AgentState,
    agent_label: str,
    allowed_prefixes: tuple[str, ...],
) -> AgentState:
    # Global guardrail for invalid class references to avoid pointless tool loops.
    class_token = extract_class_token_from_user(state["user_input"])
    if class_token and not is_valid_class_token(class_token):
        state["response"] = (
            f"Invalid class reference: '{class_token}'. "
            "Use class number like 'class 5' or class_id like 'c5'."
        )
        return state

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
You are an autonomous School Database {agent_label} Agent.

You MUST use MCP tools to complete the task.

Available tools and schemas:
{tool_summary}

Rules:
- Understand natural English.
- Use only tools that match these operation prefixes: {allowed_prefixes}.
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
        decision = parse_decision(raw)

        if not decision:
            decision = _repair_to_json(raw)
            if not decision:
                state["response"] = f"Invalid agent response format: {raw}"
                return state

        tool = extract_tool_name(decision, tool_names, raw)
        action = normalize_action(decision, tool)

        if action == "tool":
            args = extract_arguments(decision)

            if tool not in tool_names:
                state["response"] = f"Invalid tool selected: {tool}"
                return state
            if not _is_tool_allowed(tool, allowed_prefixes):
                state["response"] = f"Tool not allowed for {agent_label.lower()} agent: {tool}"
                return state

            params = args.get("params") or {}
            query = args.get("query") or {}
            body = args.get("body") or {}

            clean_args = {
                "params": {k: v for k, v in params.items() if v is not None},
                "query": {k: v for k, v in query.items() if v is not None},
                "body": {k: v for k, v in body.items() if v is not None},
            }
            clean_args = apply_schema_fixes(tool, clean_args, tools_by_name, state["user_input"], tool_names)

            tool_def = tools_by_name.get(tool) or {}
            input_schema = tool_def.get("inputSchema", {})
            body_schema = ((input_schema.get("properties") or {}).get("body") or {})
            body_props = body_schema.get("properties") or {}
            if "class_id" in body_props:
                class_token = extract_class_token_from_user(state["user_input"])
                if class_token and not is_valid_class_token(class_token):
                    state["response"] = (
                        f"Invalid class reference: '{class_token}'. "
                        "Use class number like 'class 5' or class_id like 'c5'."
                    )
                    return state

            signature = call_signature(tool, clean_args)
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

            scratchpad.append(f"Tool: {tool}\nResult: {result}")

            if is_write_tool(tool):
                state["result"] = {
                    "tool": tool,
                    "arguments": clean_args,
                    "tool_result": result,
                    "operation_done": not looks_like_error(result),
                }
                return state

            continue

        if action == "final":
            state["response"] = extract_final_text(decision)
            return state

        state["response"] = f"Invalid agent action: {find_first_key(decision, {'action', 'act', 'type', 'next_action'})}"
        return state

    for entry in reversed(scratchpad):
        if not entry.startswith("Tool: "):
            continue
        first_line = entry.splitlines()[0]
        tool_name = first_line.replace("Tool: ", "").strip()
        if is_write_tool(tool_name):
            state["response"] = f"{tool_name} completed successfully."
            return state

    state["response"] = "Agent stopped after maximum reasoning steps."
    return state
