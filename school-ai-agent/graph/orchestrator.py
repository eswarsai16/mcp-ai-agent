from langchain_ollama import ChatOllama
from graph.state import AgentState

llm = ChatOllama(model="qwen2.5:3b", temperature=0)

READ_ENTITY_KEYWORDS = {
    "student",
    "students",
    "teacher",
    "teachers",
    "class",
    "classes",
    "subject",
    "subjects",
    "mark",
    "marks",
    "school",
    "database",
}

WRITE_KEYWORDS = {
    "add",
    "create",
    "insert",
    "new",
    "update",
    "edit",
    "change",
    "delete",
    "remove",
}


def orchestrator(state: AgentState) -> AgentState:
    user_text = state["user_input"].lower()

    has_entity = any(k in user_text for k in READ_ENTITY_KEYWORDS)
    has_write_intent = any(k in user_text for k in WRITE_KEYWORDS)

    if has_entity:
        state["intent"] = "updatedetails" if has_write_intent else "getdetails"
        return state

    history_text = "\n".join(
        [f"{m['role']}: {m['content']}" for m in state["history"][-6:]]
    )

    prompt = f"""
    You are routing requests for a School Database AI system.

    If the user is asking about:
    - students
    - teachers
    - classes
    - subjects
    - marks
    - school database data

    Then classify as:
    - getDetails (read-only queries)
    - updateDetails (create/update/delete)

    If the user is just chatting or asking general knowledge, classify as:
    - conversation

    Conversation history:
    {history_text}

    User:
    {state["user_input"]}

    Return ONLY one word:
    getDetails
    updateDetails
    conversation
    """

    intent = llm.invoke(prompt).content.strip().lower()

    if intent not in ["getdetails", "updatedetails", "conversation"]:
        intent = "conversation"

    state["intent"] = intent
    return state
