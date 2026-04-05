from pathlib import Path


REQUIRED_FILES = [
    "k6_write_spike_shared.js",
    "k6_50_concurrent_spike.js",
    "k6_200_concurrent_spike.js",
    "k6_500_concurrent_spike.js",
    "k6_1000_concurrent_spike.js",
    "k6_smoke_write.js",
    "k6_redis_redirect_cache.js",
]


def test_expected_perf_scripts_exist():
    perf_dir = Path("tests/perf")
    for name in REQUIRED_FILES:
        assert (perf_dir / name).exists(), name


def test_new_concurrent_perf_scripts_use_expected_default_vus():
    perf_dir = Path("tests/perf")
    expectations = {
        "k6_50_concurrent_spike.js": 'buildWriteSpikeOptions(50, "5m")',
        "k6_200_concurrent_spike.js": 'buildWriteSpikeOptions(200, "5m")',
        "k6_500_concurrent_spike.js": 'buildWriteSpikeOptions(500, "5m")',
        "k6_1000_concurrent_spike.js": 'buildWriteSpikeOptions(1000, "5m")',
    }

    for name, snippet in expectations.items():
        body = (perf_dir / name).read_text(encoding="utf-8")
        assert snippet in body

    shared = (perf_dir / "k6_write_spike_shared.js").read_text(encoding="utf-8")
    assert '"X-Request-ID": requestId(' in shared
    assert 'executor: "constant-vus"' in shared
