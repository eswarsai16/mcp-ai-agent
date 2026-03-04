from graph.agents.mutation_agent_core import run_mutation_agent
from graph.core.state import AgentState


def post_agent(state: AgentState) -> AgentState:
    return run_mutation_agent(
        state=state,
        agent_label="CREATE",
        allowed_prefixes=("create",),
    )
