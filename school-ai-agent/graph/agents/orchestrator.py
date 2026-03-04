from langchain_ollama import ChatOllama
from graph.core.state import AgentState

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
    "modify",
    "delete",
    "remove",
    "drop",
}

CREATE_KEYWORDS = {"add", "create", "insert", "new"}
UPDATE_KEYWORDS = {"update", "edit", "change", "modify", "rename", "set"}
DELETE_KEYWORDS = {"delete", "remove", "drop"}


def _contains_any(text: str, words: set[str]) -> bool:
    return any(w in text for w in words)


def _deterministic_intent(user_text: str) -> str | None:
    capability_phrases = [
        "can you help",
        "what can you",
        "are you able",
        "can you modify",
        "can you update",
    ]
    if any(p in user_text for p in capability_phrases):
        return "conversation"

    has_entity = _contains_any(user_text, READ_ENTITY_KEYWORDS)
    if not has_entity:
        return None

    if _contains_any(user_text, DELETE_KEYWORDS):
        return "deletedetails"
    if _contains_any(user_text, UPDATE_KEYWORDS):
        return "updatedetails"
    if _contains_any(user_text, CREATE_KEYWORDS):
        return "postdetails"
    if _contains_any(user_text, WRITE_KEYWORDS):
        return "updatedetails"
    return "getdetails"


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
    user_text = state["user_input"].lower()

    fast_intent = _deterministic_intent(user_text)
    if fast_intent:
        state["intent"] = fast_intent
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

    Then classify as one of:
    - getDetails (read-only queries)
    - postDetails (create/add operations)
    - updateDetails (edit/change operations)
    - deleteDetails (delete/remove operations)

    If the user is just chatting or asking general knowledge, classify as:
    - conversation

    Conversation history:
    {history_text}

    User:
    {state["user_input"]}

    Return ONLY one word:
    getDetails
    postDetails
    updateDetails
    deleteDetails
    conversation
    """

    intent = llm.invoke(prompt).content.strip()
    state["intent"] = _normalize_intent(intent)
    return state
