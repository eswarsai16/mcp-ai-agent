"""
Generic orchestrator - routes conversation to GenericMCPAgent.
No business logic, no school knowledge.
"""
from typing import Dict, Any
from .generic_mcp_agent import GenericMCPAgent
from .conversation_agent import ConversationAgent
from ..core.state import AgentState


class GenericOrchestrator:
    """
    Routes user requests to the appropriate handler.
    1. ConversationAgent: understand user intent
    2. GenericMCPAgent: execute the MCP tool
    3. ConversationAgent: respond to user with actual data
    """
    
    def __init__(self, mcp_url: str = "http://localhost:4000/mcp"):
        self.mcp_agent = GenericMCPAgent(mcp_url)
        self.conversation_agent = ConversationAgent()
    
    async def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Execute orchestration:
        1. Extract intent from user message
        2. Call GenericMCPAgent
        3. Format response for user with actual data
        """
        # Handle both dict and object state
        if isinstance(state, dict):
            messages = state.get("messages", [])
            context = state.get("context", {})
        else:
            messages = state.messages if hasattr(state, "messages") else []
            context = state.context if hasattr(state, "context") else {}
        
        user_message = messages[-1]["content"] if messages else ""
        
        # Execute via generic agent
        execution_result = await self.mcp_agent.execute(
            user_request=user_message,
            context=context or {}
        )
        
        # Format response - this will include actual data
        response = await self.conversation_agent.format_response(
            user_request=user_message,
            execution_result=execution_result
        )
        
        return {
            "messages": messages + [{"role": "assistant", "content": response}],
            "context": context,
            "execution_result": execution_result
        }
