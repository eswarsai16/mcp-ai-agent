from __future__ import annotations

import json
import re

from langchain_ollama import ChatOllama

from graph.core.decision_parsing import extract_error_message, looks_like_error
from graph.core.state import AgentState

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0,
    format="json",
    timeout=30,
)


def _safe_json_load(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw:
        return None

    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        raw = raw.replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    return None


def _extract_rows(result):
    if isinstance(result, dict):
        payload = result.get("structuredContent", result)

        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]

        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            if isinstance(data, dict):
                return [data]

            for v in payload.values():
                if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                    return v
    
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                text = text.strip()
                if not text:
                    continue
                if text.startswith("[") or text.startswith("{"):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            return [x for x in parsed if isinstance(x, dict)]
                        if isinstance(parsed, dict):
                            return [parsed]
                    except Exception:
                        continue

    return []


def _format_single_record(row: dict) -> str:
    parts = []
    for k, v in row.items():
        label = k.replace("_", " ").title()
        parts.append(f"{label}: {v}")

    return "Here is what I found:\n" + "\n".join(parts)


def _format_multiple_records(rows: list[dict]) -> str:
    lines = [f"I found {len(rows)} matching records:"]
    for i, row in enumerate(rows, start=1):
        summary = ", ".join(f"{k}={row[k]}" for k in sorted(row.keys()))
        lines.append(f"{i}. {summary}")
    return "\n".join(lines)


def _llm_verify_and_summarize(user_input: str, tool: str | None, arguments: dict, tool_result) -> str | None:
    prompt = f"""
You are the final verification and response layer for a School Database AI assistant.

You must verify whether the operation was successful based on the tool result.
Then produce the final user-facing text.

Return STRICT JSON only:
{{
  "operation_status": "success|failed|unclear",
  "response": "final response for user"
}}

Rules:
- Do not mention MCP, JSON, schemas, or internal routing.
- If tool result indicates an error, set operation_status to failed and explain clearly.
- If required input is missing, ask one short clarification question.
- Keep the response concise and directly useful.

User request:
{user_input}

Tool used:
{tool}

Tool arguments:
{json.dumps(arguments, ensure_ascii=True)}

Tool result:
{json.dumps(tool_result, ensure_ascii=True, default=str)}
""".strip()

    try:
        raw = llm.invoke(prompt).content
    except Exception:
        return None

    parsed = _safe_json_load(raw)
    if not parsed:
        return None

    response = parsed.get("response")
    if isinstance(response, str) and response.strip():
        return response.strip()
    return None


def summarize_agent(state: AgentState) -> AgentState:
    if state.get("response") and not state.get("result"):
        return state

    execution = state.get("result")
    if not execution:
        state["response"] = state.get("response") or "I could not find any information for that."
        return state

    if isinstance(execution, dict) and "tool_result" in execution:
        tool = execution.get("tool")
        arguments = execution.get("arguments") or {}
        tool_result = execution.get("tool_result")
    else:
        tool = None
        arguments = {}
        tool_result = execution

    if looks_like_error(tool_result):
        state["response"] = extract_error_message(tool_result)
        return state
    
    verified_text = _llm_verify_and_summarize(
        user_input=state.get("user_input", ""),
        tool=tool,
        arguments=arguments,
        tool_result=tool_result,
    )
    if verified_text:
        state["response"] = verified_text
        return state

    rows = _extract_rows(tool_result)
    if rows:
        state["response"] = (
            _format_single_record(rows[0]) if len(rows) == 1 else _format_multiple_records(rows)
        )
        return state

    state["response"] = "The operation completed, but I could not format the result clearly."
    return state
