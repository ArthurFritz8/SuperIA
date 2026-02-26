from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_discord_send_message_is_critical():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, 'mandar mensagem para Alice no discord: oi')
    assert plan.intent == "discord.send_message"
    assert plan.risk == RiskLevel.CRITICAL
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "discord.send_message"]
