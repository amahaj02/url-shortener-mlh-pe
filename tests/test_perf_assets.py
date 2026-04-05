from pathlib import Path


REQUIRED_FILES = [
    "k6_50_concurrent_spike.js",
    "k6_200_concurrent_spike.js",
    "k6_500_concurrent_spike.js",
    "k6_1000_concurrent_spike.js",
    "k6_redis_redirect_cache.js",
]


def test_expected_perf_scripts_exist():
    perf_dir = Path("tests/perf")
    for name in REQUIRED_FILES:
        assert (perf_dir / name).exists(), name


def test_new_concurrent_perf_scripts_use_expected_default_vus():
    perf_dir = Path("tests/perf")
    expectations = {
        "k6_200_concurrent_spike.js": "const VUS = Number(__ENV.VUS || 200);",
        "k6_500_concurrent_spike.js": "const VUS = Number(__ENV.VUS || 500);",
        "k6_1000_concurrent_spike.js": "const VUS = Number(__ENV.VUS || 1000);",
    }

    for name, snippet in expectations.items():
        body = (perf_dir / name).read_text(encoding="utf-8")
        assert snippet in body
        assert "\"X-Request-ID\": requestId(" in body
        assert "executor: \"constant-vus\"" in body
