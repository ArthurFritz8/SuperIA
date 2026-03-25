import time


def test_run_tool_with_retry_async_ok(monkeypatch):
    from omniscia.core.config import Settings
    from omniscia.core.types import ToolCall, ToolResult
    from omniscia.modules.memory.store import JsonlMemoryStore
    from omniscia.core.brain import _run_tool_with_retry_async

    class DummyRegistry:
        def __init__(self):
            self.calls = []

        def run(self, name, args):  # noqa: ANN001
            self.calls.append((name, dict(args or {})))
            return ToolResult(status="ok", output="x")

    settings = Settings(retry_max_attempts=2, retry_backoff_s=0.0)
    reg = DummyRegistry()
    memory = JsonlMemoryStore()

    call = ToolCall(tool_name="core.echo", args={"text": "hi"})

    # run
    import asyncio

    res = asyncio.run(_run_tool_with_retry_async(None, settings, reg, call, memory))  # type: ignore[arg-type]
    assert res.status == "ok"
    assert len(reg.calls) == 1

    # memory should have tool_output
    events = memory.recent(limit=5)
    assert any(e.kind == "tool_output" and e.payload.get("tool") == "core.echo" for e in events)


def test_run_tool_with_retry_async_retries(monkeypatch):
    from omniscia.core.config import Settings
    from omniscia.core.types import ToolCall, ToolResult
    from omniscia.modules.memory.store import JsonlMemoryStore
    from omniscia.core.brain import _run_tool_with_retry_async

    class DummyConsole:
        def __init__(self):
            self.lines = []

        def print(self, msg):  # noqa: ANN001
            self.lines.append(str(msg))

    class DummyRegistry:
        def __init__(self):
            self.n = 0

        def run(self, name, args):  # noqa: ANN001
            self.n += 1
            if self.n < 2:
                return ToolResult(status="error", error="timeout")
            return ToolResult(status="ok", output="ok")

    settings = Settings(retry_max_attempts=2, retry_backoff_s=0.0)
    reg = DummyRegistry()
    memory = JsonlMemoryStore()
    console = DummyConsole()

    call = ToolCall(tool_name="core.echo", args={"text": "hi"})

    import asyncio

    t0 = time.time()
    res = asyncio.run(_run_tool_with_retry_async(console, settings, reg, call, memory))
    assert res.status == "ok"
    assert reg.n == 2
    assert (time.time() - t0) < 1.0
    assert any("Tool falhou" in ln for ln in console.lines)
