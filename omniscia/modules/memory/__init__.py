"""Módulo de Memória.

Objetivo:
- Dar ao agente memória de longo prazo (persistente), começando simples e auditável.

Estratégia incremental:
1) Persistência em JSONL (sempre disponível, sem dependências externas)
2) (Opcional) Vetorização + ChromaDB para RAG

Por quê JSONL primeiro?
- Debug fácil (um evento por linha)
- Resiliência (append-only)
- Zero setup
"""
