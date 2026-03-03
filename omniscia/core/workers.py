"""Workers em background (thread pool) para execuções longas.

Objetivo:
- Permitir que o loop principal continue responsivo enquanto uma automação roda.
- Coletar resultado/erro e emitir notificações para o usuário.

Notas:
- Mantemos thread-safe e simples: o worker não escreve no console nem na memória;
  ele apenas retorna um resumo. O loop principal imprime/apenda na memória.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class JobResult:
    job_id: str
    name: str
    status: str  # ok|error|cancelled
    output: str | None = None
    error: str | None = None
    duration_s: float = 0.0


@dataclass(frozen=True)
class JobInfo:
    job_id: str
    name: str
    created_ts: float
    done: bool
    status: str  # pending|running|ok|error|cancelled


class WorkerManager:
    def __init__(self, *, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="omni-worker")
        self._lock = threading.Lock()
        self._jobs: dict[str, tuple[str, float, Future]] = {}
        self._notifications: "queue.Queue[JobResult]" = queue.Queue()

    def submit(self, name: str, fn: Callable[[], tuple[str, str | None, str | None]]) -> str:
        """Submit a job.

        fn must return: (status, output, error)
        where status is ok|error|cancelled.
        """

        job_id = uuid.uuid4().hex[:10]
        created = time.time()

        def _runner() -> JobResult:
            t0 = time.time()
            try:
                status, output, error = fn()
            except Exception as exc:  # noqa: BLE001
                status, output, error = "error", None, str(exc)
            dt = max(0.0, time.time() - t0)
            return JobResult(job_id=job_id, name=name, status=status, output=output, error=error, duration_s=dt)

        fut = self._executor.submit(_runner)

        with self._lock:
            self._jobs[job_id] = (name, created, fut)

        def _done_cb(f: Future) -> None:  # noqa: ANN001
            try:
                res: JobResult = f.result()
            except Exception as exc:  # noqa: BLE001
                res = JobResult(job_id=job_id, name=name, status="error", error=str(exc))
            self._notifications.put(res)

        fut.add_done_callback(_done_cb)
        return job_id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            tup = self._jobs.get(job_id)
            if not tup:
                return False
            _, _, fut = tup
            return bool(fut.cancel())

    def get_info(self, job_id: str) -> JobInfo | None:
        with self._lock:
            tup = self._jobs.get(job_id)
        if not tup:
            return None
        name, created, fut = tup
        if fut.cancelled():
            status = "cancelled"
        elif fut.done():
            try:
                res: JobResult = fut.result()
                status = res.status
            except Exception:
                status = "error"
        else:
            status = "running"
        return JobInfo(job_id=job_id, name=name, created_ts=created, done=fut.done(), status=status)

    def list_jobs(self) -> list[JobInfo]:
        with self._lock:
            ids = list(self._jobs.keys())
        out: list[JobInfo] = []
        for jid in ids:
            info = self.get_info(jid)
            if info is not None:
                out.append(info)
        out.sort(key=lambda j: j.created_ts)
        return out

    def pop_notifications(self, *, max_items: int = 10) -> list[JobResult]:
        out: list[JobResult] = []
        for _ in range(max_items):
            try:
                out.append(self._notifications.get_nowait())
            except queue.Empty:
                break
        return out

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
