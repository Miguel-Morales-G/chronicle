import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from chronicle.llm.azure_openai_client import LLMResponse


# Log file placed alongside the existing tokens_usage.log in tools/
_DEFAULT_LOG_FILE = (
    Path(__file__).parent.parent.parent.parent / "tools" / "tokens_usage.log"
)


def log_token_usage(
    response: Union[LLMResponse, object],
    caller: str,
    log_file: Union[str, Path, None] = None,
) -> None:
    """Append a token-usage entry to the token log.

    Accepts either a :class:`~chronicle.llm.azure_openai_client.LLMResponse`
    (preferred) or any object with a ``.usage`` attribute (legacy compatibility
    with raw Azure OpenAI completion objects).

    Args:
        response: An ``LLMResponse`` or raw Azure OpenAI completion object.
        caller:   Name of the script or agent that made the request.
        log_file: Optional path override for the log file.  Defaults to
                  ``tools/tokens_usage.log`` relative to the repo root.
    """
    if isinstance(response, LLMResponse):
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        total_tokens = response.total_tokens
    else:
        # Legacy path: raw Azure OpenAI completion object
        usage = response.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens

    entry = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "function_that_called": caller,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
        },
    }

    target = Path(log_file) if log_file else _DEFAULT_LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
