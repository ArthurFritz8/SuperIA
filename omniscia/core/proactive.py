"""Proatividade (opt-in) via APScheduler.

O agente pode 'falar primeiro' quando detectar anomalias (CPU/RAM muito alta).

Política:
- Apenas alerta e pede confirmação; nunca mata processos automaticamente.
- Possui cooldown para evitar spam.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ProactiveState:
    last_alert_ts: float = 0.0
    consecutive_high: int = 0


def start_proactive_scheduler(
    *,
    interval_s: int,
    cpu_threshold: int,
    ram_threshold: int,
    on_alert,
) -> None:
    """Inicia scheduler em background.

    `on_alert(message: str)` será chamado quando detectar condição.
    """

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Dependência ausente: apscheduler") from exc

    try:
        import psutil
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Dependência ausente: psutil") from exc

    state = ProactiveState()

    def _job() -> None:
        # Cooldown (10 min)
        now = time.time()
        if state.last_alert_ts and (now - state.last_alert_ts) < 600:
            return

        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory().percent

        if cpu >= cpu_threshold or mem >= ram_threshold:
            state.consecutive_high += 1
        else:
            state.consecutive_high = 0
            return

        # Exige 2 leituras consecutivas acima do threshold.
        if state.consecutive_high < 2:
            return

        # Descobre top process por CPU (best-effort)
        top = None
        try:
            procs = []
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    procs.append(p)
                except Exception:
                    continue
            # Primeira amostra
            for p in procs:
                try:
                    p.cpu_percent(None)
                except Exception:
                    pass
            time.sleep(0.15)
            best = (-1.0, None)
            for p in procs:
                try:
                    val = float(p.cpu_percent(None))
                    if val > best[0]:
                        best = (val, p)
                except Exception:
                    continue
            if best[1] is not None:
                top = (best[1].info.get("name"), best[1].info.get("pid"), best[0])
        except Exception:
            top = None

        extra = ""
        if top and top[0]:
            extra = f" Processo suspeito: {top[0]} (pid={top[1]} cpu~{top[2]:.0f}%)."

        msg = (
            f"Notei uso alto do sistema (CPU={cpu:.0f}%, RAM={mem:.0f}%).{extra} "
            "Deseja que eu te ajude a investigar/encerrar?"
        )
        state.last_alert_ts = now
        state.consecutive_high = 0
        on_alert(msg)

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_job, "interval", seconds=int(interval_s), id="proactive")
    sched.start()
