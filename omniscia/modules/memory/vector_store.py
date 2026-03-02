"""Memória vetorial (ChromaDB) — opt-in.

Objetivo:
- Dar busca semântica em histórico/códigos/outputs, além do substring search do JSONL.

Segurança/privacidade:
- Persiste localmente em `data/chroma`.
- Não envia dados para a rede (embeddings locais via sentence-transformers).

Notas:
- Esta camada não tenta ser perfeita; é um baseline simples e auditável.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorHit:
    id: str
    score: float
    text: str
    meta: dict[str, Any]


class ChromaVectorMemory:
    def __init__(
        self,
        *,
        persist_dir: str = "data/chroma",
        collection: str = "omniscia_memory",
        embed_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        self._persist_dir = str(persist_dir)
        self._collection_name = str(collection)
        self._embed_model = str(embed_model)

        try:
            import chromadb
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Dependências de memória vetorial ausentes (chromadb/sentence-transformers)") from exc

        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)

        # Chroma client persistente
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._embed_fn = SentenceTransformerEmbeddingFunction(model_name=self._embed_model)
        self._col = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, *, item_id: str, text: str, meta: dict[str, Any] | None = None) -> None:
        if not item_id or not str(item_id).strip():
            raise ValueError("item_id vazio")
        t = (text or "").strip()
        if not t:
            raise ValueError("text vazio")

        m = dict(meta or {})
        # Chroma exige valores simples em metadata (str/int/float/bool)
        safe_meta: dict[str, Any] = {}
        for k, v in m.items():
            key = str(k)
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                safe_meta[key] = v
            else:
                safe_meta[key] = json.dumps(v, ensure_ascii=False)[:2000]

        self._col.upsert(ids=[str(item_id)], documents=[t], metadatas=[safe_meta])

    def query(self, *, query: str, limit: int = 5) -> list[VectorHit]:
        q = (query or "").strip()
        if not q:
            return []
        if limit < 1:
            limit = 1
        if limit > 20:
            limit = 20

        res = self._col.query(query_texts=[q], n_results=int(limit))

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        hits: list[VectorHit] = []
        for i in range(min(len(ids), len(docs), len(metas), len(dists))):
            # Chroma retorna distância (cosine); convertemos para score ~similaridade.
            dist = float(dists[i])
            score = 1.0 - dist
            hits.append(
                VectorHit(
                    id=str(ids[i]),
                    score=score,
                    text=str(docs[i] or ""),
                    meta=dict(metas[i] or {}),
                )
            )
        return hits
