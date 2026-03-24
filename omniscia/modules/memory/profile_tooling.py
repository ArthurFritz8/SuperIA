"""Tools para perfil persistente do usuário (memória de longo prazo)."""

from __future__ import annotations

import json
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.memory.profile_store import UserProfileStore


def register_profile_tools(registry: ToolRegistry) -> None:
    store = UserProfileStore()

    registry.register(
        ToolSpec(
            name="memory.profile_get",
            description="Lê o perfil persistente do usuário (JSON).",
            risk="LOW",
            fn=lambda args: _profile_get(args, store=store),
        )
    )

    registry.register(
        ToolSpec(
            name="memory.profile_update",
            description="Atualiza (merge) o perfil persistente do usuário. Args: patch (object).",
            risk="LOW",
            fn=lambda args: _profile_update(args, store=store),
        )
    )

    registry.register(
        ToolSpec(
            name="memory.profile_reset",
            description="Reseta o perfil persistente do usuário (apaga preferências).",
            risk="LOW",
            fn=lambda args: _profile_reset(args, store=store),
        )
    )


def _profile_get(args: dict[str, Any], *, store: UserProfileStore) -> ToolResult:
    prof = store.load()
    return ToolResult(status="ok", output=json.dumps(prof, ensure_ascii=False, indent=2))


def _profile_update(args: dict[str, Any], *, store: UserProfileStore) -> ToolResult:
    patch = args.get("patch")
    if not isinstance(patch, dict):
        return ToolResult(status="error", error="informe patch como object/dict")
    prof = store.update(patch)
    return ToolResult(status="ok", output=json.dumps(prof, ensure_ascii=False, indent=2))


def _profile_reset(args: dict[str, Any], *, store: UserProfileStore) -> ToolResult:
    store.reset()
    return ToolResult(status="ok", output="ok")
