import asyncio


def test_tool_registry_run_async_falls_back_to_thread():
    from omniscia.core.tools import ToolRegistry, ToolSpec
    from omniscia.core.types import ToolResult

    reg = ToolRegistry()

    def fn(args):  # noqa: ANN001
        return ToolResult(status="ok", output=str(args.get("x")))

    reg.register(ToolSpec(name="t.sync", description="", fn=fn))

    out = asyncio.run(reg.run_async("t.sync", {"x": 123}))
    assert out.status == "ok"
    assert out.output == "123"


def test_tool_registry_async_only_tool():
    from omniscia.core.tools import ToolRegistry, ToolSpec
    from omniscia.core.types import ToolResult

    reg = ToolRegistry()

    async def afn(args):  # noqa: ANN001
        await asyncio.sleep(0)
        return ToolResult(status="ok", output="y")

    reg.register(ToolSpec(name="t.async", description="", async_fn=afn))

    # sync run should error
    res_sync = reg.run("t.async", {})
    assert res_sync.status == "error"
    assert "async-only" in (res_sync.error or "")

    res_async = asyncio.run(reg.run_async("t.async", {}))
    assert res_async.status == "ok"
    assert res_async.output == "y"
