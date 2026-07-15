"""LLM client abstractions for the harness runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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


@dataclass(frozen=True)
class OpenAICompatibleClient:
    """Configuration shell for an OpenAI-compatible chat-completions client."""

    base_url: str
    model: str
    api_key: str

    def complete(self, messages: list[dict[str, str]]) -> str:
        del messages
        raise NotImplementedError("Network LLM calls are not used by offline tests.")
