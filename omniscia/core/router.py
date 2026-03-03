"""Router (interpretação de comandos -> plano).

Rationale:
- Um agente sério separa *entendimento* (router) de *execução* (tools).
- Assim podemos trocar a fonte de inteligência: heurística, LLM, regras, etc.

Este MVP tem dois modos:
- heuristic: regras simples e previsíveis
- llm: usa LiteLLM (multi-provider). Se faltar config, cai para heuristic.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.types import Plan, RiskLevel, ToolCall

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normaliza texto para matching heurístico.

    Motivação:
    - Acentos e encoding variam entre terminais (Windows, bash, PowerShell).
    - Para heurísticas simples, a normalização reduz falsos negativos.

    Estratégia:
    - lowercase
    - remove acentos via NFKD
    """

    t = (text or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t


def route(settings: Settings, user_message: str) -> Plan:
    # Exit must be handled deterministically before any LLM routing.
    # Otherwise the LLM may hallucinate a destructive action (e.g., shutdown).
    if _normalize(user_message) in {"sair", "exit", "quit"}:
        msg = user_message.strip()
        return Plan(intent="exit", user_message=msg, final_response="Encerrando.")

    # Prefer deterministic heuristics whenever they match.
    # This improves UX (no latency/quota) and avoids LLM hallucinations.
    heuristic = _route_heuristic(user_message)
    deterministic_intents = {
        # OS openers
        "os.open_url",
        "os.open_explorer",
        "os.open_app",
        "os.close_app",
        "os.scan_apps",
        "os.generate_open_apps",
        "os.mkdir",
        # Filesystem routines
        "fs.list_dir",
        "fs.read_text",
        "fs.delete",
        "fs.mkdir",
        "fs.copy",
        "fs.move",
        # Vision basics
        "screen.screenshot",
        "screen.ocr",
        # Router intents for vision
        "vision.screenshot",
        "vision.ocr",
        # GUI explicit coordinates
        "gui.get_mouse",
        "gui.move_mouse",
        "gui.click",
        "gui.click_box_center",
        "gui.type_text",
        "gui.press_key",
        # Games
        "game.trex_autoplay",
        "game.autoplay",
        "game.list_profiles",
        "game.save_profile",
        "game.calibrate_runner_from_mouse",
        # Education
        "edu.pdf_word_autofill",
        # Web read-only
        "web.get_page_text",
        "win.focus_window",
        "discord.send_message",
        "jgrasp.create_java_program",
        "jgrasp.write_code",
        # DevAgent (explicit)
        "dev.exec",
        "dev.run_python",
        "dev.autofix_python_file",
        "dev.autofix_cmd",
        "dev.scaffold_project",
        # Session toggles
        "core.omega_on",
        "core.omega_off",
        "core.voice_on",
        "core.voice_off",
        "core.help",
    }
    if heuristic.intent in deterministic_intents:
        return heuristic

    if settings.router_mode == "llm":
        plan = route_llm(settings, user_message, heuristic_fallback=heuristic)
        if plan is not None:
            return plan

    return heuristic


def route_llm(
    settings: Settings,
    user_message: str,
    *,
    context_messages: list[dict[str, str]] | None = None,
    heuristic_fallback: Plan | None = None,
) -> Plan | None:
    """Roteia via LLM (quando configurado), opcionalmente com contexto adicional.

    Uso:
    - `route()` chama isso para o primeiro plano em modo llm.
    - O loop ReAct pode chamar isso novamente após tool outputs, passando `context_messages`.

    Observação:
    - `context_messages` deve conter apenas roles "user"/"assistant".
    - Guardrails de segurança são aplicados aqui.
    """

    plan = _route_with_llm_messages(
        settings,
        (context_messages or []) + [{"role": "user", "content": str(user_message or "").strip()}],
    )
    if plan is None:
        return None

    norm = _normalize(user_message)

    def _asked_for_screen_or_gui(n: str) -> bool:
        # IMPORTANTE: não basta mencionar "tela".
        # Ex.: "na minha tela apareceu..." NÃO é pedido pra usar OCR/screenshot.
        # Só libera tools quando houver pedido explícito (imperativo) ou ação (clicar/digitar).

        # Pedidos explícitos de clique/teclado.
        if re.search(
            r"\b(clica|clicar|clique|mouse|teclado|digita|digitar|digite|aperta|apertar|pressione|pressionar|pule|pular|jogue|jogar)\b",
            n,
        ):
            return True

        # Pedidos explícitos de screenshot/OCR.
        if re.search(
            r"\b(screenshot|print\s*screen|printscreen|captura\s+de\s+tela|ocr|ler\s+texto|leia\s+o\s+texto)\b",
            n,
        ):
            return True

        # Imperativo + tela/screen.
        has_imperative = bool(
            re.search(r"\b(olha|olhe|veja|ver|verifique|analise|analisa|mostra|mostre|leia)\b", n)
        )
        has_screen_word = bool(re.search(r"\b(tela|screen)\b", n))
        return has_imperative and has_screen_word

    def _asked_for_dev_exec(n: str) -> bool:
        return bool(re.search(r"\b(rode|rodar|executa|execute|comando|terminal|cmd|powershell|python)\b", n))

    asked_screen_or_gui = _asked_for_screen_or_gui(norm)
    asked_dev = _asked_for_dev_exec(norm)

    def _has_forbidden_tools(p: Plan) -> bool:
        for c in p.tool_calls:
            name = (c.tool_name or "").strip()
            if name.startswith(("screen.", "gui.")) or name in {"win.focus_window"}:
                if not asked_screen_or_gui:
                    return True
            if name.startswith("dev.") and not asked_dev:
                return True
        return False

    if _has_forbidden_tools(plan):
        # Tenta uma segunda vez instruindo explicitamente a responder só em texto.
        no_tools_msg = (
            user_message
            + "\n\nIMPORTANTE: o usuário NÃO pediu para ver/clicar na tela nem executar comandos. "
            + "Responda APENAS com orientação em texto, tool_calls=[] e risk=LOW."
        )
        plan2 = _route_with_llm_messages(
            settings,
            (context_messages or []) + [{"role": "user", "content": no_tools_msg}],
        )
        if plan2 is not None and not _has_forbidden_tools(plan2) and (plan2.final_response or "").strip():
            plan = plan2
        else:
            # Fallback final: zera tools e devolve resposta textual (se existir).
            plan = plan.model_copy(
                update={
                    "intent": "chat",
                    "risk": RiskLevel.LOW,
                    "tool_calls": [],
                    "final_response": (plan.final_response or "").strip()
                    or "Posso te orientar em texto. Me diga o que você quer fazer e com quais detalhes.",
                }
            )

    # Safety guard: don't let the LLM trigger Discord actions unless the user asked.
    if any((c.tool_name or "").startswith("discord.") for c in plan.tool_calls):
        asked_discord = "discord" in norm
        asked_message = bool(re.search(r"\b(mensagem|msg|chat)\b", norm))
        if not (asked_discord and asked_message):
            logger.warning("LLM plan attempted Discord tools without explicit user request; falling back")
            if heuristic_fallback is not None:
                return heuristic_fallback
            return Plan(intent="chat", user_message=user_message.strip(), tool_calls=[], risk=RiskLevel.LOW, final_response="Posso ajudar em texto. Se você quiser mesmo enviar mensagem no Discord, diga explicitamente o destinatário e a mensagem.")

    return plan


def _route_heuristic(user_message: str) -> Plan:
    msg = user_message.strip()
    norm = _normalize(msg)

    # Entradas só-numéricas (usuário tentando "escolher um passo" ou responder menu).
    # O MVP não tem UX de menu por números, então damos um caminho claro.
    if re.fullmatch(r"\d{1,3}", norm or ""):
        return Plan(
            intent="chat",
            user_message=msg,
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response=(
                "Eu não uso números como seleção de menu. "
                "Se você quer que eu execute a automação, repita o pedido completo (ex.: 'faça as atividades do PDF no Word'), "
                "ou diga explicitamente: 'pode executar agora' depois de colocar o PDF em foco."
            ),
        )

    def _guess_name_from_text(text: str) -> str | None:
        # quoted "Meu Projeto"
        q = re.search(r"['\"]([^'\"]{2,60})['\"]", text)
        if q:
            return q.group(1).strip()
        m = re.search(r"\b(chamado|chamada|nome)\b\s+([\w\- ]{2,60})", text, flags=re.IGNORECASE)
        if m:
            return (m.group(2) or "").strip()
        return None

    # Regra: toggles de sessão (modo omega)
    if re.search(r"\b(omega|jarvis)\b", norm) and re.search(
        r"\b(ativar|ativa|liga|ligar|on|habilitar)\b",
        norm,
    ):
        return Plan(
            intent="core.omega_on",
            user_message=msg,
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response="Ok — modo omega ativado nesta sessão.",
        )

    if re.search(r"\b(omega|jarvis)\b", norm) and re.search(
        r"\b(desativar|desativa|desliga|desligar|off)\b",
        norm,
    ):
        return Plan(
            intent="core.omega_off",
            user_message=msg,
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response="Ok — modo omega desativado nesta sessão.",
        )

    # Regra: comandos de voz (TTS) em runtime
    # Importante: isso NÃO liga STT; apenas habilita/desabilita falar respostas.
    if re.search(r"\b(silenciar|mute|sem\s+voz|tirar\s+voz|desativar\s+voz|desliga\s+a\s+voz)\b", norm):
        return Plan(
            intent="core.voice_off",
            user_message=msg,
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response="Ok — voz desativada (modo silencioso).",
        )

    if re.search(r"\b(ativar\s+voz|liga\s+a\s+voz|ligar\s+voz|falar\s+resposta|fala\s+as\s+respostas)\b", norm):
        return Plan(
            intent="core.voice_on",
            user_message=msg,
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response="Ok — voz ativada para respostas (se disponível).",
        )

    def _guess_output_filename_for_ext(text: str, ext: str) -> str | None:
        # Prefer the *last* match for the requested extension.
        # Rationale: the message may contain the source PDF title and the desired output filename.
        ext = (ext or "").strip().lower().lstrip(".")
        if ext not in {"docx", "pdf"}:
            return None

        quoted = re.findall(rf"['\"]([^'\"]{{3,140}}\.{ext})['\"]", text, flags=re.IGNORECASE)
        if quoted:
            return (quoted[-1] or "").strip()

        bare = re.findall(rf"\b([^\s]{{3,140}}\.{ext})\b", text, flags=re.IGNORECASE)
        if bare:
            return (bare[-1] or "").strip()

        return None

    def _guess_pdf_title(text: str) -> str:
        pdf_title = ""
        q = re.search(r"['\"]([^'\"]{3,120}\.pdf)['\"]", text, flags=re.IGNORECASE)
        if q:
            pdf_title = (q.group(1) or "").strip()
        else:
            m = re.search(r"\b([^\s]{3,120}\.pdf)\b", text, flags=re.IGNORECASE)
            if m:
                pdf_title = (m.group(1) or "").strip()
        return pdf_title

    def _guess_word_title(text: str) -> str:
        word_title = "Word"
        wq = re.search(r"word\s*[:=]\s*['\"]([^'\"]{2,80})['\"]", text, flags=re.IGNORECASE)
        if wq:
            word_title = (wq.group(1) or "Word").strip() or "Word"
        return word_title

    # Regra: PDF (Google/Chrome) -> Word (digitar) ou gerar arquivo (.docx/.pdf)
    # Pedido explícito do usuário: ler/rolar o PDF e preencher/organizar as atividades.
    if re.search(r"\b(pdf)\b", norm) and re.search(
        r"\b(atividade|atividades|quest(ao|oes)|fazer|fa(c|ç)a|resolver|resolva|escrever|escreva)\b",
        norm,
    ):
        pdf_title = _guess_pdf_title(msg)
        assume_focused_pdf = False
        if not pdf_title:
            # UX melhor: se o usuário não souber o nome do arquivo, dá pra rodar assumindo
            # que ele colocou a janela do PDF em foco (ele vai aprovar via HITL antes).
            assume_focused_pdf = True

        wants_word = bool(re.search(r"\b(word)\b", norm))

        # Arquivo Word (.docx) pode aparecer como "docx", "docxs", ".docx" ou "arquivo do word".
        wants_docx = bool(
            re.search(r"\b(docx|docxs|\.docx)\b", norm)
            or (
                re.search(r"\b(gerar|criar|exportar|salvar|gera|gere|crie)\b", norm)
                and re.search(r"\b(arquivo|documento)\b", norm)
                and re.search(r"\b(word)\b", norm)
            )
        )

        # Arquivo PDF de saída: aceitar "gere um pdf" mesmo sem a palavra "arquivo".
        wants_pdf_file = bool(
            re.search(r"\b(gerar|criar|exportar|salvar|gera|gere|crie)\b", norm)
            and (
                re.search(r"\b(um\s+pdf|em\s+pdf|pdf)\b", norm)
                or ".pdf" in norm
            )
        )

        wants_desktop = bool(re.search(r"\b(área\s+de\s+trabalho|area\s+de\s+trabalho|desktop)\b", norm))

        # Opt-in para respostas completas via LLM quando o usuário pedir explicitamente "responda/solucione".
        wants_answers = bool(
            re.search(r"\b(responda|responder|respostas|solucione|solucionar|complete|completo|passo\s*a\s*passo)\b", norm)
        )

        # Se o usuário mencionou Word e não pediu explicitamente arquivo, digitamos no Word.
        if wants_word and not wants_docx and not wants_pdf_file:
            word_title = _guess_word_title(msg)
            return Plan(
                intent="edu.pdf_word_autofill",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="edu.pdf_word_autofill",
                        args={
                            "pdf_title_contains": pdf_title,
                            "assume_focused_pdf": assume_focused_pdf,
                            "word_title_contains": word_title,
                            "output_mode": "word",
                            "solve_with_llm": wants_answers,
                            "llm_max_questions": 14,
                            "max_scrolls": 22,
                            "duration_s": 45.0,
                            "settle_ms": 650,
                        },
                    )
                ],
                risk=RiskLevel.HIGH,
                final_response=(
                    "Ok — vou ler o PDF (OCR + rolagem) e preencher organizado no Word (requer aprovação). "
                    + (
                        "Antes de aprovar: clique na janela do PDF para ela ficar em foco. "
                        if assume_focused_pdf
                        else ""
                    )
                    + "Dica: deixe o PDF visível em 100%-125% e o Word aberto."
                ),
            )

        # Caso contrário, só gera arquivo quando o usuário pediu explicitamente docx/pdf.
        if wants_docx or wants_pdf_file:
            output_mode = "docx" if wants_docx else "pdf"
            out_name = _guess_output_filename_for_ext(msg, output_mode)
            # Evita capturar o PDF de entrada como nome do arquivo de saída.
            if out_name and out_name.strip().lower() == pdf_title.strip().lower():
                out_name = None

            if not out_name:
                if wants_desktop:
                    out_name = "desktop:/atividades.docx" if output_mode == "docx" else "desktop:/atividades.pdf"
                else:
                    out_name = "data/tmp/atividades.docx" if output_mode == "docx" else "data/tmp/atividades.pdf"
            elif "/" not in out_name and "\\" not in out_name:
                # Se o usuário só deu o nome do arquivo, coloca em data/tmp (ou Desktop se pedido).
                out_name = f"desktop:/{out_name}" if wants_desktop else f"data/tmp/{out_name}"
            else:
                # Se ele forneceu um path, respeitamos; mas se pediu Desktop e não usou prefixo,
                # damos preferência ao prefixo (mais portátil/seguro) quando possível.
                if wants_desktop and not out_name.lower().startswith(("desktop:/", "downloads:/", "documents:/")):
                    leaf = out_name.replace("\\", "/").split("/")[-1]
                    if leaf and "." in leaf:
                        out_name = f"desktop:/{leaf}"

            return Plan(
                intent="edu.pdf_word_autofill",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="edu.pdf_word_autofill",
                        args={
                            "pdf_title_contains": pdf_title,
                            "assume_focused_pdf": assume_focused_pdf,
                            "output_mode": output_mode,
                            "out_path": out_name,
                            "overwrite": True,
                            "solve_with_llm": wants_answers,
                            "llm_max_questions": 14,
                            "max_scrolls": 22,
                            "duration_s": 45.0,
                            "settle_ms": 650,
                        },
                    )
                ],
                risk=RiskLevel.HIGH,
                final_response=(
                    f"Ok — vou ler o PDF (OCR + rolagem) e gerar um arquivo {output_mode.upper()} (requer aprovação). "
                    + ("Antes de aprovar: clique na janela do PDF para ela ficar em foco. " if assume_focused_pdf else "")
                    + "Dica: deixe o PDF visível em 100%-125%."
                ),
            )

    # Regra: jogar o T-Rex (Chrome Dino) explicitamente
    # Mantemos determinístico para funcionar mesmo sem LLM (quota/rate limit).
    if re.search(r"\b(jogue|jogar|joga|joguei)\b", norm) and re.search(
        r"\b(t\s*-?\s*rex|trex|dino|dinossauro|chrome\s*dino|jogo\s*do\s*dinossauro)\b",
        norm,
    ):
        title_contains = None
        # Se o usuário fornecer um título de janela entre aspas, usamos como hint.
        q = re.search(r"['\"]([^'\"]{2,80})['\"]", msg)
        if q:
            title_contains = (q.group(1) or "").strip()

        args: dict[str, Any] = {"duration_s": 30.0, "settle_ms": 450}
        if title_contains:
            args["title_contains"] = title_contains

        return Plan(
            intent="game.trex_autoplay",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="game.trex_autoplay", args=args)],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou tentar jogar o T‑Rex automaticamente por ~30s (requer aprovação).",
        )

    # Regra: automação genérica de jogo (perfil/template)
    # Observação: não tentamos automação em contexto explicitamente online/competitivo.
    if re.search(r"\b(jogue|jogar|joga)\b", norm) and re.search(r"\b(jogo|game)\b", norm):
        if re.search(r"\b(online|competitivo|ranked|ranqueado|anti\s*-?cheat|multiplayer|pvp)\b", norm):
            return Plan(
                intent="chat",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response=(
                    "Posso orientar em texto, mas não vou automatizar jogos online/competitivos. "
                    "Se for um jogo offline/solo ou um jogo de navegador simples, diga isso explicitamente."
                ),
            )

        # Tenta inferir um nome de perfil simples.
        q = re.search(r"['\"]([^'\"]{2,60})['\"]", msg)
        profile = (q.group(1).strip().lower() if q else "")

        # Se o usuário não forneceu um profile, fazemos calibração runner rápida via mouse.
        if not profile and re.search(r"\b(qualquer|qualquer\s+jogo)\b", norm):
            tmp_profile = "runner"
            return Plan(
                intent="game.autoplay",
                user_message=msg,
                tool_calls=[
                    ToolCall(tool_name="game.calibrate_runner_from_mouse", args={"name": tmp_profile, "jump_key": "space"}),
                    ToolCall(tool_name="game.autoplay", args={"profile": tmp_profile, "duration_s": 30.0, "settle_ms": 450}),
                ],
                risk=RiskLevel.HIGH,
                final_response=(
                    "Ok — antes de aprovar, coloque o mouse em cima do personagem do jogo. "
                    "Vou calibrar (runner) e jogar por ~30s (requer aprovação)."
                ),
            )

        args: dict[str, Any] = {"duration_s": 30.0, "settle_ms": 450}
        if profile:
            args["profile"] = profile
        else:
            args["template"] = "runner"

        return Plan(
            intent="game.autoplay",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="game.autoplay", args=args)],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou tentar jogar automaticamente por ~30s (requer aprovação).",
        )

    def _strip_quotes(s: str) -> str:
        return (s or "").strip().strip('"').strip("'").strip()

    def _guess_folder_name(text: str) -> str | None:
        q = re.search(r"['\"]([^'\"]+)['\"]", text)
        if q:
            return q.group(1).strip()

        m2 = re.search(
            r"\b(pasta|diretorio|diret[oó]rio|folder|dir)\b\s+(?:chamada|chamado|nome)?\s*[: ]\s*(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not m2:
            return None

        tail = (m2.group(2) or "").strip()
        # Remove sufixos de localização (ex: 'na área de trabalho', 'no disco D')
        tail = re.split(
            r"\b(no|na|em)\b\s+(?:[aá]rea de trabalho|desktop|disco|ssd|drive)\b",
            tail,
            flags=re.IGNORECASE,
        )[0].strip()
        return tail.strip().strip('"').strip("'")

    # NOTA: geração de código (ex.: exemplos completos de Java) é responsabilidade do modo LLM.
    # No modo heurístico, preferimos não chutar código nem “enfiar” templates fixos.

    # Regra: screenshot
    is_screenshot = bool(
        re.search(r"\b(screenshot|printscreen|print screen|captura de tela|tire uma captura)\b", norm)
        or (re.search(r"\bprint\b", norm) and re.search(r"\b(tela|screen)\b", norm))
    )
    if is_screenshot:
        wants_desktop = bool(re.search(r"\b(área de trabalho|area de trabalho|desktop)\b", norm))
        wants_save = bool(re.search(r"\b(salvar|salva|salve|guardar)\b", norm))

        args: dict[str, Any] = {}
        if wants_desktop and wants_save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            args["path"] = f"desktop:/screen_{ts}.png"
        return Plan(
            intent="vision.screenshot",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="screen.screenshot", args=args)],
            risk=RiskLevel.MEDIUM,
            final_response=(
                "Tirei uma captura de tela e salvei na Área de Trabalho." if (wants_desktop and wants_save) else "Tirei uma captura de tela."
            ),
        )

    # Regra: abrir Explorador / gerenciador de arquivos
    if re.search(r"\b(explorador|explorer|gerenciador de arquivos|arquivos)\b", norm) and re.search(
        r"\b(abrir|abra|abre|open)\b", norm
    ):
        return Plan(
            intent="os.open_explorer",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_explorer", args={"path": "."})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri o Explorador de Arquivos.",
        )

    # Regra: abrir alvos potencialmente perigosos (sempre pede HITL)
    if re.search(r"\b(abrir|abra|abre|open)\b", norm):
        dangerous_map = {
            "cmd": r"\b(cmd|prompt de comando|command prompt)\b",
            "powershell": r"\b(power\s*shell|powershell)\b",
            "pwsh": r"\b(pwsh)\b",
            "terminal": r"\b(windows terminal|terminal)\b",
            "regedit": r"\b(regedit|editor do registro|registro)\b",
        }
        for app_key, pat in dangerous_map.items():
            if re.search(pat, norm):
                return Plan(
                    intent="os.open_app",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="os.open_app", args={"app": app_key})],
                    risk=RiskLevel.CRITICAL,
                    final_response="Ok — vou abrir isso (requer aprovação).",
                )

    # Regra: gerar allowlist de apps automaticamente
    if re.search(r"\b(gerar|criar|montar)\b.*\b(allowlist|lista)\b.*\b(app|apps|programa|programas)\b", norm):
        return Plan(
            intent="os.generate_open_apps",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.generate_open_apps", args={"out_path": "data/open_apps.generated.json", "overwrite": True})],
            risk=RiskLevel.HIGH,
            final_response="Ok. Vou gerar um arquivo JSON com apps detectados para sua allowlist.",
        )

    # Regra: listar apps instalados/atalhos
    if re.search(r"\b(listar|lista|mostrar|ver)\b.*\b(apps|programas)\b", norm) and re.search(
        r"\b(instalados|atalhos|menu iniciar|menu|start)\b", norm
    ):
        return Plan(
            intent="os.scan_apps",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.scan_apps", args={"max_results": 400})],
            risk=RiskLevel.LOW,
            final_response="Ok, vou listar atalhos de apps detectados.",
        )

    # Regra: abrir YouTube no navegador padrão
    if "youtube" in norm and re.search(r"\b(abrir|abra|abre|open)\b", norm):
        return Plan(
            intent="os.open_url",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_url", args={"url": "https://www.youtube.com/"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri o YouTube no seu navegador.",
        )

    # Regra: abrir calculadora do Windows
    if re.search(r"\b(calculadora|calculator|calc)\b", norm) and re.search(
        r"\b(abrir|abra|abre|open)\b", norm
    ):
        return Plan(
            intent="os.open_app",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "calculator"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri a Calculadora do Windows.",
        )

    # Regra: abrir Discord
    if "discord" in norm and re.search(r"\b(abrir|abra|abre|open)\b", norm):
        return Plan(
            intent="os.open_app",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "discord"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri o Discord.",
        )

    # Regra: fechar Discord (gracioso, sem taskkill)
    if "discord" in norm and re.search(r"\b(fechar|feche|fecha|close|encerrar)\b", norm):
        in_background = bool(re.search(r"\b(segundo plano|background|bandeja|tray|minimizad[oa])\b", norm))
        return Plan(
            intent="os.close_app",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="os.close_app",
                    args={"app": "discord", "visible_only": (not in_background)},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou fechar o Discord (requer aprovação).",
        )

    # Regra: pedidos de geração de código (matriz/matemática/etc.)
    # - Em modo heurístico: não chutamos templates fixos.
    # - Em modo llm: a heurística retorna chat (não determinístico) e o `route()` chama o LLM.
    if re.search(r"\b(criar|crie|cria|fazer|faca|faça|gerar|gere|escrever|escreva|montar)\b", norm):
        wants_code = bool(re.search(r"\b(c[oó]digo|codigo)\b", norm))
        wants_jgrasp = ("jgrasp" in norm)
        wants_matrix_math = bool(re.search(r"\b(matriz|matrix|matem[aá]tica|matematica|math)\b", norm))
        wants_conta_math = bool(re.search(r"\bconta\b", norm)) and not bool(
            re.search(r"\b(login|senha|email|e-mail|conta\s+banc[aá]ria|banco|cadastro|registrar)\b", norm)
        )

        if wants_code and (wants_matrix_math or (wants_jgrasp and wants_conta_math) or (wants_matrix_math and not wants_jgrasp)):
            return Plan(
                intent="chat",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response=(
                    "Consigo gerar esse código, mas no modo heurístico eu não uso templates fixos. "
                    "Ative o modo LLM (OMNI_ROUTER_MODE=llm) e repita o pedido, ou descreva exatamente o que o programa deve fazer "
                    "(entradas, saídas e restrições) que eu te guio passo a passo."
                ),
            )

    # Regra: criar um programa/projeto simples no jGRASP (fallback determinístico)
    if "jgrasp" in norm and re.search(r"\b(criar|crie|cria|fazer|faca|faça|gerar|gere|montar)\b", norm):
        if re.search(r"\b(programa|projeto)\b", norm) and re.search(r"\b(simples|hello\s*world|ol[aá]\s*,?\s*mundo)\b", norm):
            # Se o usuário pedir explicitamente para salvar na Área de Trabalho, use o prefixo desktop:/
            # (a tool do jGRASP aplica guardrails e resolve com Known Folders).
            wants_desktop = bool(
                re.search(r"\b(área de trabalho|area de trabalho|desktop)\b", norm)
            )

            path = "scratch/HelloWorld.java"
            class_name = "HelloWorld"
            if wants_desktop:
                path = "desktop:/MeuProjeto/MeuProjeto.java"
                class_name = "MeuProjeto"

            return Plan(
                intent="jgrasp.create_java_program",
                user_message=msg,
                tool_calls=[
                    ToolCall(tool_name="os.open_app", args={"app": "jgrasp"}),
                    ToolCall(
                        tool_name="jgrasp.create_java_program",
                        args={
                            "path": path,
                            "class_name": class_name,
                            "message": "Olá, mundo!",
                            "open_in_jgrasp": True,
                            "settle_ms": 900,
                        },
                    ),
                ],
                risk=RiskLevel.HIGH,
                final_response="Ok — vou criar um programa Java simples no jGRASP (requer aprovação).",
            )

    # Regra: enviar mensagem no Discord
    # Exemplos:
    # - "mandar mensagem para Alice no discord: oi"
    # - "enviar msg discord para \"Alice\": tudo bem?"
    m = re.search(
        r"\b(mandar|enviar)\b.*\b(mensagem|msg)\b.*\b(para|pra)\b\s*(?P<to>[^:]+?)\s*(?:\bno\b\s*discord|\bdiscord\b)?\s*[:\-]\s*(?P<text>.+)$",
        msg,
        flags=re.IGNORECASE,
    )
    if m:
        to = _strip_quotes(m.group("to") or "")
        text = (m.group("text") or "").strip()
        if to and text:
            return Plan(
                intent="discord.send_message",
                user_message=msg,
                tool_calls=[
                    ToolCall(tool_name="os.open_app", args={"app": "discord"}),
                    ToolCall(tool_name="discord.send_message", args={"to": to, "message": text, "settle_ms": 900}),
                ],
                risk=RiskLevel.CRITICAL,
                final_response="Ok — vou enviar a mensagem no Discord (requer aprovação).",
            )

    # Regra: "clique no chat da Alice e mande um oi" (sem mencionar Discord explicitamente)
    # Preferimos o fluxo via atalhos (discord.send_message) em vez de coordenadas/GUI.
    m = re.search(
        r"\bclique\b.*\bchat\b.*\bda\b\s*(?P<to>[^,.;:]+?)\s+e\s+\bmande\b\s+(?P<text>.+)$",
        msg,
        flags=re.IGNORECASE,
    )
    if m:
        to = _strip_quotes(m.group("to") or "")
        text = (m.group("text") or "").strip()
        # Remove sufixos comuns: "para ela/ele".
        text = re.sub(r"\b(pra|para)\s+(ela|ele|ele(a)?)\b\s*$", "", text, flags=re.IGNORECASE).strip()
        # Frases como "um oi" => "oi".
        text_norm = _normalize(text)
        if re.fullmatch(r"(um\s+)?oi", text_norm):
            text = "oi"

        if to and text:
            return Plan(
                intent="discord.send_message",
                user_message=msg,
                tool_calls=[
                    ToolCall(tool_name="os.open_app", args={"app": "discord"}),
                    ToolCall(tool_name="discord.send_message", args={"to": to, "message": text, "settle_ms": 900}),
                ],
                risk=RiskLevel.CRITICAL,
                final_response="Ok — vou abrir o chat e enviar a mensagem no Discord (requer aprovação).",
            )

    # Regra: OCR
    if re.search(r"\b(ocr|ler tela|leia a tela|o que esta escrito|o que esta na tela)\b", norm):
        return Plan(
            intent="vision.ocr",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="screen.ocr", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Fiz OCR da tela atual.",
        )

    # Regra: criar pasta (mkdir)
    m = re.search(
        r"\b(criar|crie|cria|make|mkdir)\b.*\b(pasta|diretorio|diret[oó]rio|folder|dir)\b",
        msg,
        flags=re.IGNORECASE,
    )
    if m:
        name = _guess_folder_name(msg)
        if not name:
            return Plan(
                intent="chat",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="echo", args={"text": msg})],
                risk=RiskLevel.LOW,
                final_response="Qual nome da pasta? (ex: criar pasta: data/minha_pasta)",
            )

        # Desktop/Área de Trabalho (resolve via Known Folder; inclui OneDrive redirecionado)
        if re.search(r"\b([aá]rea de trabalho|desktop)\b", norm):
            return Plan(
                intent="os.mkdir",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.mkdir", args={"known_folder": "desktop", "name": name})],
                risk=RiskLevel.HIGH,
                final_response=f"Ok, criei a pasta na Área de Trabalho: {name}",
            )

        # Drive específico (ex: D:, 'disco D', 'SSD (D:)')
        drive = None
        m_drive = re.search(r"\b([c-zC-Z])\s*:\b", msg)
        if m_drive:
            drive = m_drive.group(1).upper()
        else:
            m_drive2 = re.search(r"\bdisco\s+([c-z])\b", norm)
            if m_drive2:
                drive = m_drive2.group(1).upper()
            elif re.search(r"\bssd\b", norm) and re.search(r"\b[dD]\b", msg):
                drive = "D"

        if drive:
            return Plan(
                intent="os.mkdir",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.mkdir", args={"path": f"{drive}:/{name}"})],
                risk=RiskLevel.HIGH,
                final_response=f"Ok, criei a pasta em {drive}:\\{name}",
            )

        # Default: workspace
        rel = name.replace("\\", "/")
        return Plan(
            intent="fs.mkdir",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.mkdir", args={"path": rel})],
            risk=RiskLevel.LOW,
            final_response=f"Ok, criei a pasta no workspace: {rel}",
        )

    # Regra: copiar arquivo/pasta
    m = re.search(r"\b(copiar|copie|copy)\b\s+(.+?)\s+\b(para|pra|to)\b\s+(.+)$", msg, flags=re.IGNORECASE)
    if m:
        src = m.group(2).strip().strip('"').strip("'")
        dst = m.group(4).strip().strip('"').strip("'")
        return Plan(
            intent="fs.copy",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.copy", args={"src": src, "dst": dst, "overwrite": False})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, copiei no workspace.",
        )

    # Regra: mover/renomear
    m = re.search(r"\b(mover|mova|move|renomear|renomeie|rename|mv)\b\s+(.+?)\s+\b(para|pra|to)\b\s+(.+)$", msg, flags=re.IGNORECASE)
    if m:
        src = m.group(2).strip().strip('"').strip("'")
        dst = m.group(4).strip().strip('"').strip("'")
        return Plan(
            intent="fs.move",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.move", args={"src": src, "dst": dst, "overwrite": False})],
            risk=RiskLevel.HIGH,
            final_response="Ok, movi/renomeei no workspace.",
        )

    # Regra: DEV - executar comando (ex: "executar: python -c \"print(2+2)\"")
    # Regra: DEV - compilar/verificar o projeto (Python)
    # "compilar" em Python = verificar que tudo importa/compila + (opcional) rodar testes.
    if re.search(r"\b(compilar|compila|compile|build)\b", norm) and re.search(
        r"\b(projeto|project|repositorio|repo)\b", norm
    ):
        # Mantemos comandos allowlisted (python/pytest) para passar pelo sandbox com segurança.
        return Plan(
            intent="dev.exec",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.exec",
                    args={"command": "python -m compileall -q omniscia", "timeout_s": 120},
                ),
                ToolCall(
                    tool_name="dev.exec",
                    args={"command": "python -m pytest -q", "timeout_s": 300},
                ),
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou verificar/compilar o projeto (compileall) e rodar os testes (requer aprovacao).",
        )

    m = re.search(r"\b(executar|rodar)\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        command = m.group(2).strip()

        # Heurística de risco: comandos destrutivos viram CRITICAL.
        cmd_norm = _normalize(command)
        critical = bool(re.search(r"\b(rm\s+-rf|del\b|erase\b|format\b|shutdown\b|reg\b)\b", cmd_norm))

        return Plan(
            intent="dev.exec",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="dev.exec", args={"command": command, "timeout_s": 120})],
            risk=RiskLevel.CRITICAL if critical else RiskLevel.HIGH,
            final_response="Vou executar o comando no sandbox.",
        )

    # Regra: DEV - python rápido (ex: "python: print(2+2)")
    m = re.search(r"\bpython\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        return Plan(
            intent="dev.run_python",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="dev.run_python", args={"code": code, "timeout_s": 60})],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou executar esse Python.",
        )

    # Regra: DEV - auto-fix de arquivo python (ex: "autofix script.py")
    m = re.search(r"\b(autofix|auto\s*fix|corrigir)\b\s+([\w\-./\\]+\.py)\b", norm)
    if m:
        path = m.group(2).strip().replace("\\", "/")
        return Plan(
            intent="dev.autofix_python_file",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.autofix_python_file",
                    args={"path": path, "max_iters": 3, "timeout_s": 60},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou tentar corrigir o arquivo e executar novamente.",
        )

    # Regra: DEV - auto-fix por comando (ex: "autofixcmd: pytest -q")
    m = re.search(r"\b(autofixcmd|auto\s*fix\s*cmd)\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        command = m.group(2).strip()
        return Plan(
            intent="dev.autofix_cmd",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.autofix_cmd",
                    args={"command": command, "max_iters": 3, "timeout_s": 120},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou tentar corrigir até o comando passar.",
        )

    # Regra: DEV - corrigir testes (atalho para pytest)
    if re.search(r"\b(corrigir testes|arrumar testes|fix tests|rodar testes|run tests)\b", norm):
        return Plan(
            intent="dev.autofix_cmd",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.autofix_cmd",
                    args={"command": "pytest -q", "max_iters": 3, "timeout_s": 180},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou rodar os testes e tentar corrigir o que falhar.",
        )

    # Regra: GUI - mover mouse (ex: "mover mouse 100 200")
    m = re.search(r"\b(mover mouse|move mouse)\b\s+(\d+)\s+(\d+)", norm)
    if m:
        x = int(m.group(2))
        y = int(m.group(3))
        return Plan(
            intent="gui.move_mouse",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.move_mouse", args={"x": x, "y": y})],
            risk=RiskLevel.HIGH,
            final_response="Movi o mouse.",
        )

    # Regra: GUI - clicar (ex: "clicar 100 200")
    m = re.search(r"\b(clicar|click)\b\s+(\d+)\s+(\d+)", norm)
    if m:
        x = int(m.group(2))
        y = int(m.group(3))
        return Plan(
            intent="gui.click",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.click", args={"x": x, "y": y})],
            risk=RiskLevel.CRITICAL,
            final_response="Vou clicar (requer aprovação).",
        )

    # Regra: GUI - digitar (ex: "digitar: olá mundo")
    m = re.search(r"\b(digitar|type)\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        text = m.group(2)
        return Plan(
            intent="gui.type_text",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.type_text", args={"text": text})],
            risk=RiskLevel.CRITICAL,
            final_response="Vou digitar no foco atual (requer aprovação).",
        )

    # Regra: GUI - posição do mouse
    # Colocamos depois de mover/clicar/digitar para evitar conflitos.
    if (
        "mouse" in norm
        and any(k in norm for k in ["posicao", "pos", "onde"])
        and not re.search(r"\d+\s+\d+", norm)
    ):
        return Plan(
            intent="gui.get_mouse",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.get_mouse", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui está a posição do mouse.",
        )

    # Regra: memória
    if re.search(r"\b(lembra|lembrar|memoria|o que falamos|historico)\b", norm):
        if re.search(r"\b(ultim|recent|timeline|log|acao|acoes)\b", norm):
            return Plan(
                intent="memory.recent",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="memory.recent", args={"limit": 30})],
                risk=RiskLevel.LOW,
                final_response="Aqui estão as ações mais recentes.",
            )
        # Extrai query simples removendo palavras comuns.
        q = re.sub(r"\b(lembra|lembrar|memoria|o que falamos|historico)\b", "", norm)
        q = q.strip() or msg
        return Plan(
            intent="memory.search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.search", args={"query": q, "limit": 5})],
            risk=RiskLevel.LOW,
            final_response="Busquei na memória recente.",
        )

    # Regra: criar/iniciar projeto python (scaffold)
    if re.search(r"\b(projeto|project|app|aplicacao|aplicacao)\b", norm) and re.search(
        r"\b(criar|crie|cria|novo|iniciar|inicia|montar|gera|gerar)\b",
        norm,
    ):
        wants_python = bool(re.search(r"\bpython\b", norm))
        # Default: python (mais útil no workspace do agente)
        if wants_python or "java" not in norm:
            name = _guess_name_from_text(msg) or "MeuProjeto"
            return Plan(
                intent="dev.scaffold_project",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="dev.scaffold_project",
                        args={"name": name},
                    ),
                ],
                risk=RiskLevel.HIGH,
                final_response="Ok — vou criar um projeto Python no workspace (requer aprovação).",
            )

    # Regra: web read-only (ler página)
    # Se detectar uma URL ou intenção clara de abrir/ler um site.
    m = re.search(r"https?://\S+", msg)
    wants_web = bool(m) or bool(re.search(r"\b(abra|abrir|ler|leia|resuma|resumir)\b.*\b(site|pagina)\b", norm))
    if wants_web:
        if m:
            url = m.group(0)
        else:
            # Extrai algo que pareça domínio (com path opcional), ex: example.com/foo
            m2 = re.search(r"\b([a-zA-Z0-9][\w.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)\b", msg)
            url = m2.group(1) if m2 else ""
        return Plan(
            intent="web.read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="web.get_page_text", args={"url": url, "max_chars": 6000})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, vou abrir a página e extrair o texto (read-only).",
        )

    # Regra: status/config/settings
    if norm in {"settings", "config", "configuracao", "configuracoes", "status", "seguranca"}:
        return Plan(
            intent="core.show_settings",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.show_settings", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui estão as configurações efetivas.",
        )

    # Regra: ajuda/tools
    if norm in {"ajuda", "help", "comandos", "commands"}:
        return Plan(
            intent="core.help",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.help", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui vai um guia rápido.",
        )

    if norm in {"tools", "tool"}:
        return Plan(
            intent="core.list_tools",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.list_tools", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui está a lista de tools disponíveis.",
        )

    # Regra 0: saída
    if norm in {"sair", "exit", "quit"}:
        return Plan(intent="exit", user_message=msg, final_response="Encerrando.")

    # Regra 1: operações potencialmente críticas
    # Ex: "apague", "delete", "rm -rf" etc.
    if re.search(r"\b(apagar|delete|deletar|rm\s+-rf|formatar)\b", norm):
        # Heurística simples para extrair path depois de "apagar".
        m = re.search(r"\b(apagar|delete|deletar)\s+([^\n\r]+)", norm)
        path = ""
        if m:
            path = m.group(2).strip().strip('"').strip("'")
        return Plan(
            intent="filesystem.delete",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.delete", args={"path": path})],
            risk=RiskLevel.CRITICAL,
            final_response="Ação de apagar detectada. Preciso de confirmação (HITL).",
        )

    # Regra: listar diretório
    if re.search(r"\b(listar|lista|ls|dir)\b", norm):
        return Plan(
            intent="filesystem.list",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.list_dir", args={"path": "."})],
            risk=RiskLevel.LOW,
            final_response="Listando arquivos do workspace.",
        )

    # Regra: ler arquivo
    m = re.search(r"\b(ler|leia|cat|abrir)\b\s+([^\s]+)", msg, flags=re.IGNORECASE)
    if m and m.group(2):
        path = m.group(2).strip().strip('"').strip("'").replace("\\", "/")
        return Plan(
            intent="filesystem.read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.read_text", args={"path": path, "max_chars": 8000})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, vou ler o arquivo.",
        )

    # Regra 2: escrever arquivo
    if norm.startswith("crie um arquivo") or norm.startswith("criar arquivo"):
        # Exemplo esperado: "crie um arquivo path=foo.txt conteúdo=..."
        return Plan(
            intent="dev.write_file",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="write_file",
                    args={
                        "path": "data/tmp/notes.txt",
                        "content": f"Comando: {msg}\n",
                    },
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou criar um arquivo (relativo ao workspace).",
        )

    # Default: chat (sem tools). O brain pode responder via LLM quando configurado.
    return Plan(
        intent="chat",
        user_message=msg,
        tool_calls=[],
        risk=RiskLevel.LOW,
        final_response="Ok. Me diga o que você quer fazer/entender e eu te ajudo.",
    )


