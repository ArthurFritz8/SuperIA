import types
import sys
import base64

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


def test_chat_reply_can_attach_image_when_vlm_enabled(monkeypatch, tmp_path):
    # Minimal 1x1 PNG (no Pillow required)
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/"
        "x1n8AAAAABJRU5ErkJggg=="
    )
    img = base64.b64decode(png_b64)
    p = tmp_path / "shot.png"
    p.write_bytes(img)

    # VLM helper only accepts relative paths (guardrail).
    monkeypatch.chdir(tmp_path)

    # Fake litellm module
    def fake_completion(*, model, messages, temperature):  # noqa: ANN001
        assert model == "groq/llama"
        assert messages[-1]["role"] == "user"
        content = messages[-1]["content"]
        assert isinstance(content, list)
        assert any(part.get("type") == "image_url" for part in content)
        return {"choices": [{"message": {"content": "resposta ok"}}]}

    fake_mod = types.SimpleNamespace(completion=fake_completion)
    monkeypatch.setitem(sys.modules, "litellm", fake_mod)

    settings = Settings(
        router_mode="llm",
        llm_provider="groq",
        llm_model="groq/llama",
        llm_api_key="x",
        vlm_enabled=True,
    )
    out = chat_reply(settings, "o que ha de errado?", image_path="shot.png")
    assert out == "resposta ok"
