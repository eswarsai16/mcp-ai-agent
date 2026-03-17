# School AI Agent - Project Context & Implementation Guide

## Project Overview

**School AI Agent** is a generic LLM-powered automation system that connects to any MCP (Model Context Protocol) server to execute tools on behalf of users via natural language requests.

### Core Goal
Enable users to interact with a database/API through natural language without needing to know the schema, parameter names, or API structure. The system automatically:
- Discovers available tools from the MCP server
- Interprets user intent in natural language
- Selects and executes the appropriate tool
- Repairs invalid parameters when needed
- Returns human-readable results

---

## Architecture Overview

### High-Level Flow
```
User Input (Natural Language)
    ↓
LLM Agent (Tool Selection)
    ↓
MCP Client (API Communication)
    ↓
MCP Server (Executes Tool)
    ↓
Result Processing & Formatting
    ↓
Human-Readable Output
```

### Key Components

#### 1. **Entry Point** ([run.py](run.py))
- Implements continuous conversation loop
- Handles user input and exit commands ("exit", "bye")
- Invokes the orchestrator graph for each request
- Formats and displays results to user

**Key Features:**
- Continuous loop with exit handling
- Human-readable output formatting
- Async/await orchestration

#### 2. **Graph Orchestration** ([graph/build_graph.py](graph/build_graph.py))
- Builds the state machine graph using LangChain
- Manages workflow between agents
- Handles state transitions

#### 3. **Core Agents**

##### **GenericMCPAgent** ([graph/agents/generic_mcp_agent.py](graph/agents/generic_mcp_agent.py))
The main decision-making agent. Workflow:
1. **Tool Discovery** - Queries MCP server for available tools and their schemas
2. **LLM Decision Making** - Prompts LLM to select tool and extract parameters
3. **Tool Execution** - Calls MCP server with selected tool
4. **Error Handling & Repair** - If validation fails, uses LLM to repair parameters
5. **Result Formatting** - Returns structured result to user

**Key Methods:**
- `execute()` - Main orchestration method
- `_get_llm_decision()` - Prompts LLM for tool selection and parameter extraction
- `_execute_tool()` - Calls MCP server and handles validation errors
- `_repair_args()` - Uses LLM to fix invalid parameters

##### **ConversationAgent** ([graph/agents/conversation_agent.py](graph/agents/conversation_agent.py))
Manages conversation context and formatting. Responsibilities:
- Maintains conversation history
- Formats assistant messages for display

##### **Orchestrator** ([graph/agents/orchestrator.py](graph/agents/orchestrator.py))
Coordinates agent execution within the state graph:
- Delegates user requests to GenericMCPAgent
- Manages agent state and context

#### 4. **Core Services**

##### **MCPClient** ([graph/core/mcp_client.py](graph/core/mcp_client.py))
Low-level HTTP client for MCP server communication:
- `call_tool()` - Executes tool on MCP server
- `get_schema()` - Retrieves tool schema and metadata
- Handles HTTP requests, error handling, JSON serialization

##### **SchemaDiscovery** ([graph/core/schema_discovery.py](graph/core/schema_discovery.py))
Dynamically discovers tools from MCP server:
- `get_available_tools()` - Lists all tools with their schemas
- Parses tool parameters (params, body, query sections)
- Extracts field types and descriptions

##### **DecisionParser** ([graph/core/decision_parsing.py](graph/core/decision_parsing.py))
Parses LLM responses into structured decisions:
- Extracts JSON from LLM text
- Validates decision structure
- Handles malformed LLM responses

#### 5. **State Management** ([graph/core/state.py](graph/core/state.py))
Defines the state schema:
- Messages array (conversation history)
- Context object (metadata and user information)

#### 6. **Configuration** ([config.py](config.py))
- MCP server URL
- LLM model and connection details
- Debug flags

---

## System Features

### 1. **Dynamic Tool Discovery**
- Automatically queries MCP server for available tools
- No hardcoded tool names or schemas
- Supports any MCP server with any tool set

