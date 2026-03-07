"""
Base LLM Agent Class - All LLM-powered agents inherit from this.
Includes observability (prompt/response/tokens/timing) and error recovery (retries + optional fallback).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import logging

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

# Observability: log LLM calls (prompt length, response length, duration, token usage if available)
_LLM_LOGGER = logging.getLogger("abcover.llm")


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
            model_name: Specific model name (e.g., "gemini-1.5-flash", "gpt-4"; for Bedrock use inference profile ID like "us.anthropic.claude-3-5-sonnet-20241022-v2:0")
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
            # Use inference profile ID (us.*) for on-demand; raw model ID causes ValidationException
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
    
    def _get_fallback_llm(self) -> Optional[Any]:
        """Optional fallback LLM (e.g. Google) if primary fails. Override or set via env."""
        fallback_provider = (os.getenv("LLM_FALLBACK_PROVIDER") or "").strip().lower()
        if not fallback_provider or fallback_provider == self.model_provider:
            return None
        try:
            if fallback_provider == "google" or fallback_provider == "gemini":
                api_key = os.getenv("GOOGLE_API_KEY")
                if api_key:
                    return ChatGoogleGenerativeAI(
                        model=os.getenv("LLM_MODEL") or "gemini-2.5-flash",
                        temperature=0.3,
                        google_api_key=api_key,
                    )
        except Exception:
            pass
        return None

    def _call_llm(self, user_message: str, context: Optional[Dict] = None) -> str:
        """
        Call the LLM with retries, optional fallback, and observability logging.
        Logs: agent name, prompt length, response length, duration, token usage (if available).
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_message),
        ]
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        retry_delay = float(os.getenv("LLM_RETRY_DELAY", "1.0"))

        last_error = None
        for attempt in range(max_retries):
            try:
                start = time.perf_counter()
                response = self.llm.invoke(messages)
                duration_sec = time.perf_counter() - start
                content = response.content if hasattr(response, "content") else str(response)
                # Token usage (LangChain often puts it in response_metadata or usage_metadata)
                usage = {}
                if hasattr(response, "response_metadata") and response.response_metadata:
                    usage = response.response_metadata.get("usage", response.response_metadata)
                if not usage and hasattr(response, "usage_metadata") and response.usage_metadata:
                    usage = {
                        "input_tokens": getattr(response.usage_metadata, "input_tokens", None),
                        "output_tokens": getattr(response.usage_metadata, "output_tokens", None),
                    }
                # Observability log (no full prompt/response to avoid huge logs; use LANGCHAIN_TRACING for full traces)
                _LLM_LOGGER.info(
                    "llm_call agent=%s provider=%s prompt_len=%d response_len=%d duration_sec=%.2f input_tokens=%s output_tokens=%s attempt=%d",
                    self.agent_name,
                    self.model_provider,
                    len(self.system_prompt) + len(user_message),
                    len(content),
                    duration_sec,
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                    attempt + 1,
                )
                return content
            except Exception as e:
                last_error = e
                _LLM_LOGGER.warning(
                    "llm_call attempt %d failed agent=%s error=%s",
                    attempt + 1,
                    self.agent_name,
                    str(e),
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                continue

        # Retries exhausted: try fallback model if configured
        fallback = self._get_fallback_llm()
        if fallback is not None:
            try:
                start = time.perf_counter()
                response = fallback.invoke(messages)
                duration_sec = time.perf_counter() - start
                content = response.content if hasattr(response, "content") else str(response)
                _LLM_LOGGER.info(
                    "llm_call fallback agent=%s prompt_len=%d response_len=%d duration_sec=%.2f",
                    self.agent_name,
                    len(self.system_prompt) + len(user_message),
                    len(content),
                    duration_sec,
                )
                return content
            except Exception as fallback_err:
                _LLM_LOGGER.error("llm_call fallback failed agent=%s error=%s", self.agent_name, str(fallback_err))
                raise last_error from fallback_err
        raise last_error
    
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
