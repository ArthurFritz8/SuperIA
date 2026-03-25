from omniscia.core.router_prompt_data import load_schema_hints, load_static_tools_block


def test_load_static_tools_block_is_string():
    txt = load_static_tools_block()
    assert isinstance(txt, str)


def test_load_schema_hints_is_dict():
    d = load_schema_hints()
    assert isinstance(d, dict)
    # If data files are present, it should have at least a few known keys.
    if d:
        assert "core.list_tools" in d
