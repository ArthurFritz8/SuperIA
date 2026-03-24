"""Health checks específicos do Ollama (local).

Objetivo:
- Detectar quando o Ollama está rodando em CPU em vez de GPU (VRAM).
- Avisar UMA vez (sem spam), com instruções curtas de correção.

Detecção:
- Usamos o endpoint HTTP local do Ollama: GET /api/ps
- O campo `size_vram` (bytes) indica quanto do modelo está em VRAM.
  - > 0 => GPU/VRAM em uso
  - == 0 => CPU-only (ou GPU não utilizada)

Observação:
- Se o modelo não estiver carregado ainda, /api/ps pode não listar o modelo.
  Nesse caso, não avisamos (checamos de novo na próxima chamada).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request


_logger = logging.getLogger(__name__)

# Cache para evitar spam: marcamos OK/WARN por (base_url, model).
_OLLAMA_GPU_CHECK_DONE: set[str] = set()


def _normalize_base_url(base_url: str) -> str:
    b = (base_url or "").strip()
    while b.endswith("/"):
        b = b[:-1]
    return b


def _normalize_model_name(model: str) -> str:
    m = (model or "").strip()
    if m.lower().startswith("ollama/"):
        return m.split("/", 1)[1]
    return m


def maybe_warn_if_ollama_cpu(*, provider: str | None, base_url: str | None, model: str | None) -> None:
    """Warn once if Ollama reports the model is not using VRAM (CPU-only)."""

    p = (provider or "").strip().lower().rstrip("/")
    if p != "ollama":
        return

    if not base_url or not str(base_url).strip():
        return

    if not model or not str(model).strip():
        return

    b = _normalize_base_url(str(base_url))
    m = _normalize_model_name(str(model))
    if not b or not m:
        return

    key = f"{b}|{m}"
    if key in _OLLAMA_GPU_CHECK_DONE:
        return

    url = f"{b}/api/ps"

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=1.6) as r:  # noqa: S310
            raw = r.read().decode("utf-8")
        data = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Não fazemos barulho: é só um health-check.
        _logger.debug("Ollama health-check falhou (%s): %s", url, exc)
        return
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Ollama health-check falhou (%s): %s", url, exc)
        return

    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return

    match = None
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        model_name = str(item.get("model") or "").strip()
        if name == m or model_name == m:
            match = item
            break

    if match is None:
        # Modelo não está carregado agora; tenta de novo na próxima chamada.
        return

    try:
        size_vram = int(match.get("size_vram") or 0)
    except Exception:  # noqa: BLE001
        size_vram = 0

    if size_vram > 0:
        _OLLAMA_GPU_CHECK_DONE.add(key)
        return

    # CPU-only detectado.
    _logger.warning(
        "Ollama está rodando em CPU (size_vram=0) para '%s' em %s. "
        "Se você quer GPU no Windows/AMD, inicie o servidor com OLLAMA_VULKAN=1 e reinicie o Ollama. "
        "Confirme em %s/api/ps se size_vram > 0.",
        m,
        b,
        b,
    )
    _OLLAMA_GPU_CHECK_DONE.add(key)
