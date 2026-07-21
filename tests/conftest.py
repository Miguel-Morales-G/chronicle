"""
Shared test helpers and fixtures for the Chronicle test suite.

FakeLLMClient is a drop-in replacement for AzureOpenAIClient that returns
pre-programmed text responses without making any network calls.
It records every call so tests can assert on prompts sent.
"""
from chronicle.llm.azure_openai_client import LLMResponse


class FakeLLMClient:
    """Fake LLM client for testing.

    Returns pre-programmed string responses in FIFO order.
    Records every ``complete()`` call for assertion in tests.
    """

    def __init__(self, responses=None):
        """
        Args:
            responses: Ordered list of text strings to return, one per ``complete()`` call.
                       If exhausted, subsequent calls return an empty string.
        """
        self._responses = list(responses or [])
        self.calls = []

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> LLMResponse:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
            }
        )
        text = self._responses.pop(0) if self._responses else ""
        return LLMResponse(
            text=text,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
