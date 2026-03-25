import time

from omniscia.core.metrics import Metrics


def test_metrics_snapshot_counts_and_timings():
    m = Metrics()
    m.inc("a")
    m.inc("a", 2)

    t = m.timer()
    time.sleep(0.001)
    m.observe_ms("t.ms", t)

    snap = m.snapshot()
    assert snap["counters"]["a"] == 3
    assert "t.ms" in snap["timings_ms"]
    assert snap["timings_ms"]["t.ms"]["count"] >= 1
    assert snap["timings_ms"]["t.ms"]["sum_ms"] > 0
