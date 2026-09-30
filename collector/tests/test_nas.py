from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import NetworkPoint
from app.sources import nas

METRICS = """
# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{cpu="0",mode="idle"} 90
node_cpu_seconds_total{cpu="0",mode="user"} 10
node_cpu_seconds_total{cpu="1",mode="idle"} 80
node_cpu_seconds_total{cpu="1",mode="system"} 20
node_filesystem_size_bytes{device="md1",mountpoint="/volume1"} 1000
node_filesystem_avail_bytes{device="md1",mountpoint="/volume1"} 800
node_filesystem_size_bytes{device="md2",mountpoint="/volume2"} 1000
node_filesystem_avail_bytes{device="md2",mountpoint="/volume2"} 20
node_hwmon_sensor_label{chip="coretemp",label="Core 0",sensor="temp2"} 1
node_hwmon_sensor_label{chip="coretemp",label="Core 1",sensor="temp3"} 1
node_hwmon_temp_celsius{chip="coretemp",sensor="temp2"} 41
node_hwmon_temp_celsius{chip="coretemp",sensor="temp3"} 47
"""


def test_parse_metrics_reads_labels_and_skips_comments():
    metrics = nas.parse_metrics(METRICS)

    assert len(metrics["node_cpu_seconds_total"]) == 4
    assert metrics["node_cpu_seconds_total"][0] == ({"cpu": "0", "mode": "idle"}, 90.0)
    assert not any(name.startswith("#") for name in metrics)


def test_parse_metrics_skips_nan_and_infinite_values():
    text = (
        'node_hwmon_temp_celsius{chip="acpi",sensor="temp1"} NaN\n'
        'node_hwmon_temp_celsius{chip="coretemp",sensor="temp2"} 41\n'
        'node_scrape_collector_duration_seconds{collector="x"} +Inf\n'
    )

    metrics = nas.parse_metrics(text)

    assert metrics == {"node_hwmon_temp_celsius": [({"chip": "coretemp", "sensor": "temp2"}, 41.0)]}


def test_parse_metrics_handles_unlabelled_samples():
    assert nas.parse_metrics("node_boot_time_seconds 1.7e9") == {
        "node_boot_time_seconds": [({}, 1.7e9)]
    }


def test_cpu_totals_sum_idle_and_all_modes_across_cores():
    assert nas._cpu_totals(nas.parse_metrics(METRICS)) == (170.0, 200.0)


def test_cpu_temp_falls_back_to_hottest_core():
    assert nas._cpu_temp(nas.parse_metrics(METRICS)) == 47.0


def test_cpu_temp_prefers_package_sensor():
    text = METRICS + (
        'node_hwmon_sensor_label{chip="coretemp",label="Package id 0",sensor="temp1"} 1\n'
        'node_hwmon_temp_celsius{chip="coretemp",sensor="temp1"} 44\n'
    )

    assert nas._cpu_temp(nas.parse_metrics(text)) == 44.0


def test_cpu_temp_none_without_sensors():
    assert nas._cpu_temp({}) is None


def _rows(*pairs):
    return [{"date": d, "used_bytes": u} for d, u in pairs]


def test_projection_needs_a_week_of_history():
    rows = _rows(*[(f"2026-09-0{d}", d * 10) for d in range(1, 7)])

    assert nas._projection_months(rows, free_bytes=1000) is None


def test_projection_none_when_usage_is_flat_or_shrinking():
    flat = _rows(("2026-09-01", 100), *[("2026-09-10", 100)] * 7)
    shrinking = _rows(("2026-09-01", 100), *[("2026-09-10", 90)] * 7)

    assert nas._projection_months(flat, free_bytes=50) is None
    assert nas._projection_months(shrinking, free_bytes=50) is None


def test_projection_months_at_mean_daily_growth():
    # 10 bytes/day over 10 days; 3044 free bytes lasts 304.4 days = 10 months.
    rows = _rows(*[(f"2026-09-{d:02d}", d * 10) for d in range(1, 12)])

    assert nas._projection_months(rows, free_bytes=3044) == 10.0


def test_storage_puts_fullest_pool_first_and_skips_missing_mounts(store):
    metrics = nas.parse_metrics(METRICS)

    storage = nas._storage(metrics, ["/volume1", "/volume2", "/volume9"], store, "2026-09-30")

    assert [p.name for p in storage.pools] == ["volume2", "volume1"]
    assert storage.pools[0].used_pct == 98.0
    assert storage.total_bytes == 2000
    assert storage.used_bytes == 1180
    assert [r["used_bytes"] for r in store.storage_history("/volume2")] == [980]


def test_backup_marker_states(tmp_path):
    marker = tmp_path / ".backup_status"
    assert nas._backup(str(marker)).status == "unknown"

    marker.write_text("ok 2026-09-30T03:31:00+02:00\n")
    ok = nas._backup(str(marker))
    assert ok.status == "ok"
    assert ok.at == datetime.fromisoformat("2026-09-30T03:31:00+02:00")

    marker.write_text("fail 2026-09-30T03:31:00+02:00")
    assert nas._backup(str(marker)).status == "fail"

    marker.write_text("weird")
    assert nas._backup(str(marker)).status == "unknown"

    marker.write_text("ok not-a-date")
    assert nas._backup(str(marker)).status == "unknown"


def test_network_history_converts_counters_and_drops_resets():
    t0 = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    rows = [
        {"ts": t0.isoformat(), "rx_bytes": 0, "tx_bytes": 0},
        {
            "ts": (t0 + timedelta(seconds=60)).isoformat(),
            "rx_bytes": 7_500_000,
            "tx_bytes": 750_000,
        },
        # Reboot: counters restart from zero, which must not plot as a spike.
        {"ts": (t0 + timedelta(seconds=120)).isoformat(), "rx_bytes": 10, "tx_bytes": 10},
    ]

    points = nas._network_history(rows)

    assert len(points) == 1
    assert (points[0].rx, points[0].tx) == (1.0, 0.1)


def test_downsample_averages_into_buckets_and_keeps_short_series():
    t = datetime(2026, 9, 30, tzinfo=UTC)
    short = [NetworkPoint(t=t, rx=1, tx=1)] * 3
    assert nas._downsample(short, target=5) == short

    points = [NetworkPoint(t=t + timedelta(minutes=i), rx=i, tx=0) for i in range(10)]
    out = nas._downsample(points, target=5)

    assert [p.rx for p in out] == [0.5, 2.5, 4.5, 6.5, 8.5]
    assert out[-1].t == points[-1].t
