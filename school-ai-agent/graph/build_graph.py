from langgraph.graph import StateGraph, END
from graph.core.state import AgentState
from graph.agents.orchestrator import orchestrator
from graph.agents.get_agent import get_agent
from graph.agents.post_agent import post_agent
from graph.agents.update_agent import update_agent
from graph.agents.delete_agent import delete_agent
from graph.agents.conversation_agent import conversation_agent
from graph.agents.summarize_agent import summarize_agent


def route(state: AgentState):
    return state["intent"]


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("getdetails", get_agent)
    graph.add_node("postdetails", post_agent)
    graph.add_node("updatedetails", update_agent)
    graph.add_node("deletedetails", delete_agent)
    graph.add_node("conversation", conversation_agent)
    graph.add_node("summarize", summarize_agent)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route,
        {
            "getdetails": "getdetails",
            "postdetails": "postdetails",
            "updatedetails": "updatedetails",
            "deletedetails": "deletedetails",
            "conversation": "conversation",
        },
    )

    graph.add_edge("getdetails", "summarize")
    graph.add_edge("postdetails", "summarize")
    graph.add_edge("updatedetails", "summarize")
    graph.add_edge("deletedetails", "summarize")
    graph.add_edge("conversation", END)
    graph.add_edge("summarize", END)

    return graph.compile()
