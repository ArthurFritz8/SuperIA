"""Entrada CLI do Omnisciência.

Rationale:
- Usamos Typer para uma CLI simples e extensível.
- O comando default inicia o loop do cérebro.

Execute:
- `python -m omniscia.app`
- ou, se instalado como script: `omniscia`
"""

from __future__ import annotations

import typer
from dataclasses import replace
from rich.console import Console
from rich.table import Table

from omniscia.core.brain import run_brain_loop
from omniscia.core.config import Settings
from omniscia.core.logging import configure_logging

from omniscia.core.selftest import run_selftest
from omniscia.core.doctor import run_doctor
from omniscia.modules.stt.factory import build_stt

app = typer.Typer(add_completion=False, help="Omnisciência — assistente autônomo modular")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Comportamento default.

    Rationale:
    - Queremos que `python -m omniscia.app` já inicie o assistente (MVP simples).
    - Ao mesmo tempo, queremos um CLI extensível com subcomandos (ex: `memory`, `web`).

    Implementação:
    - Se nenhum subcomando for chamado, executamos `run()`.
    """

    if ctx.invoked_subcommand is None:
        run()


@app.command()
def run(
    stt_mode: str = typer.Option(
        None,
        "--stt-mode",
        help="Override do modo de entrada: text | vosk | whisper_openai (por padrao usa OMNI_STT_MODE).",
    ),
    tts_mode: str = typer.Option(
        None,
        "--tts-mode",
        help="Override do modo de fala: none | pyttsx3 (por padrao usa OMNI_TTS_MODE).",
    ),
    seconds: float = typer.Option(
        None,
        "--seconds",
        help="Override do tempo de gravacao (OMNI_STT_RECORD_SECONDS) quando estiver em voz.",
    ),
) -> None:
    """Inicia o loop principal do assistente."""

    settings = Settings.load()
    if stt_mode is not None:
        stt_mode = (stt_mode or "").strip().lower()
        if stt_mode not in {"text", "vosk", "whisper_openai"}:
            raise typer.BadParameter("stt_mode invalido (use: text | vosk | whisper_openai)")
        settings = replace(settings, stt_mode=stt_mode)  # type: ignore[arg-type]

    if tts_mode is not None:
        tts_mode = (tts_mode or "").strip().lower()
        if tts_mode not in {"none", "pyttsx3"}:
            raise typer.BadParameter("tts_mode invalido (use: none | pyttsx3)")
        settings = replace(settings, tts_mode=tts_mode)  # type: ignore[arg-type]

    if seconds is not None:
        settings = replace(settings, stt_record_seconds=float(seconds))
    configure_logging(settings)
    run_brain_loop(settings)


@app.command()
def selftest() -> None:
    """Roda um conjunto curto de testes offline (sem gastar LLM).

    Útil para validar instalação, tools básicas e roteamento determinístico.
    """

    ok, report = run_selftest()
    typer.echo(report)
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def doctor() -> None:
    """Diagnostica ambiente/dependências e sugere correções.

    Útil quando aparece "tool não registrada" ou erros de dependência opcional.
    """

    settings = Settings.load()
    ok, report = run_doctor(settings=settings)
    typer.echo(report)
    if not ok:
        raise typer.Exit(code=2)


@app.command()
def dictate(
    seconds: float = typer.Option(None, help="Duração de gravação (override do OMNI_STT_RECORD_SECONDS)"),
    stt_mode: str = typer.Option(
        None,
        "--stt-mode",
        help="Override do modo de entrada: vosk | whisper_openai (por padrao usa OMNI_STT_MODE).",
    ),
    device: int = typer.Option(
        None,
        "--device",
        help="Override do OMNI_AUDIO_INPUT_DEVICE (índice do sounddevice).",
    ),
    gain: float = typer.Option(
        None,
        "--gain",
        help="Override do OMNI_AUDIO_INPUT_GAIN (ex: 1, 10, 50).",
    ),
) -> None:
    """Ditado (voz -> texto) em uma rodada.

    Use quando você quer só transcrever e copiar/colar em outro lugar.
    """

    settings = Settings.load()
    if stt_mode is not None:
        stt_mode = (stt_mode or "").strip().lower()
        if stt_mode not in {"vosk", "whisper_openai"}:
            raise typer.BadParameter("stt_mode invalido (use: vosk | whisper_openai)")
        settings = replace(settings, stt_mode=stt_mode)  # type: ignore[arg-type]

    if seconds is not None:
        settings = replace(settings, stt_record_seconds=float(seconds))

    if device is not None:
        settings = replace(settings, audio_input_device=int(device))

    if gain is not None:
        settings = replace(settings, audio_input_gain=float(gain))

    console = Console()
    stt = build_stt(settings, console=console)
    if not stt.is_voice:
        console.print(
            "[red]STT não está em modo voz.[/red] "
            "Use OMNI_STT_MODE=whisper_openai (com OMNI_STT_OPENAI_API_KEY) ou OMNI_STT_MODE=vosk (com OMNI_STT_VOSK_MODEL_DIR)."
        )
        raise typer.Exit(code=2)

    console.print(f"[dim]Gravando por ~{settings.stt_record_seconds}s... fale agora.[/dim]")
    text = stt.listen().strip()
    if text:
        console.print(text)
    else:
        console.print(
            "[yellow]Não veio texto da transcrição.[/yellow] "
            "Confirme se você falou durante a gravação e se o microfone está correto. "
            f"(OMNI_AUDIO_INPUT_DEVICE={settings.audio_input_device})"
        )
        console.print(
            "Dica: rode `python -c \"import sounddevice as sd; print(sd.query_devices())\"` e ajuste OMNI_AUDIO_INPUT_DEVICE."
        )


@app.command("mics")
def list_mics() -> None:
    """Lista dispositivos de entrada (microfones) com índice do sounddevice."""

    console = Console()
    try:
        import sounddevice as sd
    except Exception as e:
        console.print(f"[red]Falha ao importar sounddevice:[/red] {e}")
        raise typer.Exit(code=2)

    devices = sd.query_devices()
    table = Table(title="Dispositivos de entrada (sounddevice)")
    table.add_column("idx", justify="right")
    table.add_column("in")
    table.add_column("sr")
    table.add_column("nome")

    for idx, d in enumerate(devices):
        try:
            max_in = int(d.get("max_input_channels") or 0)
        except Exception:
            max_in = 0
        if max_in <= 0:
            continue
        sr = d.get("default_samplerate")
        name = str(d.get("name") or "")
        table.add_row(str(idx), str(max_in), f"{float(sr):.0f}" if sr else "?", name)

    console.print(table)


@app.command("mic-probe")
def mic_probe(
    seconds: float = typer.Option(1.5, help="Segundos por device (fale continuamente enquanto roda)."),
    top: int = typer.Option(6, help="Quantos candidatos mostrar no ranking."),
    include_all: bool = typer.Option(
        False,
        "--all",
        help="Inclui devices que não parecem microfone (útil se seu driver não tem 'Microfone' no nome).",
    ),
) -> None:
    """Testa rapidamente dispositivos de entrada e sugere OMNI_AUDIO_INPUT_DEVICE.

    Como usar:
    - Rode e fale "teste teste teste" durante todo o scan.
    - O comando mede energia (RMS) e pico (maxabs) por device.
    """

    console = Console()
    try:
        import sounddevice as sd
        import numpy as np
    except Exception as e:
        console.print(f"[red]Dependência de voz faltando:[/red] {e}")
        raise typer.Exit(code=2)

    seconds = float(max(0.5, seconds))
    top = int(max(1, min(20, top)))

    devices = sd.query_devices()
    candidates: list[tuple[int, dict]] = []
    for idx, d in enumerate(devices):
        try:
            max_in = int(d.get("max_input_channels") or 0)
        except Exception:
            max_in = 0
        if max_in <= 0:
            continue

        name = str(d.get("name") or "")
        if not include_all:
            lowered = name.lower()
            if not ("microfone" in lowered or "microphone" in lowered or "mic" in lowered):
                continue

        candidates.append((idx, d))

    if not candidates:
        console.print(
            "[yellow]Nenhum device candidato encontrado.[/yellow] Rode `python -m omniscia.app mics` para ver a lista completa ou use `mic-probe --all`."
        )
        raise typer.Exit(code=2)

    console.print(
        f"[dim]Falando agora: o comando vai gravar ~{seconds:.1f}s por device e rankear por energia (RMS).[/dim]"
    )

    results: list[dict] = []
    for idx, d in candidates:
        name = str(d.get("name") or "")
        sr = float(d.get("default_samplerate") or 44100.0)

        try:
            audio = sd.rec(
                int(seconds * sr),
                samplerate=int(sr),
                channels=1,
                dtype="float32",
                device=idx,
            )
            sd.wait()
            x = audio.reshape(-1).astype(np.float32, copy=False)
            maxabs = float(np.max(np.abs(x))) if x.size else 0.0
            rms = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
        except Exception as e:
            results.append(
                {
                    "idx": idx,
                    "name": name,
                    "sr": sr,
                    "rms": 0.0,
                    "maxabs": 0.0,
                    "error": str(e),
                }
            )
            continue

        results.append({"idx": idx, "name": name, "sr": sr, "rms": rms, "maxabs": maxabs, "error": ""})

    ranked = sorted(results, key=lambda r: (r["rms"], r["maxabs"]), reverse=True)

    table = Table(title="Ranking de microfones (fale durante o scan)")
    table.add_column("idx", justify="right")
    table.add_column("rms")
    table.add_column("max")
    table.add_column("sr")
    table.add_column("nome")
    table.add_column("erro")

    for r in ranked[:top]:
        table.add_row(
            str(r["idx"]),
            f"{r['rms']:.6f}",
            f"{r['maxabs']:.4f}",
            f"{r['sr']:.0f}",
            (r["name"][:48] + "…") if len(r["name"]) > 49 else r["name"],
            r["error"][:28] if r["error"] else "",
        )
    console.print(table)

    best = next((r for r in ranked if not r["error"] and r["rms"] > 0.0), None)
    if not best:
        console.print("[red]Não consegui gravar com nenhum device.[/red]")
        raise typer.Exit(code=2)

    # Sugestão de ganho inicial: tenta levar maxabs para ~0.30 (sem clip), limitado.
    # Se o maxabs já for alto, mantém 1.
    target_peak = 0.30
    maxabs = float(best["maxabs"] or 0.0)
    if maxabs <= 1e-6:
        suggested_gain = 20.0
    else:
        suggested_gain = target_peak / maxabs
    suggested_gain = float(min(50.0, max(1.0, suggested_gain)))

    console.print("\n[bold]Sugestão[/bold]")
    console.print(f"- OMNI_AUDIO_INPUT_DEVICE={best['idx']}")
    console.print(f"- OMNI_AUDIO_INPUT_GAIN={suggested_gain:.1f}")
    console.print("(Depois rode `python -m omniscia.app dictate --seconds 6` para validar.)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
