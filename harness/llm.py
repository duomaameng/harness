"""LLM client abstractions for the harness runner."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen as default_urlopen

from harness.storage import _redact


class LLMClient(Protocol):
    """Model boundary: callers send messages and receive raw model output."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return the model's raw structured-action text."""


class MockLLM:
    """Deterministic offline LLM for tests and demos."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.requests: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.requests.append(messages)
        if not self._outputs:
            return '{"thought_summary":"No more actions","action":"finish","args":{"summary":"done"}}'
        return self._outputs.pop(0)


class LLMClientError(RuntimeError):
    """Raised when a real model provider cannot return usable output."""


class LLMTimeoutError(LLMClientError):
    """Raised when a model request exceeds its configured timeout."""


@dataclass(frozen=True)
class OpenAICompatibleClient:
    """Configuration shell for an OpenAI-compatible chat-completions client."""

    base_url: str
    model: str
    api_key: str
    timeout: float = 60.0
    urlopen: Callable[..., Any] = default_urlopen

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            self._chat_completions_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LLMClientError(self._http_error_message(exc)) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError("Model request timed out.") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise LLMTimeoutError("Model request timed out.") from exc
            raise LLMClientError(str(_redact(f"Model request failed: {exc}"))) from exc
        except OSError as exc:
            raise LLMClientError(str(_redact(f"Model request failed: {exc}"))) from exc
        except json.JSONDecodeError as exc:
            raise LLMClientError("Model response was not valid JSON.") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Model response did not include message content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("Model response content was empty.")
        return content

    def _chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _http_error_message(self, exc: HTTPError) -> str:
        detail = ""
        try:
            raw = exc.read().decode("utf-8")
        except Exception:
            raw = ""
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                detail = raw
            else:
                error = body.get("error") if isinstance(body, dict) else None
                if isinstance(error, dict):
                    detail = str(error.get("message") or "")
        message = f"Model request failed with HTTP {exc.code} {exc.reason}"
        if detail:
            message = f"{message}: {detail}"
        return str(_redact(message))
