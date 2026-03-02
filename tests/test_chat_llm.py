import types
import sys

import pytest

from omniscia.core.chat_llm import chat_reply
from omniscia.core.config import Settings


def test_chat_reply_uses_litellm_completion(monkeypatch):
    # Fake litellm module
    def fake_completion(*, model, messages, temperature):  # noqa: ANN001
        assert model == "groq/llama"
        assert messages[-1]["role"] == "user"
        return {"choices": [{"message": {"content": "resposta ok"}}]}

    fake_mod = types.SimpleNamespace(completion=fake_completion)
    monkeypatch.setitem(sys.modules, "litellm", fake_mod)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="groq/llama", llm_api_key="x")
    out = chat_reply(settings, "oi")
    assert out == "resposta ok"


def test_chat_reply_requires_llm_config():
    settings = Settings(router_mode="llm")
    with pytest.raises(RuntimeError):
        chat_reply(settings, "oi")
