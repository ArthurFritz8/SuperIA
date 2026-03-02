"""VLM helpers (imagem -> payload para LiteLLM).

Objetivo:
- Permitir anexar uma imagem local (screenshot) em chamadas multimodais.
- Tudo é opt-in (OMNI_VLM_ENABLED).

Nota de privacidade:
- Anexar imagem significa potencialmente enviar conteúdo de tela ao provider.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class ImageEncodeResult:
    data_url: str
    media_type: str
    bytes_len: int


def image_file_to_data_url(
    image_path: str,
    *,
    max_bytes: int = 2_000_000,
    max_side: int = 1024,
    jpeg_quality: int = 70,
) -> ImageEncodeResult:
    """Converte um arquivo de imagem em data URL (para payload multimodal).

    Estratégia:
    - Se Pillow estiver disponível: abre, redimensiona (max_side), e exporta JPEG (menor).
    - Caso contrário: lê bytes do arquivo original e usa data:image/png;base64.

    Args:
        image_path: path relativo do workspace.
        max_bytes: limite conservador para evitar estourar payload de request.
        max_side: limite máximo de largura/altura no modo Pillow.
        jpeg_quality: qualidade JPEG (1-95). 70 costuma ser bom custo/benefício.
    """

    p = Path(str(image_path).strip().replace("\\", "/"))
    if not p.as_posix() or p.as_posix().startswith("/") or ":" in p.as_posix():
        raise ValueError("image_path inválido (use path relativo)")
    if ".." in p.as_posix().split("/"):
        raise ValueError("image_path inválido (não pode conter '..')")
    if not p.exists():
        raise FileNotFoundError("imagem não existe")

    # Pillow path (preferido)
    try:
        from PIL import Image  # type: ignore

        with Image.open(p) as img:
            img = img.convert("RGB")
            w, h = img.size
            # Redimensiona mantendo aspect ratio
            if max(w, h) > int(max_side):
                scale = float(max_side) / float(max(w, h))
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = img.resize((new_w, new_h))

            q = int(jpeg_quality)
            if q < 10:
                q = 10
            if q > 95:
                q = 95

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=q, optimize=True)
            data = buf.getvalue()

        if len(data) > int(max_bytes):
            raise ValueError("imagem grande demais para anexar (tente reduzir resolucao)")

        b64 = base64.b64encode(data).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"
        return ImageEncodeResult(data_url=data_url, media_type="image/jpeg", bytes_len=len(data))
    except Exception:
        # Sem Pillow (ou falha ao abrir): fallback para bytes brutos.
        data = p.read_bytes()
        if len(data) > int(max_bytes):
            raise ValueError(
                "imagem grande demais para anexar sem Pillow (instale pillow ou reduza a imagem)"
            )
        b64 = base64.b64encode(data).decode("ascii")
        # Assume PNG no fallback (screenshot tool salva .png)
        data_url = f"data:image/png;base64,{b64}"
        return ImageEncodeResult(data_url=data_url, media_type="image/png", bytes_len=len(data))
