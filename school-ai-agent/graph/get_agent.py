from langchain_ollama import ChatOllama
from graph.mcp_client import list_tools, call_tool
from graph.state import AgentState
import json
import re

llm = ChatOllama(model="qwen2.5:3b", temperature=0)


def _call_read_tool(tool_name: str, state: AgentState) -> bool:
    try:
        result = call_tool(tool_name, {"params": {}, "query": {}, "body": {}})
        state["result"] = result
        return True
    except Exception as e:
        state["response"] = f"Tool error: {str(e)}"
        return True


def get_agent(state: AgentState) -> AgentState:
    tools = list_tools()

    if not tools:
        state["response"] = "Unable to fetch tools from MCP server."
        return state

    tool_names = [t["name"] for t in tools if t.get("name")]
    user_text = state["user_input"].lower()

    # Deterministic shortcuts for common read intents.
    if ("teacher" in user_text or "teachers" in user_text) and "getTeachers" in tool_names:
        _call_read_tool("getTeachers", state)
        return state

    if ("class" in user_text or "classes" in user_text) and "getClasses" in tool_names:
        _call_read_tool("getClasses", state)
        return state

    if ("subject" in user_text or "subjects" in user_text) and "getSubjects" in tool_names:
        _call_read_tool("getSubjects", state)
        return state

    if ("student" in user_text or "students" in user_text) and "getStudents" in tool_names:
        _call_read_tool("getStudents", state)
        return state

    # Deterministic: student + subject marks.
    match = re.search(r"s\d+.*(eng|mat|sci)\d+", user_text)
    if match and "getByStudentAndSubject" in tool_names:
        student_match = re.search(r"s\d+", user_text)
        subject_match = re.search(r"(eng|mat|sci)\d+", user_text)

        if student_match and subject_match:
            try:
                result = call_tool(
                    "getByStudentAndSubject",
                    {
                        "params": {},
                        "query": {
                            "student_id": student_match.group(),
                            "subject_id": subject_match.group(),
                        },
                        "body": {},
                    },
                )
                state["result"] = result
                return state
            except Exception as e:
                state["response"] = f"Tool error: {str(e)}"
                return state

    # Deterministic rule: full marks list.
    if "all marks" in user_text or "show all marks" in user_text:
        if "getByStudentAndSubject" in tool_names:
            try:
                result = call_tool(
                    "getByStudentAndSubject",
                    {"params": {}, "query": {}, "body": {}},
                )
                state["result"] = result
                return state
            except Exception as e:
                state["response"] = f"Tool error: {str(e)}"
                return state

    # LLM tool selection.
    prompt = f"""
You are a School Database Read-Only Agent.

IMPORTANT:
- Only answer using the available tools.
- Do NOT use general world knowledge.
- Always assume the question refers to the school database.
- Choose EXACTLY one tool from the list.

Available tools (spelling must match exactly):
{tool_names}

Return STRICT JSON only:

{{
    "tool": "EXACT_TOOL_NAME",
    "arguments": {{
            "params": {{}},
            "query": {{}},
            "body": {{}}
    }}
}}

User:
{state["user_input"]}
"""

    raw = llm.invoke(prompt).content.strip()

    try:
        decision = json.loads(raw)
    except Exception:
        state["response"] = raw
        return state

    tool = decision.get("tool")
    args = decision.get("arguments", {})

    if tool not in tool_names:
        state["response"] = "Selected tool is not valid."
        return state

    # Clean null values.
    params = args.get("params") or {}
    query = args.get("query") or {}
    body = args.get("body") or {}

    clean_args = {
        "params": {k: v for k, v in params.items() if v is not None},
        "query": {k: v for k, v in query.items() if v is not None},
        "body": {k: v for k, v in body.items() if v is not None},
    }

    try:
        result = call_tool(tool, clean_args)
        state["result"] = result
    except Exception as e:
        state["response"] = f"Tool error: {str(e)}"
        return state

    # Store list results for index reference.
    if isinstance(result, dict):
        data = result.get("structuredContent", result)
        if isinstance(data, list):
            state["last_list_result"] = data

    return state
