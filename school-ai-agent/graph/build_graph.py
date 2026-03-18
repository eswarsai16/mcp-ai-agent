
import asyncio
from typing import Any

# ✅ Direct import (no fallback needed)
from graph.agents.orchestrator import GenericOrchestrator


class _GraphWrapper:
    def __init__(self, orchestrator: Any):
        self._orch = orchestrator

    async def ainvoke(self, state: Any):
        # Orchestrator is expected to have async execute(state)
        if hasattr(self._orch, "execute"):
            maybe = self._orch.execute(state)
            return await maybe if asyncio.iscoroutine(maybe) else maybe

        # Optional support if orchestrator is callable
        if callable(self._orch):
            maybe = self._orch(state)
            return await maybe if asyncio.iscoroutine(maybe) else maybe

        raise RuntimeError("Orchestrator object is not callable and has no 'execute' method")


def build_generic_mcp_graph(mcp_url: str = "http://localhost:4000/mcp"):
    """
    Construct and return a graph-like wrapper around the project's orchestrator.
    """
    orch = GenericOrchestrator(mcp_url=mcp_url)
    return _GraphWrapper(orch)
