import re

from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_screenshot_save_to_desktop_uses_known_folder_prefix():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "tire print da tela e salva na area de trabalho")
    assert plan.intent == "vision.screenshot"
    assert plan.risk == RiskLevel.MEDIUM
    assert [c.tool_name for c in plan.tool_calls] == ["screen.screenshot"]
    path = str(plan.tool_calls[0].args.get("path", ""))
    assert re.fullmatch(r"desktop:/screen_\d{8}_\d{6}\.png", path)


def test_llm_mode_still_prefers_deterministic_screenshot(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "tire uma captura de tela e salve na área de trabalho")
    assert plan.intent == "vision.screenshot"
