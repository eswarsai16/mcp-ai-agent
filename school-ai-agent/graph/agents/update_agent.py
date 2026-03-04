from graph.agents.mutation_agent_core import run_mutation_agent
from graph.core.state import AgentState


def update_agent(state: AgentState) -> AgentState:
    return run_mutation_agent(
        state=state,
        agent_label="UPDATE",
        allowed_prefixes=("update",),
    )
