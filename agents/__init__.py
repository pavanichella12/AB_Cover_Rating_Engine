"""
Multi-Agent System for School Absence Data Analysis
LLM-Powered Agentic AI System with Blackboard Pattern
"""

# Blackboard (Shared Memory)
from .blackboard import Blackboard

# LangGraph Orchestrator
from .orchestrator_langgraph import LangGraphOrchestrator, AgentState

# Deterministic Agents
from .file_upload_agent import FileUploadAgent
from .data_selection_agent import DataSelectionAgent
from .data_cleaning_agent import DataCleaningAgent

# LLM-Powered Agents
from .data_analysis_agent import DataAnalysisAgent
from .data_cleaning_agent_llm import DataCleaningAgentLLM
from .rating_engine_agent_llm import RatingEngineAgentLLM

# Legacy (deterministic) Rating Engine Agent (optional)
try:
    from .rating_engine_agent import RatingEngineAgent
except ImportError:
    RatingEngineAgent = None

__all__ = [
    'Blackboard',  # Shared memory
    'LangGraphOrchestrator',  # LangGraph orchestrator with state
    'AgentState',  # State type for LangGraph
    'FileUploadAgent',
    'DataSelectionAgent',
    'DataCleaningAgent',  # Deterministic version
    'DataCleaningAgentLLM',  # LLM-powered version
    'DataAnalysisAgent',  # LLM-powered
    'RatingEngineAgentLLM',  # LLM-powered
    'RatingEngineAgent'  # Optional deterministic version
]
