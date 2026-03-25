"""Schemas Pydantic para argumentos de tools.

Incremental:
- Começa com um subconjunto crítico/mais usado.
- Novas tools podem ser adicionadas aqui sem tocar no runner.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from omniscia.core.tool_runner import ToolArgsBase


class WebResearchArgs(ToolArgsBase):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=10)
    max_pages: int = Field(default=3, ge=1, le=6)
    max_chars_per_page: int = Field(default=6000, ge=500, le=20000)
    save_to_memory: bool = True
    summarize: bool = True


class WebGetPageTextArgs(ToolArgsBase):
    url: str = Field(min_length=8)
    max_chars: int = Field(default=6000, ge=200, le=20000)


class FsListDirArgs(ToolArgsBase):
    path: str = Field(default=".")
    max_items: int | None = Field(default=None, ge=1, le=5000)


class FsReadTextArgs(ToolArgsBase):
    path: str = Field(min_length=1)
    max_chars: int = Field(default=8000, ge=100, le=200000)


class FsCopyArgs(ToolArgsBase):
    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    overwrite: bool = False


class FsMoveArgs(ToolArgsBase):
    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    overwrite: bool = False


class WriteFileArgs(ToolArgsBase):
    path: str = Field(min_length=1)
    content: str = ""


class DevExecArgs(ToolArgsBase):
    command: str = Field(min_length=1)
    timeout_s: float | None = Field(default=None, ge=0.1, le=3600)


class GameAutoplayArgs(ToolArgsBase):
    profile: str | None = None
    template: str | None = None
    duration_s: float = Field(default=30.0, ge=1.0, le=600.0)
    settle_ms: int = Field(default=450, ge=0, le=5000)


class GameCalibrateRunnerArgs(ToolArgsBase):
    name: str = Field(min_length=1)
    jump_key: str = Field(default="space")


class GameTrexAutoplayArgs(ToolArgsBase):
    duration_s: float = Field(default=30.0, ge=1.0, le=600.0)
    settle_ms: int = Field(default=450, ge=0, le=5000)
    title_contains: str | None = None


class EduPdfWordAutofillArgs(ToolArgsBase):
    pdf_title_contains: str = ""
    assume_focused_pdf: bool = False
    output_mode: Literal["word", "docx", "pdf"]
    out_path: str | None = None
    overwrite: bool = True
    solve_with_llm: bool = False
    llm_max_questions: int = Field(default=14, ge=0, le=50)
    max_scrolls: int = Field(default=22, ge=0, le=200)
    duration_s: float = Field(default=45.0, ge=1.0, le=600.0)
    settle_ms: int = Field(default=650, ge=0, le=5000)


class FinanceDexScreenerSearchArgs(ToolArgsBase):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=25)


class FinanceDexScreenerChainDiscoveryArgs(ToolArgsBase):
    chain: str = Field(min_length=2)
    limit: int = Field(default=10, ge=1, le=25)


class FinanceDefiLlamaProtocolsArgs(ToolArgsBase):
    limit: int = Field(default=20, ge=1, le=50)


class FinanceDefiLlamaProtocolArgs(ToolArgsBase):
    slug: str = Field(min_length=1)
