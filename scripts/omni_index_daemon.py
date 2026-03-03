"""Omni-Index daemon (watchdog).

Roda em background monitorando pastas do workspace e indexando mudanças no ChromaDB.

Uso (PowerShell/cmd):
- Instale extras: pip install -e .[memory,index]
- Configure: set OMNI_INDEX_PATHS=src;docs;.
- Rode: python scripts/omni_index_daemon.py

Obs:
- Isso NÃO instala como serviço do Windows automaticamente.
  Para iniciar no boot, use o Agendador de Tarefas do Windows apontando para esse script.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _parse_paths(raw: str) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for p in raw.replace("|", ";").split(";"):
        p2 = p.strip()
        if p2:
            parts.append(p2)
    return parts


def main() -> int:
    raw = (os.getenv("OMNI_INDEX_PATHS") or "").strip()
    paths = _parse_paths(raw)
    if not paths:
        print("OMNI_INDEX_PATHS não definido. Ex: OMNI_INDEX_PATHS=.;projects;docs")
        return 2

    try:
        from watchdog.events import FileSystemEventHandler  # type: ignore
        from watchdog.observers import Observer  # type: ignore
    except Exception as exc:
        print(f"watchdog não disponível: {exc}")
        return 2

    try:
        from omniscia.modules.memory.vector_store import ChromaVectorMemory
        from omniscia.modules.memory.omni_indexer import index_paths_to_vector
    except Exception as exc:
        print(f"deps de memória vetorial indisponíveis: {exc}")
        return 2

    vm = ChromaVectorMemory(persist_dir="data/chroma", collection="omniscia_memory")

    def _index_one(fp: Path) -> None:
        # Indexa o arquivo específico (se suportado) passando o próprio path.
        try:
            index_paths_to_vector(vm=vm, paths=[str(fp)], source="omni-index-daemon")
        except Exception:
            return

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):  # noqa: ANN001
            if getattr(event, "is_directory", False):
                return
            try:
                _index_one(Path(event.src_path))
            except Exception:
                return

        def on_created(self, event):  # noqa: ANN001
            if getattr(event, "is_directory", False):
                return
            try:
                _index_one(Path(event.src_path))
            except Exception:
                return

    obs = Observer()
    handler = Handler()

    for p in paths:
        wp = Path(p).resolve()
        if not wp.exists():
            continue
        if wp.is_file():
            wp = wp.parent
        try:
            obs.schedule(handler, str(wp), recursive=True)
            print(f"watching: {wp}")
        except Exception as exc:
            print(f"falha agendando watch em {wp}: {exc}")

    print("Indexação inicial...")
    try:
        seen, indexed = index_paths_to_vector(vm=vm, paths=paths, source="omni-index-daemon-initial")
        print(f"initial: seen_files={seen} indexed_items={indexed}")
    except Exception as exc:
        print(f"indexação inicial falhou: {exc}")

    obs.start()
    print("Daemon rodando. Ctrl+C para sair.")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Saindo...")
    finally:
        obs.stop()
        obs.join(timeout=3.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
