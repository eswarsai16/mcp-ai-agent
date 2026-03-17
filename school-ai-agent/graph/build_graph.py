"""Build graph wrapper that exposes an `ainvoke(state)` coroutine.

This file provides two exported functions used by run scripts:
"""
import asyncio
from typing import Any

def _find_orchestrator_class():
    """Try several import paths to locate an orchestrator class."""
    candidates = [
        ("graph.agents.orchestrator", "GenericOrchestrator"),
        ("graph.agents.orchestrator", "Orchestrator"),
    ]

    for module_name, class_name in candidates:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls is not None:
                return cls
        except Exception as e:
            continue

    return None

class _GraphWrapper:
    def __init__(self, orchestrator: Any):
        self._orch = orchestrator

    async def ainvoke(self, state: Any):
        # If orchestrator is a class instance with execute method
        if hasattr(self._orch, "execute"):
            maybe = self._orch.execute(state)
            if asyncio.iscoroutine(maybe):
                return await maybe
            return maybe

        # If orchestrator is a callable (function)
        if callable(self._orch):
            maybe = self._orch(state)
            if asyncio.iscoroutine(maybe):
                return await maybe
            return maybe

        raise RuntimeError("Orchestrator object is not callable and has no 'execute' method")


def build_generic_mcp_graph(mcp_url: str = "http://localhost:4000/mcp"):
    """Construct and return a graph-like wrapper around the project's orchestrator.

    This function will try to instantiate an orchestrator class with a single
    argument `mcp_url` if the constructor supports it; otherwise it will call
    the constructor without arguments.
    """
    OrchClass = _find_orchestrator_class()
    if OrchClass is None:
        raise ImportError("Could not locate an orchestrator class in graph.agents")

    # Instantiate orchestrator with or without mcp_url
    try:
        orch = OrchClass(mcp_url)
    except TypeError:
        orch = OrchClass()

    return _GraphWrapper(orch)


# Backwards compatibility alias
def build_graph(mcp_url: str = "http://localhost:4000/mcp"):
    return build_generic_mcp_graph(mcp_url)
