from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    result: Optional[dict]
    response: Optional[str]
    history: List[Dict[str, str]]
    last_list_result: Optional[List[Dict[str, Any]]]