from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_fs_list_dir_handler():
    plan = _route("lista o conteudo da pasta ./data")
    assert plan is not None
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "fs.list_dir"


def test_fs_read_text_handler():
    plan = _route("leia o arquivo './README.md'")
    assert plan is not None
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "fs.read_text"


def test_vscode_tasks_read_handler():
    plan = _route("mostre o tasks.json do vscode")
    assert plan is not None
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "vscode.tasks_read"
