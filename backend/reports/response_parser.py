import json
import re

from reports.ai_errors import AIResponseParseError

# Optional ```json fences some providers wrap around the response.
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def parse_response(text: str) -> dict:
    """
    Map the model's text onto the AIReport fields.

    Expects one JSON object of the agreed shape:
    {"summary": str, "metric_content": {NAME: {"explanation": str,
    "suggestions": [str, ...]}}}. Returns exactly that structure
    (missing "metric_content" and missing/empty "suggestions" are
    tolerated); anything structurally different raises
    AIResponseParseError so the caller can surface a readable error.
    """
    if not isinstance(text, str) or not text.strip():
        raise AIResponseParseError(
            "The model returned an empty response."
        )

    cleaned = _FENCE_RE.sub("", text.strip()).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIResponseParseError(
            f"The model response is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise AIResponseParseError(
            "The model response must be a single JSON object."
        )

    summary = data.get("summary")

    if not isinstance(summary, str) or not summary.strip():
        raise AIResponseParseError(
            "The model response is missing a non-empty 'summary' string."
        )

    raw_content = data.get("metric_content", {})

    if raw_content is None:
        raw_content = {}

    if not isinstance(raw_content, dict):
        raise AIResponseParseError(
            "'metric_content' must be a JSON object keyed by "
            "canonical metric name."
        )

    metric_content = {}

    for name, entry in raw_content.items():
        if not isinstance(entry, dict):
            raise AIResponseParseError(
                f"The content for metric {name!r} must be an object."
            )

        explanation = entry.get("explanation")

        if (
                not isinstance(explanation, str)
                or not explanation.strip()
        ):
            raise AIResponseParseError(
                f"The content for metric {name!r} is missing a "
                "non-empty 'explanation' string."
            )

        suggestions = entry.get("suggestions", [])

        if suggestions is None:
            suggestions = []

        if not isinstance(suggestions, list):
            raise AIResponseParseError(
                f"'suggestions' for metric {name!r} must be a list "
                "of strings."
            )

        normalized_suggestions = []

        for suggestion in suggestions:
            if not isinstance(suggestion, str):
                raise AIResponseParseError(
                    f"'suggestions' for metric {name!r} must contain "
                    "only strings."
                )

            if suggestion.strip():
                normalized_suggestions.append(suggestion.strip())

        metric_content[name] = {
            "explanation": explanation.strip(),
            "suggestions": normalized_suggestions,
        }

    return {
        "summary": summary.strip(),
        "metric_content": metric_content,
    }
