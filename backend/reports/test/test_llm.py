import io
import json
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from reports.ai_errors import (
    LLMNotConfiguredError,
    LLMRequestError,
)
from reports.llm import LLMClient


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _completion_body(content: str) -> bytes:
    return json.dumps(
        {
            "choices": [
                {"message": {"content": content}}
            ]
        }
    ).encode("utf-8")


class LLMClientTest(SimpleTestCase):
    """
    The seam is exercised only through fakes (ADR-0002 spirit): the
    network is patched at `reports.llm.urlopen`, and a missing key
    raises before any request would be attempted.
    """

    def _client(self, **overrides):
        defaults = {
            "base_url": "https://provider.example/v1/",
            "model": "glm-4.5-flash",
            "api_key": "secret-key",
            "timeout": 7,
        }
        defaults.update(overrides)
        return LLMClient(**defaults)

    def test_missing_key_raises_without_any_request(self):
        client = self._client(api_key="")

        with mock.patch(
                "reports.llm.urlopen"
        ) as fake_urlopen:
            with self.assertRaises(LLMNotConfiguredError):
                client.chat([{"role": "user", "content": "hi"}])

        fake_urlopen.assert_not_called()

    def test_chat_posts_payload_and_returns_content(self):
        client = self._client()
        messages = [
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "evidence here"},
        ]

        with mock.patch(
                "reports.llm.urlopen"
        ) as fake_urlopen:
            fake_urlopen.return_value = FakeResponse(
                _completion_body("  Hello, analysis.  ")
            )

            content = client.chat(messages)

        self.assertEqual(content, "Hello, analysis.")

        request = fake_urlopen.call_args[0][0]
        self.assertEqual(
            fake_urlopen.call_args.kwargs["timeout"],
            7,
        )
        self.assertEqual(
            request.full_url,
            "https://provider.example/v1/chat/completions",
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer secret-key",
        )
        self.assertEqual(
            request.get_header("Content-type"),
            "application/json",
        )

        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "glm-4.5-flash")
        self.assertEqual(payload["messages"], messages)

    def test_chat_keeps_base_url_that_is_already_the_endpoint(self):
        client = self._client(
            base_url="https://provider.example/v1/chat/completions"
        )

        self.assertEqual(
            client.chat_endpoint,
            "https://provider.example/v1/chat/completions",
        )

    def test_http_error_maps_to_typed_failure_with_status(self):
        client = self._client()
        error = urllib.error.HTTPError(
            "https://provider.example/v1/chat/completions",
            429,
            "Too Many Requests",
            None,
            io.BytesIO(b"{}"),
        )

        with mock.patch(
                "reports.llm.urlopen",
                side_effect=error,
        ):
            with self.assertRaises(LLMRequestError) as raised:
                client.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(raised.exception.status_code, 429)

    def test_timeout_maps_to_typed_failure(self):
        client = self._client()

        with mock.patch(
                "reports.llm.urlopen",
                side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaises(LLMRequestError) as raised:
                client.chat([{"role": "user", "content": "hi"}])

        self.assertIn("timed out", str(raised.exception))

    def test_url_error_maps_to_typed_failure(self):
        client = self._client()

        with mock.patch(
                "reports.llm.urlopen",
                side_effect=urllib.error.URLError(
                    "connection refused"
                ),
        ):
            with self.assertRaises(LLMRequestError) as raised:
                client.chat([{"role": "user", "content": "hi"}])

        self.assertIn("Provider request failed", str(raised.exception))

    def test_unparsable_provider_body_maps_to_typed_failure(self):
        client = self._client()

        with mock.patch(
                "reports.llm.urlopen"
        ) as fake_urlopen:
            fake_urlopen.return_value = FakeResponse(
                b"<html>not json</html>"
            )

            with self.assertRaises(LLMRequestError):
                client.chat([{"role": "user", "content": "hi"}])

    def test_unexpected_provider_shape_maps_to_typed_failure(self):
        client = self._client()

        with mock.patch(
                "reports.llm.urlopen"
        ) as fake_urlopen:
            fake_urlopen.return_value = FakeResponse(
                json.dumps({"foo": "bar"}).encode("utf-8")
            )

            with self.assertRaises(LLMRequestError):
                client.chat([{"role": "user", "content": "hi"}])
