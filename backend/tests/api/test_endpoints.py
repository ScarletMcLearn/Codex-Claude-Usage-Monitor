from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_data_dir):
    from claude_codex_monitor.app import create_app

    app = create_app(enable_lifespan=False)
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_providers(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    names = {p["provider"] for p in r.json()}
    assert names == {"claude", "codex", "antigravity", "free_ai"}


def test_discovery_and_profiles(client):
    r = client.post("/api/discovery/refresh")
    assert r.status_code == 200
    r = client.get("/api/profiles")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_all_and_summary(client):
    client.post("/api/discovery/refresh")
    r = client.post("/api/refresh-all")
    assert r.status_code == 200
    r = client.get("/api/summary")
    assert r.status_code == 200
    body = r.json()
    assert "total_profiles" in body
    assert "generated_at_utc" in body


def test_summary_does_not_fetch_live_usage(client, monkeypatch):
    client.post("/api/discovery/refresh")
    client.post("/api/refresh-all")

    def fail_fetch(_profile):
        raise AssertionError("summary must read persisted snapshots, not probe providers")

    for adapter in client.app.state.discovery_service.adapters.values():
        monkeypatch.setattr(adapter, "fetch_usage", fail_fetch)

    r = client.get("/api/summary")

    assert r.status_code == 200
    assert "total_profiles" in r.json()


def test_usage_report_queries_without_persisting_snapshots(tmp_data_dir, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS", "1")
    from claude_codex_monitor.app import create_app

    app = create_app(enable_lifespan=False)
    client = TestClient(app)
    before = app.state.store.count_snapshots()

    r = client.post("/api/usage-report")

    assert r.status_code == 200
    body = r.json()
    assert body["profiles_checked"] == 5
    assert app.state.store.count_snapshots() == before
    claude_row = next(row for row in body["rows"] if row["provider"] == "claude")
    assert claude_row["source"] == "claude /usage live command"
    assert claude_row["message"] == "Live provider query completed."


def test_settings_get_and_patch(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["theme"] == "system"

    r = client.patch("/api/settings", json={"theme": "dark"})
    assert r.status_code == 200
    assert r.json()["theme"] == "dark"

    r = client.get("/api/settings")
    assert r.json()["theme"] == "dark"


def test_history_range_validation(client):
    r = client.get("/api/history?range=bogus")
    assert r.status_code == 400


def test_history_delete_requires_confirm(client):
    r = client.delete("/api/history")
    assert r.status_code == 400
    r = client.delete("/api/history?confirm=true")
    assert r.status_code == 200


def test_diagnostics_unknown_profile_404(client):
    r = client.get("/api/diagnostics/claude:does-not-exist")
    assert r.status_code == 404


def test_profile_refresh_unknown_profile_404(client):
    r = client.post("/api/profiles/claude:does-not-exist/refresh")
    assert r.status_code == 404
