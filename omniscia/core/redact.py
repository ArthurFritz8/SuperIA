from __future__ import annotations

import re


_QUERY_KEY_RE = re.compile(r"([?&]key=)([^&\s]+)", re.IGNORECASE)
_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")


def redact_secrets(text: str) -> str:
    """Redact common API key patterns from logs/errors.

    Motivação:
    - Alguns erros HTTP incluem a URL completa (ex: `...key=<API_KEY>`),
      o que pode vazar segredos em logs/tracebacks.
    """

    if not text:
        return text

    redacted = _QUERY_KEY_RE.sub(r"\1REDACTED", text)
    redacted = _GOOGLE_API_KEY_RE.sub("REDACTED", redacted)
    return redacted
