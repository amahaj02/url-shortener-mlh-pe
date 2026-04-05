from pathlib import Path


REQUIRED_FILES = [
    "k6_write_spike_shared.js",
    "k6_concurrent_spike.js",
    "k6_redis_redirect_cache.js",
]


def test_expected_perf_scripts_exist():
    perf_dir = Path("tests/perf")
    for name in REQUIRED_FILES:
        assert (perf_dir / name).exists(), name


def test_concurrent_spike_wires_shared_defaults():
    perf_dir = Path("tests/perf")
    concurrent = (perf_dir / "k6_concurrent_spike.js").read_text(encoding="utf-8")
    assert "buildWriteSpikeArrivalOptions" in concurrent
    assert 'buildWriteSpikeOptions(50, "2m")' in concurrent

    shared = (perf_dir / "k6_write_spike_shared.js").read_text(encoding="utf-8")
    assert '"X-Request-ID": requestId(' in shared
    assert 'executor: "constant-arrival-rate"' in shared
    assert 'executor: "ramping-vus"' in shared
    assert "p95MsForRamp" in shared
    assert "p95MsForArrival" in shared
    assert "K6_HTTP_P95_MS" in shared

    redis_redirect = (perf_dir / "k6_redis_redirect_cache.js").read_text(encoding="utf-8")
    assert "USE_VU_RAMP" in redis_redirect
    assert 'executor: "ramping-vus"' in redis_redirect
    assert 'executor: "constant-vus"' in redis_redirect
