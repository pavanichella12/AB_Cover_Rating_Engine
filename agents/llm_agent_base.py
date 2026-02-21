"""
Base LLM Agent Class - All LLM-powered agents inherit from this
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Optional imports for different LLM providers
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None

try:
    from langchain_aws import ChatBedrockConverse
except ImportError:
    ChatBedrockConverse = None

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

load_dotenv()


class LLMAgentBase(ABC):
    """
    Base class for LLM-powered agents.
    Provides LLM initialization and common methods.
    """
    
    def __init__(self, agent_name: str, model_provider: str = "google", model_name: Optional[str] = None):
        """
        Initialize LLM agent.
        
        Args:
            agent_name: Name of the agent
            model_provider: "google" (free, default), "openai", "anthropic", or "bedrock"
            model_name: Specific model name (e.g., "gemini-1.5-flash", "gpt-4", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        """
        self.agent_name = agent_name
        self.model_provider = model_provider
        self.llm = self._initialize_llm(model_name)
        self.system_prompt = self._get_system_prompt()
    
    def _initialize_llm(self, model_name: Optional[str]) -> Any:
        """Initialize the LLM based on provider."""
        if self.model_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            return ChatOpenAI(
                model=model_name or "gpt-4-turbo-preview",
                temperature=0.3,  # Lower temperature for more consistent reasoning
                api_key=api_key
            )
        elif self.model_provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            return ChatAnthropic(
                model=model_name or "claude-3-opus-20240229",
                temperature=0.3,
                api_key=api_key
            )
        elif self.model_provider == "google" or self.model_provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    "GOOGLE_API_KEY not found in environment variables.\n"
                    "Get FREE API key from: https://makersuite.google.com/app/apikey\n"
                    "1. Go to the link above\n"
                    "2. Sign in with Google account\n"
                    "3. Click 'Create API Key'\n"
                    "4. Copy the key and add to .env file: GOOGLE_API_KEY=your_key_here"
                )
            return ChatGoogleGenerativeAI(
                model=model_name or "gemini-2.5-flash",  # Verified working model (free, fast)
                temperature=0.3,
                google_api_key=api_key
            )
        elif self.model_provider == "bedrock":
            if ChatBedrockConverse is None:
                raise ValueError(
                    "langchain-aws is required for Bedrock. Install with: pip install langchain-aws"
                )
            region = (os.getenv("AWS_REGION") or "").strip() or "us-east-1"
            model_id = model_name or "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            return ChatBedrockConverse(
                model=model_id,
                temperature=0.3,
                region_name=region,
            )
        else:
            raise ValueError(
                f"Unsupported model provider: {self.model_provider}. "
                "Supported: 'google' (free), 'openai', 'anthropic', 'bedrock'"
            )
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    def _call_llm(self, user_message: str, context: Optional[Dict] = None) -> str:
        """
        Call the LLM with a user message and optional context.
        
        Args:
            user_message: The user's message/query
            context: Optional context dictionary to include
            
        Returns:
            LLM response as string
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def _call_llm_with_tools(self, user_message: str, tools: list, context: Optional[Dict] = None) -> Any:
        """
        Call LLM with tools (for more complex reasoning).
        Override in subclasses if needed.
        """
        # This can be extended with LangChain tools
        return self._call_llm(user_message, context)
    
    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """Process method that each agent must implement."""
        pass
