import json
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
    """

    def __init__(
            self,
            base_url: str | None = None,
            model: str | None = None,
            api_key: str | None = None,
            timeout: int | None = None,
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

    @property
    def chat_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

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
        except urllib.error.HTTPError as exc:
            raise LLMRequestError(
                f"Provider returned HTTP {exc.code}: {exc.reason}",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(
                f"Provider request failed: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise LLMRequestError(
                f"Provider request timed out after "
                f"{self.timeout} seconds"
            ) from exc
        except OSError as exc:
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
