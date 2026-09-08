class AIReportError(Exception):
    """Base for every AI-report failure the service must handle."""


class LLMNotConfiguredError(AIReportError):
    """No API key configured — the seam refuses to call out."""


class LLMRequestError(AIReportError):
    """
    The provider call failed (HTTP error, timeout, network error, or
    an unexpected response shape).
    """

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AIResponseParseError(AIReportError):
    """The model's text was not the agreed structured JSON response."""
