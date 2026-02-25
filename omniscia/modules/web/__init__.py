"""Módulo Web.

Objetivo:
- Dar ao agente capacidade de navegar/ler a web de forma autônoma.

Neste marco, implementamos ferramentas mínimas (Playwright):
- Ler texto de uma URL
- Tirar screenshot de uma URL

Rationale:
- Playwright é mais estável que Selenium para automação moderna.
- Implementamos import "lazy" para não quebrar o core se Playwright não estiver instalado.
"""
