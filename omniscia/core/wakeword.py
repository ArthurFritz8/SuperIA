from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t


_ALLOWED_PREFIX = {
    # saudações/vocativos comuns
    "ei",
    "eai",
    "e",
    "ai",
    "ola",
    "oi",
    "hey",
    "hi",
    "hello",
    # artigos/vocativos
    "o",
    "a",
    # polidez
    "por",
    "favor",
}


_CODE_CONTEXT_RE = re.compile(
    r"\b("
    r"c\+\+|csharp|c#|java|python|javascript|typescript|golang|rust|kotlin|"
    r"variavel|variavel|fun(c|ç)ao|funcao|metodo|classe|codigo|programacao|programa|"
    r"compilar|compilador|erro|stack"
    r")\b"
    r"|\bem\s+(c|c\+\+|java|python|js|javascript|ts|typescript)\b",
    flags=re.IGNORECASE,
)


def extract_after_wake_word(
    text: str,
    *,
    wake_word: str,
    mode: str = "prefix",
) -> tuple[bool, str]:
    """Detecta palavra de ativação e retorna o comando após ela.

        Regras (simples e robustas para STT):
        - mode="prefix": só ativa se o wake word aparecer como *token* perto do começo.
            Exemplos aceitos: "void ...", "ei void ...", "olá void ...", "o void ...".
        - mode="anywhere": ativa se o wake word aparecer como token em qualquer posição.
        - Se só disser o wake word (ex: "void"), retorna comando vazio.
    """

    original = (text or "").strip()
    if not original:
        return False, ""

    wake = _normalize(wake_word)
    if not wake:
        return False, ""

    # Tokenização simples (acentos removidos) para decidir se é vocativo.
    norm = _normalize(original)
    tokens = re.findall(r"[a-z0-9]+", norm)
    if not tokens:
        return False, ""

    try:
        idx = tokens.index(wake)
    except ValueError:
        return False, ""

    mode_norm = _normalize(mode)
    if mode_norm not in {"prefix", "anywhere", "smart"}:
        mode_norm = "prefix"

    if mode_norm == "smart":
        # Se parece conversa sobre código/linguagem, seja conservador:
        # só atende no formato vocativo do começo (como prefix).
        if _CODE_CONTEXT_RE.search(norm):
            mode_norm = "prefix"
        else:
            mode_norm = "anywhere"

    if mode_norm == "prefix":
        prefix = tokens[:idx]
        if idx > 0 and not all(t in _ALLOWED_PREFIX for t in prefix):
            # Wake word apareceu no meio de uma frase que não é vocativo.
            return False, ""

    # Extrai o texto após o *primeiro* wake word no original.
    # (o wake word em si é ASCII, então o regex no original é seguro.)
    m = re.search(rf"\b{re.escape(wake_word)}\b", original, flags=re.IGNORECASE)
    if not m:
        return False, ""

    after = original[m.end() :].strip()
    after = after.lstrip(" \t\r\n,.:;!?-–—")
    return True, after
