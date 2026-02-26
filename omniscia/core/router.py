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
        # GUI explicit coordinates
        "gui.get_mouse",
        "gui.move_mouse",
        "gui.click",
        "gui.click_box_center",
        "gui.type_text",
        # Web read-only
        "web.get_page_text",
        "win.focus_window",
        "discord.send_message",
        "jgrasp.create_java_program",
    }
    if heuristic.intent in deterministic_intents:
        return heuristic

    if settings.router_mode == "llm":
        plan = _route_with_llm(settings, user_message)
        if plan is not None:
            return plan

    return heuristic


def _route_heuristic(user_message: str) -> Plan:
    msg = user_message.strip()
    norm = _normalize(msg)

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

    # Regra: screenshot
    if re.search(r"\b(screenshot|printscreen|print screen|captura de tela|tire uma captura)\b", norm):
        return Plan(
            intent="vision.screenshot",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="screen.screenshot", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Tirei uma captura de tela.",
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
            tool_calls=[
                ToolCall(tool_name="os.open_url", args={"url": "https://www.youtube.com/"})
            ],
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

    # Regra: criar um programa/projeto no jGRASP (cria arquivo Java e abre no jGRASP)
    if "jgrasp" in norm and re.search(r"\b(criar|crie|cria|fazer|faca|faça|gerar|gere|montar)\b", norm):
        if re.search(r"\b(programa|projeto|codigo|codigos|c[oó]digo|c[oó]digos)\b", norm):
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
    if norm in {"tools", "tool", "ajuda", "help", "comandos", "commands"}:
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

    # Default: ecoa e responde
    return Plan(
        intent="chat",
        user_message=msg,
        tool_calls=[ToolCall(tool_name="echo", args={"text": msg})],
        risk=RiskLevel.LOW,
        final_response="Entendi. (MVP: roteador heurístico)",
    )


def _route_with_llm(settings: Settings, user_message: str) -> Plan | None:
    """Usa LLM para produzir um Plan em JSON.

    Rationale:
    - Mantemos o LLM como "gerador de estrutura" (JSON), não como executor.
    - Validamos via Pydantic antes de aceitar.

    Segurança:
    - Se config estiver ausente, retornamos None e caímos no heurístico.
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
        "REGRAS ESPECÍFICAS:\n"
        "- Se usar discord.send_message, inclua antes um os.open_app com app='discord' para garantir que o Discord esteja aberto/em foco.\n\n"
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
        "- jgrasp.create_java_program -> {path?, class_name?, message?, open_in_jgrasp?, settle_ms?} (HIGH; cria .java no workspace e abre no jGRASP)\n"
        "- os.mkdir -> {path? , known_folder? , name?} (HIGH; Windows; path absoluto ou known_folder=desktop/downloads/documents)\n"
        "- memory.search -> {query, limit}\n"
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
        "- dev.autofix_python_file -> {path, max_iters, timeout_s}\n"
        "- dev.autofix_cmd -> {command, max_iters, timeout_s} (apenas pytest)\\n"
    )

    llm_provider = settings.llm_provider
    llm_model = settings.llm_model
    llm_api_key = settings.llm_api_key
    from omniscia.core.litellm_env import provider_requires_api_key

    needs_key = provider_requires_api_key(llm_provider)
    has_key = bool((llm_api_key or "").strip())
    if not (llm_provider and llm_model and (has_key or not needs_key)):
        return None

    # Não logamos a key; só configuramos no ambiente do litellm.
    from omniscia.core.litellm_env import apply_litellm_env

    apply_litellm_env(settings)

    try:
        resp = completion(
            model=llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
        )

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
