import warnings
import asyncio
import json
import os
from typing import Any

# Suppress Pydantic V1 compatibility warning coming from langchain_core on Python 3.14+
# This avoids the noisy startup warning while keeping behavior unchanged.
warnings.filterwarnings(
    "ignore",
    message=r".*Pydantic V1 functionality isn't compatible with Python 3.14 or greater.*",
    category=UserWarning,
)

# ✅ Only one build_graph.py exists, so import directly (no fallbacks)
from graph.build_graph import build_generic_mcp_graph as _build_graph_fn

# AgentState is optional (fallback to dict if not found)
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
    # Build the graph once
    # If MCP_URL env var exists, pass it; otherwise let build_graph use its default
    mcp_url = os.getenv("MCP_URL")
    try:
        graph = _build_graph_fn(mcp_url=mcp_url) if mcp_url else _build_graph_fn()
    except TypeError:
        # If builder does not support kwargs, fallback to positional/no-arg
        graph = _build_graph_fn(mcp_url) if mcp_url else _build_graph_fn()

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
                maybe = graph(state)
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
            else:
                print("Error: graph object is not callable and has no 'ainvoke' method.")
                break

            # Print assistant messages
            messages = result.get("messages") if isinstance(result, dict) else None
            if messages and len(messages) > 1:
                # Get the last assistant message
                for m in reversed(messages):
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        content = m.get("content", "")
                        # content might be dict/list sometimes; stringify safely
                        if isinstance(content, (dict, list)):
                            content = _pretty_print(content)
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