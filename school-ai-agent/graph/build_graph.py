from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.orchestrator import orchestrator
from graph.get_agent import get_agent
from graph.update_agent import update_agent
from graph.conversation_agent import conversation_agent
from graph.summarize_agent import summarize_agent


def route(state: AgentState):
    return state["intent"]


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("getdetails", get_agent)
    graph.add_node("updatedetails", update_agent)
    graph.add_node("conversation", conversation_agent)
    graph.add_node("summarize", summarize_agent)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route,
        {
            "getdetails": "getdetails",
            "updatedetails": "updatedetails",
            "conversation": "conversation",
        },
    )

    graph.add_edge("getdetails", "summarize")
    graph.add_edge("updatedetails", "summarize")
    graph.add_edge("conversation", END)
    graph.add_edge("summarize", END)

    return graph.compile()