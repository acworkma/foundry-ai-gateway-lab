"""Offline unit tests for the shared foundation helpers.

These tests never touch Azure: env-var handling is exercised directly, and the
OpenAI client is replaced with a lightweight fake so we can assert on the exact
request payload the helpers build.
"""

import foundry_foundation as ff


def test_get_required_setting_returns_value(monkeypatch):
    monkeypatch.setenv("SAMPLE_SETTING", "value-123")
    assert ff.get_required_setting("SAMPLE_SETTING") == "value-123"


def test_get_required_setting_missing_raises(monkeypatch):
    monkeypatch.delenv("SAMPLE_SETTING", raising=False)
    import pytest

    with pytest.raises(RuntimeError):
        ff.get_required_setting("SAMPLE_SETTING")


def test_get_project_client_requires_endpoint(monkeypatch):
    monkeypatch.delenv("PROJECT_ENDPOINT", raising=False)
    import pytest

    with pytest.raises(RuntimeError):
        ff.get_project_client()


class _FakeConversations:
    def create(self):
        return type("Conversation", (), {"id": "conv_fake"})()


class _FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type("Response", (), {"output_text": "ok"})()


class _FakeOpenAIClient:
    def __init__(self):
        self.conversations = _FakeConversations()
        self.responses = _FakeResponses()


def test_invoke_agent_uses_agent_reference_payload():
    client = _FakeOpenAIClient()

    conversation, response = ff.invoke_agent(
        client, agent_name="agent-gpt", input_text="hello"
    )

    assert client.responses.kwargs["extra_body"] == {
        "agent_reference": {"name": "agent-gpt", "type": "agent_reference"}
    }
    assert client.responses.kwargs["input"] == "hello"
    assert client.responses.kwargs["conversation"] == "conv_fake"
    assert conversation.id == "conv_fake"
    assert response.output_text == "ok"


def test_invoke_agent_reuses_provided_conversation():
    client = _FakeOpenAIClient()
    existing = type("Conversation", (), {"id": "conv_existing"})()

    ff.invoke_agent(
        client, agent_name="agent-gpt", input_text="hi", conversation=existing
    )

    assert client.responses.kwargs["conversation"] == "conv_existing"
