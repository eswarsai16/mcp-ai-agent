from __future__ import annotations

import json
import re

from langchain_ollama import ChatOllama
from graph.core.state import AgentState

llm = ChatOllama(model="qwen2.5:3b", temperature=0, format="json", timeout=30)


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

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None

def _normalize_intent(intent: str) -> str:
    normalized = (intent or "").strip().lower()
    aliases = {
        "getdetails": "getdetails",
        "postdetails": "postdetails",
        "createdetails": "postdetails",
        "updatedetails": "updatedetails",
        "deletedetails": "deletedetails",
        "conversation": "conversation",
    }
    return aliases.get(normalized, "conversation")


def orchestrator(state: AgentState) -> AgentState:
    history_text = "\n".join(
        [f"{m['role']}: {m['content']}" for m in state["history"][-6:]]
    )

    prompt = f"""
You route requests for a School Database AI system.

Return STRICT JSON only:
{{
  "intent": "getDetails|postDetails|updateDetails|deleteDetails|conversation"
}}

Rules:
- If user asks to read/fetch/list/show/find database records, use getDetails.
- If user asks to create/add/insert new records, use postDetails.
- If user asks to update/edit/change records, use updateDetails.
- If user asks to delete/remove/drop records, use deleteDetails.
- Use conversation only for greetings or purely general chat not related to school database operations.
- Treat mentions of student/teacher/class/subject/marks or ids like s12,t3,c5,eng2,mat4,sci1,m10 as school database intent.

Conversation history:
{history_text}

User:
{state["user_input"]}
""".strip()

    raw = llm.invoke(prompt).content
    parsed = _safe_json_load(raw)

    if not parsed:
        repair_prompt = f"""
Convert this to strict JSON: {{"intent":"getDetails|postDetails|updateDetails|deleteDetails|conversation"}}
Content:
{raw}
""".strip()
        repaired = llm.invoke(repair_prompt).content
        parsed = _safe_json_load(repaired)

    intent = ""
    if isinstance(parsed, dict):
        intent = str(parsed.get("intent", "")).strip()

    state["intent"] = _normalize_intent(intent)
    return state
