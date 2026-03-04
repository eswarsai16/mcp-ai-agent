from langchain_ollama import ChatOllama
from graph.core.state import AgentState
import json

llm = ChatOllama(model="qwen2.5:3b", temperature=0)


def _extract_rows(result):
    if isinstance(result, dict):
        payload = result.get("structuredContent", result)
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            for value in payload.values():
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
    return []


def _format_full_rows(rows):
    lines = [f"Total records: {len(rows)}"]
    for i, row in enumerate(rows, start=1):
        parts = [f"{k}={row[k]}" for k in sorted(row.keys())]
        lines.append(f"{i}. " + ", ".join(parts))
    return "\n".join(lines)


def summarize_agent(state: AgentState) -> AgentState:
    if state.get("response"):
        return state

    result = state.get("result")

    if not result:
        state["response"] = "No result found."
        return state

    rows = _extract_rows(result)
    if rows:
        state["response"] = _format_full_rows(rows)
        return state

    prompt = f"""
Convert this into clean human-readable format:

{json.dumps(result, indent=2)}

Do not output JSON.
"""

    state["response"] = llm.invoke(prompt).content.strip()
    return state
