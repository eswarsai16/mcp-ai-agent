import warnings
import asyncio
import json
import sys
from typing import Any

# Suppress Pydantic V1 compatibility warning coming from langchain_core on Python 3.14+
# This avoids the noisy startup warning while keeping behavior unchanged.
warnings.filterwarnings(
    "ignore",
    message=r".*Pydantic V1 functionality isn't compatible with Python 3.14 or greater.*",
    category=UserWarning,
)

# Try to import the generic builder flexibly (supports several build_graph layouts)
try:
    from graph.build_graph import build_generic_mcp_graph as _build_graph_fn
except Exception:
    try:
        from graph.build_graph import build_graph as _build_graph_fn
    except Exception:
        try:
            from graph.build_graph_generic import build_generic_mcp_graph as _build_graph_fn
        except Exception:
            _build_graph_fn = None

try:
    from graph.core.state import AgentState
except Exception:
    AgentState = None


def _pretty_print(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)


async def main():
    if _build_graph_fn is None:
        print("Error: could not find a graph builder (build_generic_mcp_graph or build_graph).")
        return

    # Build the graph once (use default MCP URL from config/build_graph)
    graph = _build_graph_fn()

    # Continuous conversation loop
    print("=" * 60)
    print("Welcome to School AI Agent")
    print("Type 'exit' or 'bye' to quit")
    print("=" * 60)
    print()

    while True:
        # Get user input
        try:
            ask = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        # Check for exit commands
        if ask.lower() in ["exit", "bye", "quit", "q"]:
            print("Goodbye!")
            break

        # Skip empty input
        if not ask:
            continue

        # Prepare initial state object the graph expects
        if AgentState is not None:
            state = AgentState(messages=[{"role": "user", "content": ask}], context={})
        else:
            # Fallback to a plain dict if AgentState is unavailable
            state = {"messages": [{"role": "user", "content": ask}], "context": {}}

        # Execute the graph. Most graphs expose `ainvoke(state)` for async invocation.
        try:
            if hasattr(graph, "ainvoke"):
                result = await graph.ainvoke(state)
            elif callable(graph):
                # If graph is a coroutine function or callable wrapper
                maybe = graph(state)
                if asyncio.iscoroutine(maybe):
                    result = await maybe
                else:
                    result = maybe
            else:
                print("Error: graph object is not callable and has no 'ainvoke' method.")
                break

            # Print assistant messages
            messages = result.get("messages") if isinstance(result, dict) else None
            if messages and len(messages) > 1:
                # Get the last assistant message
                for m in reversed(messages):
                    if m.get("role") == "assistant":
                        content = m.get("content", "")
                        print(f"\nAssistant: {content}\n")
                        break
            else:
                # If no messages key, print the raw result summary
                print("No assistant messages found; printing raw result:")
                print(_pretty_print(result))

        except Exception as e:
            print(f"\nError executing request: {str(e)}\n")
            continue


if __name__ == "__main__":
    asyncio.run(main())
