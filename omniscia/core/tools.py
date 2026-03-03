"""Registro e execução de ferramentas.

Rationale:
- Ferramentas são a "ponte" entre o raciocínio e o mundo real.
- Um registro explícito facilita:
  - auditoria do que existe
  - imposição de políticas (ex: HITL)
  - testes unitários (mock de tools)

Neste MVP, tools são funções Python síncronas que retornam string.
No futuro, podemos evoluir para async + streaming.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from omniscia.core.types import ToolResult

logger = logging.getLogger(__name__)


ToolFn = Callable[[dict[str, Any]], ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: str = "LOW"  # risco intrínseco da ferramenta (ajuda a composição de risco)
    fn: ToolFn | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool já registrada: {spec.name}")
        if spec.fn is None:
            raise ValueError(f"Tool sem função: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Tool não encontrada: {name}")
        return self._tools[name]

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def run(self, name: str, args: dict[str, Any]) -> ToolResult:
        spec = self.get(name)
        try:
            assert spec.fn is not None
            return spec.fn(args)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool falhou: %s", name)
            return ToolResult(status="error", error=str(exc))


def build_default_registry(*, settings=None, memory_store=None) -> ToolRegistry:
    """Registra um conjunto mínimo de ferramentas para o MVP.

    Neste primeiro passo, criamos apenas tools "seguras" e stubs.
    """

    registry = ToolRegistry()

    def tool_echo(args: dict[str, Any]) -> ToolResult:
        text = str(args.get("text", ""))
        return ToolResult(status="ok", output=text)

    def tool_write_file(args: dict[str, Any]) -> ToolResult:
        """Escreve um arquivo no workspace.

        Importante:
        - Ainda *não* permitimos paths absolutos; reduz risco de sobrescrever o sistema.
        - Isso é um primeiro guardrail; depois criamos um sandbox com allowlist.
        """

        path = str(args.get("path", "")).strip().replace("\\", "/")
        content = str(args.get("content", ""))

        if not path or path.startswith("/") or ":" in path:
            return ToolResult(status="error", error="path inválido (use path relativo)")

        # Escrita relativa ao diretório atual (onde o processo roda).
        from pathlib import Path

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(status="ok", output=f"wrote {path}")

    def tool_show_settings(args: dict[str, Any]) -> ToolResult:
        # Preferimos mostrar as settings efetivas do processo (as já carregadas no brain).
        # Fallback: se build_default_registry foi chamado sem settings, recarrega do env.
        effective = settings
        if effective is None:
            try:
                from omniscia.core.config import Settings

                effective = Settings.load()
            except Exception as exc:  # noqa: BLE001
                return ToolResult(status="error", error=f"falha carregando settings: {exc}")

        assert effective is not None

        def _is_set(v) -> bool:
            return bool(v)

        lines = [
            "== Settings (efetivas) ==",
            f"router_mode={effective.router_mode}",
            f"hitl_enabled={effective.hitl_enabled}",
            f"hitl_min_risk={effective.hitl_min_risk}",
            f"hitl_require_token={effective.hitl_require_token}",
            f"omega_enabled={getattr(effective, 'omega_enabled', False)}",
            f"retry_max_attempts={getattr(effective, 'retry_max_attempts', 1)}",
            f"retry_backoff_s={getattr(effective, 'retry_backoff_s', 0.0)}",
            f"retry_side_effect_tools={getattr(effective, 'retry_side_effect_tools', False)}",
            "",
            "== LLM ==",
            f"llm_provider={effective.llm_provider or ''}",
            f"llm_model={effective.llm_model or ''}",
            f"llm_api_key_set={_is_set(effective.llm_api_key)}",
            "",
            "== STT/TTS ==",
            f"stt_mode={effective.stt_mode}",
            f"stt_openai_api_key_set={_is_set(effective.stt_openai_api_key)}",
            f"stt_openai_model={effective.stt_openai_model}",
            f"tts_mode={effective.tts_mode}",
            f"tts_speak_responses={getattr(effective, 'tts_speak_responses', False)}",
            f"tts_speak_alerts={getattr(effective, 'tts_speak_alerts', False)}",
            f"tts_speak_wake_ack={getattr(effective, 'tts_speak_wake_ack', False)}",
            "",
            "== Web/OCR ==",
            f"web_headless={effective.web_headless}",
            f"web_assume_https={effective.web_assume_https}",
            f"tesseract_cmd_set={_is_set(effective.tesseract_cmd)}",
            "",
            f"log_level={effective.log_level}",
        ]

        return ToolResult(status="ok", output="\n".join(lines))

    def tool_list_tools(args: dict[str, Any]) -> ToolResult:
        specs = sorted(registry.list(), key=lambda s: s.name)
        lines = ["== Tools registradas =="]
        for spec in specs:
            lines.append(f"- {spec.name} (risk={spec.risk}): {spec.description}")
        return ToolResult(status="ok", output="\n".join(lines))

    def tool_help(args: dict[str, Any]) -> ToolResult:
        lines = [
            "== Ajuda (PT-BR) ==",
            "Comandos úteis:",
            "- ajuda  (esta tela)",
            "- tools  (lista completa de tools)",
            "- settings  (ver config efetiva)",
            "- ativar voz  (fala as respostas)",
            "- silenciar  (modo silencioso)",
            "",
            "Omega/Jarvis (confiabilidade):",
            "- ativa o modo omega  (retries em tools seguras)",
            "- desativa o omega",
            "",
            "Arquivos/pastas (workspace):",
            "- listar pasta data",
            "- ler arquivo: README.md",
            "- criar pasta na área de trabalho: PastaNova",
            "",
            "Visão:",
            "- tire print da tela",
            "- tire print da tela e salva na area de trabalho",
            "",
            "PDF -> Word (automação):",
            "- faça as atividades do PDF \"Aula 01 - Atividades.pdf\" no Word  (digita no Word)",
            "- faça as atividades do PDF \"Aula 01 - Atividades.pdf\" e gere um arquivo docx",
            "- faça as atividades do PDF \"Aula 01 - Atividades.pdf\" e gere um arquivo pdf",
            "",
            "Projetos:",
            "- crie um projeto python chamado MeuApp",
        ]
        return ToolResult(status="ok", output="\n".join(lines))

    registry.register(
        ToolSpec(
            name="echo",
            description="Devolve o texto informado (diagnóstico)",
            risk="LOW",
            fn=tool_echo,
        )
    )

    registry.register(
        ToolSpec(
            name="write_file",
            description="Escreve arquivo relativo ao workspace (guardrailed)",
            risk="HIGH",
            fn=tool_write_file,
        )
    )

    registry.register(
        ToolSpec(
            name="core.show_settings",
            description="Mostra settings efetivas (segredos redigidos)",
            risk="LOW",
            fn=tool_show_settings,
        )
    )

    registry.register(
        ToolSpec(
            name="core.list_tools",
            description="Lista tools registradas (com risco e descrição)",
            risk="LOW",
            fn=tool_list_tools,
        )
    )

    registry.register(
        ToolSpec(
            name="core.help",
            description="Mostra ajuda com exemplos de comandos",
            risk="LOW",
            fn=tool_help,
        )
    )

    # Registro de ferramentas de memória (baseline JSONL).
    if memory_store is not None:
        try:
            from omniscia.modules.memory.tooling import register_memory_tools

            register_memory_tools(registry, memory_store)
        except Exception:
            logger.info("Memory tools indisponíveis (erro ao importar/registrar).")

    # Registro opcional de memória vetorial (ChromaDB) para RAG.
    if settings is not None and getattr(settings, "vector_memory_enabled", False):
        try:
            from omniscia.modules.memory.vector_tooling import register_vector_memory_tools

            register_vector_memory_tools(registry, memory_store=memory_store, settings=settings)
        except Exception:
            logger.info("Vector memory tools indisponíveis (erro ao importar/registrar).")

    # Tools de filesystem (guardrailed)
    try:
        from omniscia.modules.os_control.filesystem import register_filesystem_tools

        register_filesystem_tools(registry)
    except Exception:
        logger.info("Filesystem tools indisponíveis (erro ao importar/registrar).")

    # Tools do DevAgent (execução de código/comandos)
    try:
        from omniscia.modules.dev_agent.tooling import register_dev_tools

        register_dev_tools(registry, settings=settings)
    except Exception:
        logger.info("DevAgent tools indisponíveis (erro ao importar/registrar).")

    # Tools de GUI (mouse/teclado)
    try:
        from omniscia.modules.os_control.gui import register_gui_tools

        register_gui_tools(registry)
    except Exception:
        logger.info("GUI tools indisponíveis (erro ao importar/registrar).")

    # Tools de abrir recursos no SO (Explorer/URLs)
    try:
        from omniscia.modules.os_control.openers import register_open_tools

        register_open_tools(registry, settings=settings)
    except Exception:
        logger.info("Open tools indisponíveis (erro ao importar/registrar).")

    # Tools específicas de apps (ex: Discord via GUI)
    try:
        from omniscia.modules.apps.discord_gui import register_discord_tools

        register_discord_tools(registry)
    except Exception:
        logger.info("Discord tools indisponíveis (erro ao importar/registrar).")

    # Tools específicas de apps (ex: jGRASP via GUI)
    try:
        from omniscia.modules.apps.jgrasp_gui import register_jgrasp_tools

        register_jgrasp_tools(registry)
    except Exception:
        logger.info("jGRASP tools indisponíveis (erro ao importar/registrar).")

    # Tools Windows (janelas)
    try:
        from omniscia.modules.os_control.win_windows_tools import register_windows_window_tools

        register_windows_window_tools(registry)
    except Exception:
        logger.info("Windows window tools indisponíveis (erro ao importar/registrar).")

    # Tools UI Automation (Windows UIA) — alternativa ao PyAutoGUI (opt-in por deps)
    try:
        from omniscia.modules.os_control.ui_automation_tools import register_ui_automation_tools

        register_ui_automation_tools(registry)
    except Exception:
        logger.info("UI Automation tools indisponíveis (uiautomation não instalado ou erro ao importar).")

    # Tools de visão (screenshot)
    try:
        from omniscia.modules.vision.screenshot import register_vision_tools

        register_vision_tools(registry)
    except Exception:
        logger.info("Vision tools indisponíveis (erro ao importar/registrar).")

    # Rewind multimodal (buffer de screenshots em RAM) — opt-in
    if settings is not None:
        try:
            from omniscia.modules.vision.rewind import register_rewind_tools

            register_rewind_tools(registry, settings)
        except Exception:
            logger.info("Rewind tools indisponíveis (erro ao importar/registrar).")

    # Tools de OCR
    if settings is not None:
        try:
            from omniscia.modules.vision.ocr import register_ocr_tools

            register_ocr_tools(registry, settings)
        except Exception:
            logger.info("OCR tools indisponíveis (erro ao importar/registrar).")

    # Tools de jogos (ex.: T-Rex autoplay)
    try:
        from omniscia.modules.games.trex import register_game_tools

        register_game_tools(registry)
    except Exception:
        logger.info("Game tools indisponíveis (erro ao importar/registrar).")

    # Framework de jogos por perfis
    try:
        from omniscia.modules.games.profiles import register_game_profile_tools

        register_game_profile_tools(registry)
    except Exception:
        logger.info("Game profile tools indisponíveis (erro ao importar/registrar).")

    # Educação / automação assistida (OCR + Word)
    try:
        from omniscia.modules.education.pdf_word_autofill import register_edu_tools

        register_edu_tools(registry)
    except Exception:
        logger.info("Edu tools indisponíveis (erro ao importar/registrar).")

    # Registro opcional de ferramentas web.
    # Import lazy para evitar dependência dura de Playwright neste estágio.
    if settings is not None:
        try:
            from omniscia.modules.web.tooling import register_web_tools

            register_web_tools(registry, settings)
        except Exception:
            # Se o módulo ou dependência não existir, seguimos só com o core.
            logger.info("Web tools indisponíveis (Playwright não instalado ou erro ao importar).")

    # Loader de tools custom (opt-in)
    if settings is not None and getattr(settings, "custom_tools_enabled", False):
        try:
            from omniscia.tools.custom.loader import load_custom_tools

            load_custom_tools(registry)
        except Exception:
            logger.info("Custom tools indisponíveis (erro ao importar/registrar).")

    return registry
