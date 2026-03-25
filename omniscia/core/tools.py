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
from typing import Any, Callable, Awaitable

from omniscia.core.types import ToolResult
from omniscia.core.approvals import ApprovalStore
from omniscia.core.doctor import run_doctor
from omniscia.core.policy import PolicyEngine
from omniscia.core.snapshots import SnapshotManager

logger = logging.getLogger(__name__)


ToolFn = Callable[[dict[str, Any]], ToolResult]
ToolAsyncFn = Callable[[dict[str, Any]], Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: str = "LOW"  # risco intrínseco da ferramenta (ajuda a composição de risco)
    fn: ToolFn | None = None
    async_fn: ToolAsyncFn | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool já registrada: {spec.name}")
        if spec.fn is None and spec.async_fn is None:
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
            if spec.fn is None:
                raise RuntimeError(f"Tool é async-only: {name}")
            return spec.fn(args)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool falhou: %s", name)
            return ToolResult(status="error", error=str(exc))

    async def run_async(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Executa uma tool de forma async.

        - Se a tool tiver `async_fn`, usa ela.
        - Senão, executa `fn` síncrona em thread via asyncio.to_thread.
        """

        import asyncio

        spec = self.get(name)
        try:
            if spec.async_fn is not None:
                return await spec.async_fn(args)
            if spec.fn is None:
                raise RuntimeError(f"Tool sem função: {name}")
            return await asyncio.to_thread(spec.fn, args)
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
            f"hitl_remember_approvals={getattr(effective, 'hitl_remember_approvals', False)}",
            f"hitl_approvals_path={getattr(effective, 'hitl_approvals_path', 'data/hitl_approvals.json')}",
            f"policy_enabled={getattr(effective, 'policy_enabled', True)}",
            f"policy_path={getattr(effective, 'policy_path', 'data/policy.json')}",
            f"snapshots_enabled={getattr(effective, 'snapshots_enabled', True)}",
            f"snapshots_dir={getattr(effective, 'snapshots_dir', 'data/snapshots')}",
            f"snapshots_auto_before_high_risk={getattr(effective, 'snapshots_auto_before_high_risk', True)}",
            f"runlog_enabled={getattr(effective, 'runlog_enabled', True)}",
            f"runlog_dir={getattr(effective, 'runlog_dir', 'data/runs')}",
            f"replay_enabled={getattr(effective, 'replay_enabled', True)}",
            f"omega_enabled={getattr(effective, 'omega_enabled', False)}",
            f"retry_max_attempts={getattr(effective, 'retry_max_attempts', 1)}",
            f"retry_backoff_s={getattr(effective, 'retry_backoff_s', 0.0)}",
            f"retry_side_effect_tools={getattr(effective, 'retry_side_effect_tools', False)}",
            f"autonomy_enabled={getattr(effective, 'autonomy_enabled', False)}",
            f"autonomy_max_steps={getattr(effective, 'autonomy_max_steps', 12)}",
            f"autonomy_checkpoint_every={getattr(effective, 'autonomy_checkpoint_every', 4)}",
                f"async_enabled={getattr(effective, 'async_enabled', False)}",
            "",
            "== LLM ==",
            f"llm_provider={effective.llm_provider or ''}",
            f"llm_model={effective.llm_model or ''}",
            f"llm_api_key_set={_is_set(effective.llm_api_key)}",
            f"llm_base_url={getattr(effective, 'llm_base_url', '') or ''}",
            f"llm_fallback_provider={getattr(effective, 'llm_fallback_provider', '') or ''}",
            f"llm_fallback_model={getattr(effective, 'llm_fallback_model', '') or ''}",
            f"llm_fallback_api_key_set={_is_set(getattr(effective, 'llm_fallback_api_key', ''))}",
            f"llm_fallback_base_url={getattr(effective, 'llm_fallback_base_url', '') or ''}",
            f"plan_critic_enabled={getattr(effective, 'plan_critic_enabled', False)}",
            f"profile_auto_update={getattr(effective, 'profile_auto_update', False)}",
            "",
            "== Memória vetorial (RAG) ==",
            f"vector_memory_enabled={getattr(effective, 'vector_memory_enabled', False)}",
            f"vector_memory_auto_index={getattr(effective, 'vector_memory_auto_index', False)}",
            f"vector_memory_auto_remember={getattr(effective, 'vector_memory_auto_remember', False)}",
            f"vector_memory_persist_dir={getattr(effective, 'vector_memory_persist_dir', 'data/chroma')}",
            f"vector_memory_collection={getattr(effective, 'vector_memory_collection', 'omniscia_memory')}",
            f"vector_memory_embed_model={getattr(effective, 'vector_memory_embed_model', 'all-MiniLM-L6-v2')}",
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
            "- mapear programas abertos  (janelas + processos)",
            "- listar programas instalados  (registro do Windows)",
            "- ativar voz  (fala as respostas)",
            "- silenciar  (modo silencioso)",
            "",
            "Diagnóstico/instalação:",
            "- doctor  (diagnóstico do ambiente)",
            "- Se aparecer 'tool não registrada': rode `python -m omniscia doctor`",
            "- Para validar offline: `python -m omniscia selftest`",
            "- Para habilitar features opcionais: `pip install -e \".[all]\"`",
            "  (web) depois: `python -m playwright install`",
            "- Config: crie um `.env` baseado no `.env.example`",
            "- LLM local/proxy: use OMNI_LLM_BASE_URL (e OMNI_LLM_FALLBACK_* para fallback)",
            "",
            "Omega/Jarvis (confiabilidade):",
            "- ativa o modo omega  (retries em tools seguras)",
            "- desativa o omega",
            "- ativar autonomia  (executa tarefas longas com mais passos)",
            "- desativar autonomia",
            "- listar permissoes lembradas",
            "- revogar permissoes contendo vscode.",
            "- resetar permissoes lembradas",
            "- compactar memoria  (reduz data/memory/events.jsonl mantendo os mais recentes)",
            "",
            "Arquivos/pastas (workspace):",
            "- listar pasta data",
            "- ler arquivo: README.md",
            "- criar pasta na área de trabalho: PastaNova",
            "",
            "Apps (Windows):",
            "- abrir VS Code",
            "- listar extensões do VS Code",
            "- instalar extensão ms-python.python no VS Code",
            "- remover extensão ms-python.python do VS Code",
            "- ler settings do VS Code",
            "- ler tasks do VS Code",
            "- ler launch do VS Code",
            "- listar apps instalados",
            "- listar apps abertos",
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

    def tool_memory_compact(args: dict[str, Any]) -> ToolResult:
        """Compacta o JSONL de memória baseline (data/memory/events.jsonl).

        Args:
          - base_dir?: default 'data/memory'
          - keep_last?: default 5000 (linhas)
          - archive?: default true (salva linhas antigas em data/memory/archive/)
        """

        from pathlib import Path
        import time

        base_dir = str(args.get("base_dir", "data/memory") or "data/memory").strip() or "data/memory"
        keep_last = int(args.get("keep_last", 5000) or 5000)
        archive = str(args.get("archive", "true") or "true").strip().lower() != "false"

        if keep_last < 0:
            keep_last = 0
        if keep_last > 200_000:
            keep_last = 200_000

        base = Path(base_dir)
        events = base / "events.jsonl"
        if not events.exists():
            return ToolResult(status="ok", output="no events.jsonl (nada a compactar)")

        lines = events.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        if total <= keep_last:
            return ToolResult(status="ok", output=f"ok (total={total}, keep_last={keep_last}; sem mudanças)")

        cut = max(0, total - keep_last)
        old_lines = lines[:cut]
        new_lines = lines[cut:]

        ts = int(time.time())
        tmp = base / f"events.jsonl.tmp.{ts}"
        archive_dir = base / "archive"
        archive_path = archive_dir / f"events.archive.{ts}.jsonl"
        old_path = base / f"events.jsonl.old.{ts}"

        base.mkdir(parents=True, exist_ok=True)
        if archive:
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path.write_text("\n".join(old_lines) + "\n", encoding="utf-8")

        tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        # Renames em duas fases para ser mais robusto no Windows.
        events.rename(old_path)
        tmp.rename(events)

        payload = {
            "base_dir": str(base.as_posix()),
            "total_before": total,
            "kept": len(new_lines),
            "archived": len(old_lines) if archive else 0,
            "archive_path": str(archive_path.as_posix()) if archive else None,
            "old_path": str(old_path.as_posix()),
        }
        import json

        return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False, indent=2))

    def _approvals_store() -> ApprovalStore:
        effective = settings
        if effective is None:
            from omniscia.core.config import Settings as _S

            effective = _S.load()
        path = getattr(effective, "hitl_approvals_path", "data/hitl_approvals.json")
        store = ApprovalStore(path)
        store.load()
        return store

    def _policy_engine() -> PolicyEngine:
        effective = settings
        if effective is None:
            from omniscia.core.config import Settings as _S

            effective = _S.load()
        path = getattr(effective, "policy_path", "data/policy.json")
        eng = PolicyEngine(path=path)
        eng.load()
        return eng

    def _snapshot_mgr() -> SnapshotManager:
        effective = settings
        if effective is None:
            from omniscia.core.config import Settings as _S

            effective = _S.load()
        snap_dir = getattr(effective, "snapshots_dir", "data/snapshots")
        return SnapshotManager(snapshots_dir=str(snap_dir))

    def tool_doctor(args: dict[str, Any]) -> ToolResult:
        try:
            _ok, report = run_doctor(settings=settings)
            return ToolResult(status="ok", output=report)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_approvals_list(args: dict[str, Any]) -> ToolResult:
        try:
            store = _approvals_store()
            payload = {
                "path": store.path.as_posix(),
                "count": len(store.list_keys()),
                "keys": store.list_keys(),
            }
            import json

            return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_approvals_reset(args: dict[str, Any]) -> ToolResult:
        try:
            store = _approvals_store()
            store.reset()
            return ToolResult(status="ok", output="ok")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_approvals_revoke(args: dict[str, Any]) -> ToolResult:
        keys = args.get("keys")
        contains = str(args.get("contains", "") or "").strip()
        keys_list = [str(k).strip() for k in keys] if isinstance(keys, list) else []
        if not keys_list and not contains:
            return ToolResult(status="error", error="informe keys (lista) ou contains (string)")

        try:
            store = _approvals_store()
            removed = 0
            if keys_list:
                removed += store.revoke(keys_list)
            if contains:
                removed += store.revoke_where_contains(contains)
            store.save()

            import json

            return ToolResult(status="ok", output=json.dumps({"removed": removed}, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_policy_show(args: dict[str, Any]) -> ToolResult:
        try:
            eng = _policy_engine()
            payload = {
                "path": eng.path.as_posix(),
                "enabled": eng.policy.enabled,
                "default_action": eng.policy.default_action,
                "allow": list(eng.policy.allow),
                "deny": list(eng.policy.deny),
                "deny_risk_at_or_above": str(eng.policy.deny_risk_at_or_above) if eng.policy.deny_risk_at_or_above else None,
                "allowed_path_prefixes": list(eng.policy.allowed_path_prefixes),
                "load_error": eng.load_error,
            }
            import json

            return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_policy_write(args: dict[str, Any]) -> ToolResult:
        payload = args.get("policy")
        if not isinstance(payload, dict):
            return ToolResult(status="error", error="policy deve ser um dict")
        try:
            eng = _policy_engine()
            eng.save(payload)
            return ToolResult(status="ok", output=f"updated {eng.path.as_posix()}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_snapshot_create(args: dict[str, Any]) -> ToolResult:
        label = str(args.get("label", "manual") or "manual").strip() or "manual"
        try:
            mgr = _snapshot_mgr()
            info = mgr.create(label=label)
            import json

            return ToolResult(
                status="ok",
                output=json.dumps(
                    {
                        "snapshot_id": info.snapshot_id,
                        "zip_path": info.zip_path,
                        "file_count": info.file_count,
                    },
                    ensure_ascii=False,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_snapshot_list(args: dict[str, Any]) -> ToolResult:
        limit = int(args.get("limit", 20) or 20)
        try:
            mgr = _snapshot_mgr()
            snaps = mgr.list(limit=limit)
            import json

            return ToolResult(
                status="ok",
                output=json.dumps(
                    [{"snapshot_id": s.snapshot_id, "zip_path": s.zip_path} for s in snaps],
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

    def tool_snapshot_restore(args: dict[str, Any]) -> ToolResult:
        snap = str(args.get("snapshot_id", "") or "").strip()
        if not snap:
            return ToolResult(status="error", error="snapshot_id vazio")
        try:
            mgr = _snapshot_mgr()
            out = mgr.restore(snap)
            return ToolResult(status="ok", output=out)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc))

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
            name="core.doctor",
            description="Diagnóstico do ambiente (deps/config/CLI).",
            risk="LOW",
            fn=tool_doctor,
        )
    )

    registry.register(
        ToolSpec(
            name="core.approvals_list",
            description="Lista aprovações HITL lembradas (cache persistente).",
            risk="LOW",
            fn=tool_approvals_list,
        )
    )

    registry.register(
        ToolSpec(
            name="core.approvals_revoke",
            description="Revoga aprovações HITL lembradas. Args: keys? (list), contains? (string).",
            risk="HIGH",
            fn=tool_approvals_revoke,
        )
    )

    registry.register(
        ToolSpec(
            name="core.approvals_reset",
            description="Reseta todas as aprovações HITL lembradas (apaga o cache).",
            risk="HIGH",
            fn=tool_approvals_reset,
        )
    )

    registry.register(
        ToolSpec(
            name="core.policy_show",
            description="Mostra a policy efetiva carregada do arquivo local.",
            risk="LOW",
            fn=tool_policy_show,
        )
    )

    registry.register(
        ToolSpec(
            name="core.policy_write",
            description="Escreve/atualiza a policy (JSON) em disco. Args: policy (dict).",
            risk="HIGH",
            fn=tool_policy_write,
        )
    )

    registry.register(
        ToolSpec(
            name="core.snapshot_create",
            description="Cria snapshot (zip) do workspace para rollback. Args: label?",
            risk="MEDIUM",
            fn=tool_snapshot_create,
        )
    )

    registry.register(
        ToolSpec(
            name="core.snapshot_list",
            description="Lista snapshots recentes. Args: limit?",
            risk="LOW",
            fn=tool_snapshot_list,
        )
    )

    registry.register(
        ToolSpec(
            name="core.snapshot_restore",
            description="Restaura um snapshot (destrutivo). Args: snapshot_id",
            risk="CRITICAL",
            fn=tool_snapshot_restore,
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

    registry.register(
        ToolSpec(
            name="core.memory_compact",
            description="Compacta data/memory/events.jsonl mantendo os mais recentes. Args: keep_last?, archive?, base_dir?",
            risk="HIGH",
            fn=tool_memory_compact,
        )
    )

    # Perfil persistente do usuário (memória de longo prazo) — local e auditável.
    try:
        from omniscia.modules.memory.profile_tooling import register_profile_tools

        register_profile_tools(registry)
    except Exception:
        logger.info("Profile tools indisponíveis (erro ao importar/registrar).")

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

    # Inventário do sistema (processos/apps instalados) — read-only
    try:
        from omniscia.modules.os_control.inventory import register_inventory_tools

        register_inventory_tools(registry)
    except Exception:
        logger.info("Inventory tools indisponíveis (erro ao importar/registrar).")

    # Tools VS Code (via CLI `code` + arquivos .vscode)
    try:
        from omniscia.modules.vscode.tooling import register_vscode_tools

        register_vscode_tools(registry)
    except Exception:
        logger.info("VS Code tools indisponíveis (erro ao importar/registrar).")

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

    # Integrações (APIs públicas) — read-only
    try:
        from omniscia.modules.integrations.public_apis import register_public_api_tools

        register_public_api_tools(registry)
    except Exception:
        logger.info("Public API tools indisponíveis (erro ao importar/registrar).")

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
