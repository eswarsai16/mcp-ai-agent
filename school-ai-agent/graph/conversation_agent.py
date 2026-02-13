from langchain_ollama import ChatOllama
from graph.state import AgentState

llm = ChatOllama(model="qwen2.5:3b", temperature=0)


def conversation_agent(state: AgentState) -> AgentState:
    state["result"] = None

    prompt = f"""
You are a School AI assistant.
Always reply in English.

User:
{state["user_input"]}
"""

    state["response"] = llm.invoke(prompt).content.strip()
    return state