def _route_with_llm(settings: Settings, user_message: str) -> Plan | None:
    """Usa LLM para produzir um Plan em JSON.

    Rationale:
    - Mantemos o LLM como "gerador de estrutura" (JSON), não como executor.
    - Validamos via Pydantic antes de aceitar.

    Segurança:
    - Se config estiver ausente, retornamos None e caímos no heurístico.
    """

    return _route_with_llm_messages(settings, [{"role": "user", "content": str(user_message or "").strip()}])


def _route_with_llm_messages(settings: Settings, messages: list[dict[str, str]]) -> Plan | None:
    """Usa LLM para produzir um Plan em JSON, aceitando histórico curto.

    `messages` deve ser uma lista no formato OpenAI: {role, content}.
    Roles aceitas aqui: system/user/assistant.
    """

    from omniscia.core.litellm_env import provider_requires_api_key

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        logger.warning("Router LLM habilitado, mas falta OMNI_LLM_*; caindo no heurístico")
        return None

    try:
        from litellm import completion
    except Exception:  # noqa: BLE001
        logger.exception("litellm não disponível; caindo no heurístico")
        return None

    system = (
        "Você é um roteador de ferramentas para um agente autônomo. "
        "Sua tarefa é transformar a intenção do usuário em um JSON de plano. "
        "Responda APENAS com JSON válido (sem markdown, sem texto extra).\n\n"
        "FORMATO:\n"
        "{\n"
        "  \"intent\": string,\n"
        "  \"user_message\": string,\n"
        "  \"risk\": \"LOW\"|\"MEDIUM\"|\"HIGH\"|\"CRITICAL\",\n"
        "  \"tool_calls\": [ { \"tool_name\": string, \"args\": object } ],\n"
        "  \"final_response\": string\n"
        "}\n\n"
        "REGRAS DE RISCO:\n"
        "- Se envolver apagar arquivos, formatar, shutdown, pagamentos/compras, login, transferir dinheiro: risk=CRITICAL.\n"
        "- Se envolver automação de mouse/teclado (clicar/digitar) ou executar comandos: risk=HIGH (ou CRITICAL se destrutivo).\n\n"
        "CONTEXTO (IMPORTANTE):\n"
        "- Você pode receber mensagens anteriores com resultados de tools (ex.: 'TOOL_RESULT ...'). Use isso para decidir próximos passos.\n\n"
        "REGRA MAIS IMPORTANTE (NÃO INVENTE AUTOMAÇÃO):\n"
        "- Se o usuário pediu apenas orientação/explicação/dicas (ex: jogos, estudo, dúvidas), responda em texto: tool_calls=[] e risk=LOW.\n"
        "- Só use tools de tela (screen.*), janela (win.focus_window) ou GUI (gui.* / screen.click_text) quando o usuário pedir explicitamente para ver/clicar/digitar na tela.\n"
        "- Só use dev.* quando o usuário pedir explicitamente para executar/rodar comandos ou código.\n"
        "- Nunca adivinhe window_title: só preencha window_title se o usuário fornecer o texto do título (ou substring) na mensagem.\n\n"
        "REGRAS ESPECÍFICAS:\n"
        "- Se usar discord.send_message, inclua antes um os.open_app com app='discord' para garantir que o Discord esteja aberto/em foco.\n\n"
        "- jGRASP (MUITO IMPORTANTE):\n"
        "  - Se o usuário pedir um programa/código Java 'funcional', 'completo', 'de matriz', 'de matemática', etc., use jgrasp.create_java_program OU jgrasp.write_code com o campo code (NÃO use apenas message).\n"
        "  - O campo code deve conter Java compilável, sem markdown e sem cercas de código (```), e a classe pública deve bater com class_name.\n"
        "  - Defaults: path='scratch/<ClassName>.java' e class_name='<ClassName>' (PascalCase).\n"
        "  - Só use path com prefixo 'desktop:/' quando o usuário pedir explicitamente 'Área de Trabalho/desktop'.\n"
        "  - Se o usuário disser que o jGRASP já está aberto e/ou que não precisa criar arquivo, prefira jgrasp.write_code com select_all=true (substitui o editor atual).\n"
        "  - Se houver TOOL_RESULT indicando falha por foco/timing, ajuste settle_ms para mais alto (ex.: 1200) e garanta os.open_app('jgrasp') antes.\n\n"
        "- Self-coding (opt-in):\n"
        "  - Se NÃO existir uma tool adequada e o usuário pedir para 'criar uma ferramenta' ou 'criar um script', você pode propor self-coding.\n"
        "  - Faça isso SOMENTE como plano explícito e seguro: (1) write_file em scratch/<nome>.py, (2) dev.run_python com script='scratch/<nome>.py'.\n"
        "  - Alternativa (preferida para plugins): use dev.create_tool para criar um módulo em omniscia/tools/custom e recarregar tools no runtime.\n"
        "  - Marque risk=CRITICAL e descreva claramente o que o script faz.\n"
        "  - Nunca escreva scripts fora de scratch/.\n\n"
        "FERRAMENTAS DISPONÍVEIS (tool_name -> args):\n"
        "- core.show_settings -> {}\n"
        "- core.list_tools -> {}\n"
        "- echo -> {text}\n"
        "- write_file -> {path, content}\n"
        "- os.open_url -> {url} (apenas http/https)\n"
        "- os.open_explorer -> {path?} (path relativo; default '.')\n"
        "- os.open_app -> {app} (allowlist configurável via OMNI_OPEN_APPS_FILE/OMNI_OPEN_APPS_JSON; exemplos: calculator, notepad, paint, snippingtool, discord)\n"
        "- win.focus_window -> {title_contains, timeout_s?, visible_only?} (HIGH; Windows; retorna rect)\n"
        "- discord.send_message -> {to, message, settle_ms?} (CRITICAL; requer Discord em foco)\n"
        "- jgrasp.create_java_program -> {path?, class_name?, message?, code?, open_in_jgrasp?, settle_ms?} (HIGH; cria .java e abre no jGRASP; use code para conteúdo completo)\n"
        "- jgrasp.write_code -> {code, settle_ms?, select_all?} (HIGH; cola/escreve no editor do jGRASP; não cria arquivo)\n"
        "- os.mkdir -> {path? , known_folder? , name?} (HIGH; Windows; path absoluto ou known_folder=desktop/downloads/documents)\n"
        "- memory.search -> {query, limit}\n"
        "- memory.search_vector -> {query, limit} (se disponível)\n"
        "- memory.index_recent -> {limit} (se disponível)\n"
        "- memory.remember -> {text, topic?, tags?} (se disponível; salva memória durável)\n"
        "- web.get_page_text -> {url, max_chars}\n"
        "- web.screenshot -> {url, path?}\n"
        "- web.get_links -> {url, max_links?}\n"
        "- fs.list_dir -> {path}\n"
        "- fs.read_text -> {path, max_chars}\n"
        "- fs.mkdir -> {path}\n"
        "- fs.copy -> {src, dst, overwrite?}\n"
        "- fs.move -> {src, dst, overwrite?} (pode ser renomear)\n"
        "- fs.delete -> {path} (CRITICAL)\n"
        "- screen.screenshot -> {}\n"
        "- screen.ocr -> {path?}\n"
        "- screen.find_text -> {query, path?, window_title?, max_results?, min_conf?} (retorna caixas x/y/w/h)\n"
        "- screen.click_text -> {query, path?, window_title?, min_conf?} (CRITICAL)\n"
        "- gui.get_mouse -> {}\n"
        "- gui.move_mouse -> {x, y}\n"
        "- gui.click -> {x, y} (CRITICAL)\n"
        "- gui.click_box_center -> {x, y, w, h} (CRITICAL)\n"
        "- gui.type_text -> {text} (CRITICAL)\n"
        "IMPORTANTE: Para abrir sites/apps/pastas, use os.open_url/os.open_explorer/os.open_app (NÃO use dev.exec).\n"
        "IMPORTANTE: Para clicar/digitar na tela, primeiro use screen.find_text para obter coordenadas, depois gui.click/gui.type_text.\n"
        "- dev.exec -> {command, timeout_s}\n"
        "- dev.run_python -> {code, timeout_s}\n"
        "- dev.create_tool -> {name, code, overwrite?} (CRITICAL; cria tool custom e hot-reload; requer opt-in)\n"
        "- dev.autofix_python_file -> {path, max_iters, timeout_s}\n"
        "- dev.autofix_cmd -> {command, max_iters, timeout_s} (apenas pytest)\\n"
    )

    llm_model = settings.llm_model

    # Não logamos a key; só configuramos no ambiente do litellm.
    from omniscia.core.litellm_env import apply_litellm_env

    apply_litellm_env(settings)

    try:
        clean_msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
        for m in messages:
            role = str((m or {}).get("role") or "").strip().lower()
            content = str((m or {}).get("content") or "")
            if role in {"user", "assistant", "system"} and content.strip():
                # Nunca deixamos o caller substituir o system principal.
                if role == "system":
                    role = "assistant"
                clean_msgs.append({"role": role, "content": content})

        resp = completion(model=llm_model, messages=clean_msgs, temperature=0.0)

        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]

        # Robustez: alguns modelos devolvem texto extra. Tentamos extrair o primeiro objeto JSON.
        raw = content.strip()
        try:
            data: dict[str, Any] = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            data = json.loads(raw[start : end + 1])

        return Plan.model_validate(data)
    except Exception as e:  # noqa: BLE001
        from omniscia.core.redact import redact_secrets

        logger.error(
            "Falha ao rotear via LLM; caindo no heurístico (%s)",
            redact_secrets(str(e)),
        )
        return None
