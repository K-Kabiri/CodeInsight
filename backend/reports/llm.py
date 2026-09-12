import json
import time
import urllib.error
import urllib.request

from django.conf import settings

from reports.ai_errors import (
    LLMNotConfiguredError,
    LLMRequestError,
)

# Module-level alias so tests patch the exact seam without touching
# urllib globally.
urlopen = urllib.request.urlopen

# Module-level alias so retry tests patch the wait instead of sleeping.
sleep = time.sleep

# HTTP statuses worth retrying: rate limiting (429) and transient
# server faults. Client errors (4xx other than 429) are never retried.
RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})

# Capped exponential backoff between attempts (seconds): 1, 2, 4, 8, ...
RETRY_BACKOFF_INITIAL = 1.0
RETRY_BACKOFF_CAP = 8.0


class LLMClient:
    """
    The single network seam of the AI-report work: a thin,
    provider-agnostic OpenAI-compatible chat call.

    Everything about the provider (base URL, model, key, timeout)
    comes from settings via python-decouple, so pointing at another
    provider is purely a configuration change. No code path here is
    provider-specific. Tests never reach the network: they inject
    fakes by patching `reports.llm.urlopen`, and a missing key raises
    before any request is attempted.

    Transient provider failures (HTTP 429/5xx, network errors,
    timeouts) are retried with a capped exponential backoff when
    `max_attempts` (settings `LLM_RETRY_ATTEMPTS`) is greater than 1,
    so rate-limit hiccups self-heal instead of failing the report.
    """

    def __init__(
            self,
            base_url: str | None = None,
            model: str | None = None,
            api_key: str | None = None,
            timeout: int | None = None,
            max_attempts: int | None = None,
    ):
        self.base_url = (
            base_url if base_url is not None
            else settings.LLM_BASE_URL
        ).rstrip("/")
        self.model = (
            model if model is not None
            else settings.LLM_MODEL
        )
        self.api_key = (
            api_key if api_key is not None
            else settings.LLM_API_KEY
        )
        self.timeout = (
            timeout if timeout is not None
            else settings.LLM_TIMEOUT
        )
        # How many times the request is attempted: rate limits and
        # transient faults self-heal on the retry (LLM_RETRY_ATTEMPTS).
        self.max_attempts = (
            max_attempts if max_attempts is not None
            else settings.LLM_RETRY_ATTEMPTS
        )

    @property
    def chat_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        """Capped exponential backoff after the failed attempt number."""
        return min(
            RETRY_BACKOFF_INITIAL * (2 ** (attempt - 1)),
            RETRY_BACKOFF_CAP,
        )

    def chat(self, messages: list[dict]) -> str:
        """
        Send one chat request and return the assistant's text.

        `messages` is the OpenAI-style list of role/content dicts
        produced by the prompt builder.
        """
        if not self.api_key:
            raise LLMNotConfiguredError(
                "LLM_API_KEY is not configured — set it in the "
                "environment to enable AI report generation."
            )

        payload = {
            "model": self.model,
            "messages": messages,
        }

        attempts = max(1, self.max_attempts)

        for attempt in range(1, attempts + 1):
            request = urllib.request.Request(
                self.chat_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )

            try:
                with urlopen(
                        request,
                        timeout=self.timeout,
                ) as response:
                    raw = response.read().decode("utf-8")
                    break
            except urllib.error.HTTPError as exc:
                if (
                        exc.code in RETRYABLE_CODES
                        and attempt < attempts
                ):
                    sleep(self._retry_delay(attempt))
                    continue
                raise LLMRequestError(
                    f"Provider returned HTTP {exc.code}: {exc.reason}",
                    status_code=exc.code,
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < attempts:
                    sleep(self._retry_delay(attempt))
                    continue
                raise LLMRequestError(
                    f"Provider request failed: {exc.reason}"
                ) from exc
            except TimeoutError as exc:
                if attempt < attempts:
                    sleep(self._retry_delay(attempt))
                    continue
                raise LLMRequestError(
                    f"Provider request timed out after "
                    f"{self.timeout} seconds"
                ) from exc
            except OSError as exc:
                if attempt < attempts:
                    sleep(self._retry_delay(attempt))
                    continue
                raise LLMRequestError(
                    f"Provider request failed: {exc}"
                ) from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMRequestError(
                f"Unexpected provider response: {exc}"
            ) from exc

        if not isinstance(content, str):
            raise LLMRequestError(
                "Provider returned a non-text chat completion."
            )

        return content.strip()
