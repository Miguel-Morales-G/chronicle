import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from openai import AzureOpenAI


@dataclass
class LLMResponse:
    """Encapsulates a single LLM completion result.

    Attributes:
        text:              The text content of the model's response.
        prompt_tokens:     Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens:      Total tokens consumed.
    """

    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AzureOpenAIClient:
    """Thin wrapper around the Azure OpenAI chat-completion API.

    Designed for dependency injection: tests substitute a ``FakeLLMClient``
    that satisfies the same ``complete()`` interface without network calls.

    Args:
        endpoint:    Azure OpenAI endpoint URL.
        deployment:  Azure OpenAI deployment/model name.
        api_key:     Azure OpenAI API key.
        api_version: API version string (default: ``"2025-01-01-preview"``).
    """

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_key: str,
        api_version: str = "2025-01-01-preview",
    ) -> None:
        self._deployment = deployment
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "AzureOpenAIClient":
        """Construct an ``AzureOpenAIClient`` from environment variables.

        Loads a ``.env`` file if present (or from ``env_file`` if provided),
        then reads ``ENDPOINT_URL``, ``DEPLOYMENT_NAME``, and
        ``AZURE_OPENAI_API_KEY``.

        Args:
            env_file: Optional path to a ``.env`` file to load explicitly.

        Returns:
            A configured ``AzureOpenAIClient`` instance.

        Raises:
            EnvironmentError: If any required environment variable is missing.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        endpoint = os.getenv("ENDPOINT_URL")
        deployment = os.getenv("DEPLOYMENT_NAME")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")

        missing = [
            name
            for name, val in {
                "ENDPOINT_URL": endpoint,
                "DEPLOYMENT_NAME": deployment,
                "AZURE_OPENAI_API_KEY": api_key,
            }.items()
            if not val
        ]
        if missing:
            raise EnvironmentError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + "\nSet them in your environment or in a .env file."
            )

        return cls(endpoint=endpoint, deployment=deployment, api_key=api_key)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Send a chat completion request and return an ``LLMResponse``.

        Args:
            system_prompt: The system message content.
            user_prompt:   The user message content.
            max_tokens:    Maximum number of completion tokens.

        Returns:
            An ``LLMResponse`` containing the response text and token counts.
        """
        messages = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
        ]
        completion = self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            max_completion_tokens=max_tokens,
            stop=None,
            stream=False,
        )
        text = self._extract_text(completion)
        usage = completion.usage
        return LLMResponse(
            text=text,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

    @staticmethod
    def _extract_text(completion) -> str:
        """Extract string content from a chat completion response.

        Handles both plain-string and list-of-parts content shapes returned
        by different SDK versions.
        """
        content = completion.choices[0].message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts).strip()
        return str(content).strip()
