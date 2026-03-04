from graph.agents.mutation_agent_core import run_mutation_agent
from graph.core.state import AgentState


def delete_agent(state: AgentState) -> AgentState:
    return run_mutation_agent(
        state=state,
        agent_label="DELETE",
        allowed_prefixes=("delete", "remove"),
    )
