"""
Configuration file to switch between school-specific and generic agents.
Allows for gradual migration and A/B testing.
"""

import os
from enum import Enum


class AgentMode(Enum):
    """Choose which agent system to use."""
    GENERIC = "generic"  # New: Schema-driven, works with any MCP API
    SCHOOL = "school"    # Old: School-specific hardcoded logic


# ============================================================================
# MAIN CONFIGURATION
# ============================================================================

# Which agent system to use
AGENT_MODE = AgentMode.GENERIC

# MCP Server URL
MCP_URL = os.getenv("MCP_URL", "http://localhost:4000/mcp")

# LLM Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
LLM_TEMPERATURE = 0

# ============================================================================
# IMPORT BASED ON MODE
# ============================================================================

def get_graph():
    """Get the appropriate graph based on configuration."""
    
    if AGENT_MODE == AgentMode.GENERIC:
        print("Using GENERIC agent (schema-driven, dynamic)")
        from graph.build_graph import build_generic_mcp_graph
        return build_generic_mcp_graph(mcp_url=MCP_URL)
    
    elif AGENT_MODE == AgentMode.SCHOOL:
        print("Using SCHOOL agent (hardcoded logic, school-specific)")
        # Keep old import for backwards compatibility if needed
        from graph.build_graph_old import build_graph
        return build_graph()
    
    else:
        raise ValueError(f"Unknown agent mode: {AGENT_MODE}")


def get_orchestrator():
    """Get the appropriate orchestrator based on configuration."""
    
    if AGENT_MODE == AgentMode.GENERIC:
        from graph.agents.orchestrator import GenericOrchestrator
        return GenericOrchestrator(mcp_url=MCP_URL)
    
    elif AGENT_MODE == AgentMode.SCHOOL:
        from graph.agents.orchestrator_old import SchoolOrchestrator
        return SchoolOrchestrator()
    
    else:
        raise ValueError(f"Unknown agent mode: {AGENT_MODE}")


# ============================================================================
# ENVIRONMENT OVERRIDES
# ============================================================================

# Allow environment variables to override
_env_mode = os.getenv("AGENT_MODE", "").upper()
if _env_mode:
    try:
        AGENT_MODE = AgentMode[_env_mode]
    except KeyError:
        print(f"Invalid AGENT_MODE: {_env_mode}. Using default: {AGENT_MODE}")


# ============================================================================
# FEATURE FLAGS
# ============================================================================

FEATURES = {
    # Enable/disable generic features
    "schema_discovery": AGENT_MODE == AgentMode.GENERIC,
    "dynamic_tool_selection": AGENT_MODE == AgentMode.GENERIC,
    "generic_error_repair": AGENT_MODE == AgentMode.GENERIC,
    
    # Enable/disable school-specific features
    "hardcoded_entities": AGENT_MODE == AgentMode.SCHOOL,
    "school_validation": AGENT_MODE == AgentMode.SCHOOL,
    "school_error_messages": AGENT_MODE == AgentMode.SCHOOL,
    
    # Debug features
    "debug_schema_discovery": os.getenv("DEBUG_SCHEMA", "false").lower() == "true",
    "debug_llm_decisions": os.getenv("DEBUG_LLM", "false").lower() == "true",
    "debug_tool_execution": os.getenv("DEBUG_TOOLS", "false").lower() == "true",
}


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
# Option 1: Use default configuration
python run.py

# Option 2: Switch to school mode
AGENT_MODE=SCHOOL python run.py

# Option 3: Enable debug logging
DEBUG_SCHEMA=true DEBUG_LLM=true python run.py

# Option 4: Change MCP URL
MCP_URL=http://localhost:5000/mcp python run.py

# Option 5: All together
AGENT_MODE=GENERIC MCP_URL=http://localhost:4000/mcp DEBUG_LLM=true python run.py
"""


# ============================================================================
# STATUS INFO
# ============================================================================

def print_config():
    """Print current configuration."""
    print("\n" + "="*60)
    print("AGENT CONFIGURATION")
    print("="*60)
    print(f"Mode: {AGENT_MODE.value}")
    print(f"MCP URL: {MCP_URL}")
    print(f"LLM Model: {LLM_MODEL}")
    print("\nFeatures Enabled:")
    for feature, enabled in FEATURES.items():
        status = "✓" if enabled else "✗"
        print(f"  {status} {feature}")
    print("="*60 + "\n")


if __name__ == "__main__":
    print_config()
