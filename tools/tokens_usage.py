import json
import os
from datetime import datetime, timezone


LOG_FILE = os.path.join(os.path.dirname(__file__), "tokens_usage.log")


def log_token_usage(completion, caller: str) -> None:
    """
    Appends a token usage entry to tokens_usage.log.

    Args:
        completion: The chat completion response object from Azure OpenAI.
        caller:     Name of the script or function that made the request.
    """
    entry = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "function_that_called": caller,
        "tokens": {
            "prompt": completion.usage.prompt_tokens,
            "completion": completion.usage.completion_tokens,
            "total": completion.usage.total_tokens,
        },
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
