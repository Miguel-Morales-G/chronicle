from abc import ABC, abstractmethod
from typing import Any

from chronicle.io.prompt_loader import load_prompt
from chronicle.llm.azure_openai_client import LLMResponse
from chronicle.llm.token_logger import log_token_usage


class BaseAgent(ABC):
    """Abstract base class for all Chronicle agents.

    Provides shared behaviour:
    - Loading the agent's system prompt from a markdown file.
    - Calling the injected LLM client and logging token usage.
    - A common ``run()`` interface enforced on all subclasses.

    Args:
        name:               Human-readable agent name used in logging and token records.
        system_prompt_path: Path to the agent's markdown system-prompt file.
        llm_client:         Any object that implements
                            ``complete(system_prompt, user_prompt, max_tokens) -> LLMResponse``.
    """

    def __init__(self, name: str, system_prompt_path: str, llm_client: Any) -> None:
        self.name = name
        self.system_prompt_path = system_prompt_path
        self.llm_client = llm_client

    def load_system_prompt(self) -> str:
        """Load and return the system prompt for this agent.

        Returns:
            The contents of the system prompt markdown file.

        Raises:
            FileNotFoundError: If the system prompt file does not exist.
        """
        return load_prompt(self.system_prompt_path)

    def _call_llm(self, user_prompt: str, max_tokens: int = 800) -> LLMResponse:
        """Load the system prompt, call the LLM client, and log token usage.

        Args:
            user_prompt: The user-turn prompt to send.
            max_tokens:  Maximum number of completion tokens.

        Returns:
            An ``LLMResponse`` with the model's text and token counts.
        """
        system_prompt = self.load_system_prompt()
        response = self.llm_client.complete(system_prompt, user_prompt, max_tokens)
        try:
            log_token_usage(response, caller=self.name)
        except Exception as exc:
            print(f"[warn] token logging failed for {self.name}: {exc}")
        return response

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's primary task.

        Must be implemented by every subclass.
        """
        raise NotImplementedError
