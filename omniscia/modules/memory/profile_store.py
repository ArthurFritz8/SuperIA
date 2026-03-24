"""Perfil persistente do usuário (memória de longo prazo).

Objetivo:
- Guardar preferências estáveis (nome, idioma, tom, estilo, etc.) de forma auditável.
- Persistência local (arquivo JSON) para sobreviver entre execuções.

Notas de segurança/privacidade:
- Apenas armazenamento local em `data/user_profile.json` (por padrão).
- Não envia dados para a rede.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_PATH = Path("data/user_profile.json")


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        key = str(k)
        if isinstance(v, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(dict(out[key]), dict(v))
        else:
            out[key] = v
    return out


@dataclass
class UserProfileStore:
    path: Path = DEFAULT_PROFILE_PATH

    def load(self) -> dict[str, Any]:
        p = Path(self.path)
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, profile: dict[str, Any]) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict):
            raise ValueError("patch deve ser object/dict")
        current = self.load()
        merged = _deep_merge(current, patch)
        self.save(merged)
        return merged

    def reset(self) -> None:
        self.save({})

    def to_context_text(self, *, max_chars: int = 1200) -> str:
        prof = self.load()
        if not prof:
            return ""
        # Texto compacto e estável (bom para LLMs).
        lines: list[str] = ["PERFIL_DO_USUARIO (memória persistente):"]
        for k in sorted(prof.keys()):
            v = prof.get(k)
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                s = str(v).strip()
                if s:
                    lines.append(f"- {k}: {s}")
            elif isinstance(v, list):
                items = [str(x).strip() for x in v if str(x).strip()]
                if items:
                    lines.append(f"- {k}: {', '.join(items)[:250]}")
            elif isinstance(v, dict):
                # Render shallow keys
                sub = []
                for sk in sorted(v.keys()):
                    sv = v.get(sk)
                    if sv is None:
                        continue
                    if isinstance(sv, (str, int, float, bool)) and str(sv).strip():
                        sub.append(f"{sk}={str(sv).strip()}")
                if sub:
                    lines.append(f"- {k}: {', '.join(sub)[:300]}")
        blob = "\n".join(lines).strip()
        if len(blob) > max_chars:
            blob = blob[:max_chars] + "\n... [truncado]"
        return blob
