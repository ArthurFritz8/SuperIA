# Omnisciência (Omnisciência) — Assistente Pessoal Autônomo Universal

> Codinome: **Omnisciência** ("mãos, olhos, ouvidos e memória")

Este repositório implementa um agente autônomo modular em Python, pensado para:
- **Perceber** (voz/visão), **agir** (OS/web), **programar** (auto-correção) e **lembrar** (memória/RAG)
- Operar com **Human-in-the-Loop (HITL)** para ações críticas

## Visão de arquitetura (alto nível)

O sistema é dividido em 4 camadas:

1. **Interface (I/O)**: STT/TTS, visão, CLI.
2. **Cérebro (Core)**: roteamento, planejamento, políticas de segurança (HITL), execução de ferramentas.
3. **Ferramentas (Tools)**: wrappers seguros para OS, navegador, DevAgent, integrações.
4. **Memória**: histórico, vetores (RAG), preferências, segredos (criptografados).

## Árvore planejada do projeto

A estrutura abaixo é a "espinha dorsal" (nem tudo precisa ser implementado de uma vez):

```
SuperIA/
  README.md
  pyproject.toml
  requirements.txt
  .env.example
  .gitignore

  omniscia/
    __init__.py
    app.py

    core/
      __init__.py
      brain.py          # loop principal: ouvir -> decidir -> agir -> responder
      router.py         # interpreta comando e gera plano (LLM ou heurística)
      tools.py          # registro/execução de ferramentas
      hitl.py           # Human-in-the-Loop: aprovação p/ ações críticas
      config.py         # settings via env
      types.py          # schemas (Pydantic) p/ planos, ferramentas, memória
      logging.py        # setup de logs

    modules/
      stt/
        __init__.py
        base.py
        fallback_text.py
        whisper_openai.py

      tts/
        __init__.py
        base.py
        pyttsx3_tts.py

      vision/
        __init__.py
        screenshot.py
        ocr.py
        vision_llm.py

      os_control/
        __init__.py
        actions.py
        filesystem.py

      web/
        __init__.py
        browser.py
        actions.py

      dev_agent/
        __init__.py
        coder.py
        sandbox.py

      memory/
        __init__.py
        store.py
        embeddings.py
        secrets.py

      integrations/
        __init__.py
        iot.py
        news.py
        finance.py

  data/
    .gitkeep
```

## Stack tecnológico (por módulo)

> A estratégia aqui é **núcleo mínimo** + **extras opcionais**. O agente deve rodar mesmo sem microfone, sem Tesseract, sem Playwright etc.

### Core (Cérebro)
- **Python 3.11+**
- `pydantic` (schemas e validação de planos)
- `typer` (CLI)
- `rich` (UI no terminal)
- `python-dotenv` (config por `.env`)
- `litellm` (camada multi-provider para LLMs: OpenAI/Azure/Gemini/Anthropic)

### Voz (STT/TTS)
- STT:
  - **MVP**: `fallback_text` (digitar no terminal)
  - Online: `openai` (Whisper API), via `OMNI_STT_MODE=whisper_openai`
  - Offline (opcional): `faster-whisper`
- TTS:
  - Offline: `pyttsx3`
  - Alternativa (opcional): `edge-tts`

### Visão
- Screenshot: `mss` + `Pillow`
- OCR: `pytesseract` (requer Tesseract instalado no sistema)
- VLM (opcional): Gemini Vision / OpenAI Vision via `litellm`

### Ações (OS)
- Automação: `pyautogui` (mouse/teclado)
- Hotkeys/escuta (opcional): `pynput`

### Web
- **Playwright** (recomendado) para automação robusta
- Alternativa: Selenium (se necessário)

### Memória / RAG
- Vetor DB local: `chromadb`
- Embeddings:
  - Local: `sentence-transformers`
  - Online: embeddings via provider LLM
- Segredos:
  - `cryptography` para criptografia local
  - (Windows) `keyring` como alternativa integrada

### Integrações / IoT
- HTTP: `httpx`
- Automação por APIs: Home Assistant, Tuya, Philips Hue, etc.
- Jobs proativos: `apscheduler` (opcional)

## Rodando (MVP)

1) Crie um `.env` baseado em `.env.example`.

2) Instale dependências:

- `pip install -r requirements.txt`

3) Execute:

- `python -m omniscia.app`

O MVP roda em **modo texto**, usando LLM opcional. Se `OMNI_LLM_PROVIDER` não estiver configurado, ele usa um roteador heurístico simples.

## Voz (STT Whisper API) — opcional

1) Instale dependências de captura de microfone (opcional):

- `pip install sounddevice soundfile`

2) Configure no seu `.env` (não commitar):

- `OMNI_STT_MODE=whisper_openai`
- `OMNI_STT_OPENAI_API_KEY=...`

3) Rode:

- `python -m omniscia.app run`

Se faltar chave/deps/microfone, o sistema cai automaticamente para modo texto.

## Segurança (HITL)

Ações marcadas como `risk=CRITICAL` exigem confirmação explícita via terminal antes de executar (ex: apagar arquivos, compras, logins, envio de mensagens).

---

Se quiser, no próximo passo eu já adiciono: (a) STT com Whisper, (b) Playwright com um "browser tool" real, e (c) ChromaDB para memória persistente.

## GUI e Screenshot (opcional)

Para habilitar ferramentas de mouse/teclado e screenshot local:

- `pip install pyautogui mss pillow`

Comandos heurísticos úteis no MVP:
- `posição do mouse`
- `mover mouse 100 200`
- `clicar 100 200` (CRITICAL → pede YES)
- `digitar: hello` (CRITICAL → pede YES)
- `screenshot`

## OCR (opcional)

Para ler texto da tela localmente (sem enviar imagem para a internet):

- `pip install pytesseract`
- Instale o Tesseract no Windows e (se necessário) configure `OMNI_TESSERACT_CMD`.

Comando heurístico:
- `ocr` (ou "ler tela")

## DevAgent (Programador Interno) — MVP

Comandos heurísticos:
- `python: print(2+2)`
- `executar: python -c "print('ok')"`

Auto-correção (requer LLM configurado):
- `autofix caminho/arquivo.py`

Por segurança, o executor roda sem shell e só permite executáveis allowlisted (python/pytest/git) neste estágio.
