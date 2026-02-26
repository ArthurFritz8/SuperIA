from omniscia.modules.os_control.filesystem import _safe_rel_subpath


def test_safe_rel_subpath_accepts_leading_slash():
    p = _safe_rel_subpath("/MeuProjeto/MeuProjeto.java")
    assert str(p).replace("\\", "/") == "MeuProjeto/MeuProjeto.java"
