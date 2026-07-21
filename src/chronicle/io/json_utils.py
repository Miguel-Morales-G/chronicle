import json


class ChronicleJsonError(ValueError):
    """Raised when the LLM response cannot be parsed as valid JSON.

    Attributes:
        raw_text: The raw text returned by the model, preserved for debugging.
    """

    def __init__(self, message: str, raw_text: str) -> None:
        super().__init__(message)
        self.raw_text = raw_text


def clean_json_markdown(text: str) -> str:
    """Strip Markdown code-block markers (``` or ```json) from model output.

    Args:
        text: The raw text from the LLM response.

    Returns:
        The text with leading/trailing code-block markers removed.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:].lstrip("\r\n")
    elif text.startswith("```"):
        text = text[3:].lstrip("\r\n")
    if text.endswith("```"):
        text = text[:-3].rstrip("\r\n")
    return text.strip()


def safe_parse_json(text: str) -> dict:
    """Parse a JSON string, raising ChronicleJsonError on failure.

    Strips Markdown code-block markers before parsing.

    Args:
        text: The JSON string to parse (may contain Markdown code-block markers).

    Returns:
        The parsed dict.

    Raises:
        ChronicleJsonError: If the text cannot be parsed as valid JSON.
    """
    cleaned = clean_json_markdown(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ChronicleJsonError(
            f"Model response is not valid JSON: {exc}",
            raw_text=cleaned,
        ) from exc
