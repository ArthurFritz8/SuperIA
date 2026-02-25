"""Permite executar o pacote com `python -m omniscia`.

Encaminha para a CLI principal em `omniscia.app`.
"""

from __future__ import annotations

from omniscia.app import main


if __name__ == "__main__":
    main()
