from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_pdf_word_autofill_can_run_without_pdf_title_assuming_focus():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "faça as atividades do pdf no word")
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("assume_focused_pdf") is True
    assert plan.tool_calls[0].args.get("output_mode") == "word"


def test_router_pdf_word_autofill_enables_solve_with_llm_when_asked():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "faça as atividades do pdf no word e responda as questões")
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("solve_with_llm") is True


def test_router_pdf_word_autofill_deterministic_with_pdf_name():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, 'faça todas as atividades do PDF "Aula 01 - Atividades.pdf" no Word')
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("pdf_title_contains") == "Aula 01 - Atividades.pdf"
    assert plan.tool_calls[0].args.get("output_mode") == "word"


def test_router_pdf_autofill_can_generate_docx_file():
    settings = Settings(router_mode="heuristic")
    plan = route(
        settings,
        'faça as atividades do PDF "Aula 01 - Atividades.pdf" e gere um arquivo docx "minhas-atividades.docx"',
    )
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("output_mode") == "docx"
    assert plan.tool_calls[0].args.get("out_path") == "data/tmp/minhas-atividades.docx"


def test_router_pdf_autofill_can_generate_pdf_file_default_name():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, 'faça as atividades do PDF "Aula 01 - Atividades.pdf" e gerar um arquivo pdf')
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("output_mode") == "pdf"
    assert plan.tool_calls[0].args.get("out_path") == "data/tmp/atividades.pdf"


def test_router_pdf_autofill_recognizes_gere_um_pdf_without_arquivo():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, 'faça as atividades do PDF "Aula 01 - Atividades.pdf" e gere um pdf')
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("output_mode") == "pdf"
    assert plan.tool_calls[0].args.get("out_path") == "data/tmp/atividades.pdf"


def test_router_pdf_autofill_can_target_desktop_known_folder_for_docx():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, 'faça as atividades do PDF "Aula 01 - Atividades.pdf" e gere docxs na área de trabalho')
    assert plan.intent == "edu.pdf_word_autofill"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["edu.pdf_word_autofill"]
    assert plan.tool_calls[0].args.get("output_mode") == "docx"
    assert plan.tool_calls[0].args.get("out_path") == "desktop:/atividades.docx"


def test_llm_mode_prefers_deterministic_pdf_word(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, 'faça as atividades do PDF "Aula 01 - Atividades.pdf" no Word')
    assert plan.intent == "edu.pdf_word_autofill"
