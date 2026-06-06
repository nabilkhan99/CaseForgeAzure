"""Azure model-call construction, including GPT-5 / o-series temperature handling.

GPT-5 family and o-series reasoning models reject a non-default temperature, so
the marking call must omit it for those deployments and include it otherwise.
"""
from types import SimpleNamespace

from app.services.marking_service import make_azure_model_call, model_supports_temperature


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_model_supports_temperature():
    assert model_supports_temperature("gpt-4.1") is True
    assert model_supports_temperature("gpt-4.1-mini") is True
    assert model_supports_temperature("gpt-5.4-mini") is False
    assert model_supports_temperature("gpt-5") is False
    assert model_supports_temperature("o3-mini") is False


async def test_temperature_included_for_classic_model():
    client = _FakeClient()
    call = make_azure_model_call(client, "gpt-4.1", temperature=0.2)
    await call([{"role": "user", "content": "x"}])
    assert client.chat.completions.kwargs["temperature"] == 0.2
    assert client.chat.completions.kwargs["response_format"] == {"type": "json_object"}


async def test_temperature_omitted_when_none():
    client = _FakeClient()
    call = make_azure_model_call(client, "gpt-5.4-mini", temperature=None)
    await call([{"role": "user", "content": "x"}])
    assert "temperature" not in client.chat.completions.kwargs
