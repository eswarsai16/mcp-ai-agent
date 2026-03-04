# School AI Agent

LangGraph-based multi-agent system for School DB operations through an MCP server.

## Architecture

Flow:
`User -> Orchestrator -> Specialized Agent -> MCP -> School API -> DB -> Summarizer`

Specialized agents:
- `get_agent`: read-only queries
- `post_agent`: create operations
- `update_agent`: update operations
- `delete_agent`: delete/remove operations
- `conversation_agent`: non-database chat
- `summarize_agent`: user-facing response formatting

## Project Structure

```text
school-ai-agent/
  run.py
  requirements.txt
  README.md
  .gitignore
  graph/
    build_graph.py
    agents/
      orchestrator.py
      get_agent.py
      post_agent.py
      update_agent.py
      delete_agent.py
      conversation_agent.py
      summarize_agent.py
      mutation_agent_core.py
    core/
      state.py
      mcp_client.py
      decision_parsing.py
      schema_fixups.py
```

## Run

1. Start MCP server (`localhost:4000/mcp`).
2. Install deps:
   - `pip install -r requirements.txt`
3. Run:
   - `python run.py`

Type `exit` to stop.