### 2. **Generic Parameter Extraction**
- LLM reads user request and schema
- Matches user values to schema fields semantic
- Works for any field name (id, name, category, etc.)
- Supports all parameter locations: params, body, query sections

### 3. **Error Recovery**
- Validates parameters against schema
- If validation fails, LLM is asked to repair
- Self-healing: retries up to 2 times automatically

### 4. **Natural Language Processing**
- User speaks naturally: "get all items", "create thing with id x5 name John"
- LLM interprets intent and extracts structured API calls
- No special syntax required

### 5. **Operation Types Supported**
- **List** - "list all", "get all X"
- **Get** - "get X with id abc", "find item X"
- **Create** - "create X with param1 value1 param2 value2"
- **Update** - "update X id123 with field newvalue"
- **Delete** - "delete X with id abc"

---

## Implementation Details

### LLM Prompt Strategy
The `_get_llm_decision()` method uses a detailed prompt that:
1. Shows all available tools with their schemas
2. Explains tool selection logic (match action keyword + resource type)
3. Provides parameter extraction rules
4. Gives concrete examples for each operation type
5. Specifies JSON-only response format

**Key Design:**
- **Domain-Agnostic** - Uses generic terms (item, thing, record, widget) in examples
- **Schema-Driven** - All parameter info comes from MCP server schema
- **Explicit Rules** - Step-by-step instructions for LLM to follow

### Parameter Repair Strategy
When validation fails:
1. MCP server returns error message (missing/invalid fields)
2. Repair prompt shows original request + validation error
3. LLM extracts correct values from user request
4. Resubmit with corrected parameters

### Result Formatting
Results are formatted as:
- Count of records (if list operation)
- Numbered list with field display
- Success/error status
- Human-readable messages

---

## Configuration

### Environment Variables
```bash
OLLAMA_MODEL=llama3.2:3b            # LLM model to use
OLLAMA_URL=http://localhost:11434   # Ollama server URL
MCP_URL=http://localhost:4000/mcp   # MCP server URL
DEBUG_SCHEMA=false                  # Enable schema debug logging
DEBUG_TOOLS=false                   # Enable tool execution logging
```

### Key URLs
- **Ollama LLM**: `http://localhost:11434` (serving `llama3.2:3b`)
- **MCP Server**: `http://localhost:4000/mcp` (serves tools via Model Context Protocol)

---

## File Structure (Cleaned)

```
school-ai-agent/
├── run.py                          # Entry point - continuous chat loop
├── config.py                       # Configuration management
├── requirements.txt                # Python dependencies
│
├── graph/
│   ├── build_graph.py             # State graph construction
│   │
│   ├── agents/
│   │   ├── generic_mcp_agent.py   # Core LLM agent (tool selection + execution)
│   │   ├── conversation_agent.py  # Conversation formatting
│   │   └── orchestrator.py        # Agent coordination
│   │
│   └── core/
│       ├── mcp_client.py          # MCP server HTTP client
│       ├── schema_discovery.py    # Tool schema discovery from MCP
│       ├── decision_parsing.py    # JSON parsing from LLM responses
│       └── state.py               # State schema definition
│
└── .gitignore                     # Git ignore rules
```

---

## Development Workflow

### Running the Agent
```bash
python run.py
```

Starts an interactive chat loop where you can type natural language requests:
```
Welcome to School AI Agent
Type 'exit' or 'bye' to quit
============================================================

You: get all students
Assistant: Found 52 record(s):
[1] student_id: s1, name: student 1, class_id: c1
[2] student_id: s10, name: student 10, class_id: c5
...

You: exit
Goodbye!
```

### Using Different MCP Servers
Just change the `MCP_URL` in config.py or environment variable. The agent will automatically:
1. Discover tools from the new server
2. Adjust prompts based on new tool schemas
3. Execute requests against new tools

