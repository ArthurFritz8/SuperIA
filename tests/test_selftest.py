from omniscia.core.selftest import run_selftest


def test_selftest_offline_ok():
    ok, report = run_selftest()
    assert isinstance(report, str)
    assert "selftest" in report
    assert ok is True
