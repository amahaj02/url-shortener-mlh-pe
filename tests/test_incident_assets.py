from pathlib import Path


def test_monitoring_assets_exist_and_contain_core_identifiers():
    monitoring_file = Path("config/monitoring/url-shortener-monitoring.yml")
    dashboard_file = Path("config/monitoring/grafana-dashboard-url-shortener.json")
    runbook_file = Path("docs/quests/incident-response/RUNBOOK.md")

    assert monitoring_file.exists()
    assert dashboard_file.exists()
    assert runbook_file.exists()

    monitoring = monitoring_file.read_text(encoding="utf-8")
    dashboard = dashboard_file.read_text(encoding="utf-8")
    runbook = runbook_file.read_text(encoding="utf-8")

    assert "UrlShortenerServiceDown" in monitoring
    assert "UrlShortenerHighErrorRate" in monitoring
    assert "UrlShortenerHighCpuUsage" in monitoring
    assert "URL Shortener Command Center" in dashboard
    assert "Latency" in dashboard
    assert "Traffic" in dashboard
    assert "Error" in dashboard
    assert "Saturation" in dashboard
    assert "Runbook" in runbook or "This runbook" in runbook
