import json
from urllib.error import HTTPError

import pytest

import harness.llm as llm_module
from harness.llm import OpenAICompatibleClient


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def close(self):
        pass


def test_openai_compatible_client_posts_chat_completion_and_returns_message_content():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "choices": [
                {"message": {"content": '{"action":"finish","args":{"summary":"done"}}'}}
            ]
        })

    client = OpenAICompatibleClient(
        base_url="https://api.example.test/v1/",
        model="example-model",
        api_key="sk-test",
        urlopen=fake_urlopen,
        timeout=12,
    )

    result = client.complete([{"role": "user", "content": "Return JSON"}])

    assert result == '{"action":"finish","args":{"summary":"done"}}'
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["Content-type"] == "application/json"
    assert captured["body"] == {
        "model": "example-model",
        "messages": [{"role": "user", "content": "Return JSON"}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def test_openai_compatible_client_raises_redacted_error_for_http_failures():
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            FakeResponse({"error": {"message": "bad key sk-secret-value"}}),
        )

    client = OpenAICompatibleClient(
        base_url="https://api.example.test/v1",
        model="example-model",
        api_key="sk-secret-value",
        urlopen=fake_urlopen,
    )

    with pytest.raises(llm_module.LLMClientError) as exc:
        client.complete([{"role": "user", "content": "Return JSON"}])

    message = str(exc.value)
    assert "401" in message
    assert "Unauthorized" in message
    assert "sk-secret-value" not in message
