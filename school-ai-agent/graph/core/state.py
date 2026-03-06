from typing import TypedDict, Optional, List, Dict


class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    result: Optional[dict]
    response: Optional[str]
    history: List[Dict[str, str]]