### Adding Custom Logic
If you need domain-specific behavior:
1. Extend `ConversationAgent` for custom formatting
2. Modify `_build_tool_schema_text()` in `GenericMCPAgent` for custom schema display
3. Update prompt in `_get_llm_decision()` for custom instructions
4. Extend state in `state.py` for custom context

---

## Key Achievements

### ✅ Completed
1. **Dynamic MCP Integration** - Works with any MCP server without hardcoding tools
2. **Generic LLM Prompting** - No domain assumption in prompts; works for any resource type
3. **Continuous Chat Loop** - User-friendly interactive experience
4. **Error Recovery** - Automatic parameter repair on validation failures
5. **Natural Language Interface** - Users speak naturally, system interprets intent
6. **Human-Readable Output** - Results formatted for easy reading

### 🐛 Known Issues Fixed
- JSON parsing error when LLM returns array instead of object (FIXED: type checking added)
- Continuous chat with exit handling (FIXED: implemented in run.py)

### 🚀 System Stability
- Graceful error handling throughout
- Retry logic for validation failures
- Fallback imports for compatibility
- Async/await for non-blocking operations

---

## Testing Examples

### List Operations
```
You: list all
→ Executes list tool with no parameters
→ Returns all records formatted
```

### Get by ID
```
You: get student with id s101
→ Extracts param: id=s101
→ Executes get tool
→ Returns single record
```

### Create with Parameters
```
You: create item with id x789 name Alice in group g5
→ Extracts: id=x789, name=Alice, group_id=g5
→ Executes create tool
→ Returns created record details
```

### Update Operations
```
You: update record rec12 with status pending name NewName
→ Extracts: id=rec12 (in params), status=pending, name=NewName (in body)
→ Executes update tool
→ Returns updated record
```

### Delete Operations
```
You: delete item item456
→ Extracts param: id=item456
→ Executes delete tool
→ Returns confirmation
```

---

## Dependencies

### Core
- `langchain-ollama` or `langchain-community` - LLM integration
- `aiohttp` - Async HTTP client for MCP
- `langgraph` - State graph management

### Infrastructure
- **Ollama** - Local LLM server (running llama3.2:3b)
- **MCP Server** - Custom server implementing tools

See [requirements.txt](requirements.txt) for full list.

---

## Next Steps for Future Development

1. **Multi-turn Conversation Context** - Remember previous requests in conversation
2. **Advanced Error Recovery** - Handle more complex validation error patterns
3. **Result Caching** - Cache repeated queries for performance
4. **Audit Logging** - Log all operations for compliance
5. **Permission System** - Control which tools users can access
6. **API Versioning** - Support multiple schema versions
7. **Batch Operations** - Process multiple requests in one invocation

---

## Debugging

### Enable Debug Logging
```bash
DEBUG_SCHEMA=true DEBUG_TOOLS=true python run.py
```

### Check Schema Discovery
```python
from graph.core.mcp_client import MCPClient
from graph.core.schema_discovery import SchemaDiscovery

client = MCPClient("http://localhost:4000/mcp")
discovery = SchemaDiscovery(client)
tools = asyncio.run(discovery.get_available_tools())
print(json.dumps(tools, indent=2))
```

### Check Tool Execution
Add debug print statements in `_execute_tool()` in `generic_mcp_agent.py`

---

## Project Statistics

- **Total Files**: 13 (code files)
- **Main Entry Point**: 1 (run.py)
- **Agent Classes**: 3 (GenericMCPAgent, ConversationAgent, Orchestrator)
- **Service Classes**: 3 (MCPClient, SchemaDiscovery, DecisionParser)
- **Lines of Code**: ~1,500 (core logic)
- **Supported Operations**: 5 (List, Get, Create, Update, Delete)

---

## Contact & Documentation

For more details on:
- **MCP Protocol**: Refer to MCP specification
- **LLM Prompting**: See comments in `_get_llm_decision()` method
- **Tool Schemas**: Query MCP server `/schema` endpoint or enable `DEBUG_SCHEMA=true`
