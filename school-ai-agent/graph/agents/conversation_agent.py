from langchain_ollama import ChatOllama
from graph.core.state import AgentState

llm = ChatOllama(model="qwen2.5:3b", temperature=0)


def conversation_agent(state: AgentState) -> AgentState:
    state["result"] = None
    user_text = state["user_input"].strip()
    user_lower = user_text.lower()

    capability_markers = [
        "can you help",
        "are you able",
        "through agents",
        "manage school data",
        "modify school data",
    ]
    if any(marker in user_lower for marker in capability_markers):
        state["response"] = (
            "Yes. I can help with school database operations through connected agents, "
            "including listing, creating, updating, and deleting records."
        )
        return state

    prompt = f"""
You are a School AI assistant.
Always reply in English.
Keep replies concise and relevant to this School AI system only.
Do not mention unrelated external platforms or services.

User:
{user_text}
"""

    state["response"] = llm.invoke(prompt).content.strip()
    return state
