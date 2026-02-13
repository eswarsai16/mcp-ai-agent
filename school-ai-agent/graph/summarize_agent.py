from langchain_ollama import ChatOllama
from graph.state import AgentState
import json

llm = ChatOllama(model="qwen2.5:3b", temperature=0)


def summarize_agent(state: AgentState) -> AgentState:
    if state.get("response"):
        return state

    result = state.get("result")

    if not result:
        state["response"] = "No result found."
        return state

    prompt = f"""
Convert this into clean human-readable format:

{json.dumps(result, indent=2)}

Do not output JSON.
"""

    state["response"] = llm.invoke(prompt).content.strip()
    return state