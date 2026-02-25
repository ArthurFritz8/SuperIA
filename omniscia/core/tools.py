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

    # Registro de ferramentas de memória (baseline JSONL).
    if memory_store is not None:
        try:
            from omniscia.modules.memory.tooling import register_memory_tools

            register_memory_tools(registry, memory_store)
        except Exception:
            logger.info("Memory tools indisponíveis (erro ao importar/registrar).")

    # Tools de filesystem (guardrailed)
    try:
        from omniscia.modules.os_control.filesystem import register_filesystem_tools

        register_filesystem_tools(registry)
    except Exception:
        logger.info("Filesystem tools indisponíveis (erro ao importar/registrar).")

    # Tools de GUI (mouse/teclado)
    try:
        from omniscia.modules.os_control.gui import register_gui_tools

        register_gui_tools(registry)
    except Exception:
        logger.info("GUI tools indisponíveis (erro ao importar/registrar).")

    # Tools de visão (screenshot)
    try:
        from omniscia.modules.vision.screenshot import register_vision_tools

        register_vision_tools(registry)
    except Exception:
        logger.info("Vision tools indisponíveis (erro ao importar/registrar).")

    # Tools de OCR
    if settings is not None:
        try:
            from omniscia.modules.vision.ocr import register_ocr_tools

            register_ocr_tools(registry, settings)
        except Exception:
            logger.info("OCR tools indisponíveis (erro ao importar/registrar).")

    # Registro opcional de ferramentas web.
    # Import lazy para evitar dependência dura de Playwright neste estágio.
    if settings is not None:
        try:
            from omniscia.modules.web.tooling import register_web_tools

            register_web_tools(registry, settings)
        except Exception:
            # Se o módulo ou dependência não existir, seguimos só com o core.
            logger.info("Web tools indisponíveis (Playwright não instalado ou erro ao importar).")

    return registry
