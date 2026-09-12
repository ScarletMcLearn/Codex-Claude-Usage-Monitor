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


def test_forensics_api_zero_token_empty_state(tmp_data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty_codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))
    from claude_codex_monitor.app import create_app

    client = TestClient(create_app(enable_lifespan=False))
    r = client.get("/api/forensics/overview")
    assert r.status_code == 200
    assert r.json()["zero_token_counters"]["monitor_model_generation_requests"] == 0

    r = client.post("/api/forensics/refresh")
    assert r.status_code == 200
    assert r.json()["model_generation_requests"] == 0

    r = client.get("/api/forensics/sessions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r = client.post("/api/forensics/export?export_type=full")
    assert r.status_code == 400


def test_forensics_api_session_turn_hotspots_and_export(tmp_data_dir, tmp_path, monkeypatch):
    codex_home = tmp_path / "codex_home"
    session_dir = codex_home / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "session.jsonl").write_text(
        "\n".join(
            [
                '{"timestamp":"2026-09-12T00:00:00Z","type":"user_message","session_id":"s-api","role":"user","content":"ask"}',
                '{"timestamp":"2026-09-12T00:00:01Z","type":"assistant_message","session_id":"s-api","role":"assistant","content":"answer","usage":{"input_tokens":4,"output_tokens":2},"tool":"exec_command","command":"pytest","stdout":"ok","exit_code":0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))
    monkeypatch.setenv("CCM_DATA_DIR", str(tmp_data_dir))
    from claude_codex_monitor.app import create_app

    client = TestClient(create_app(enable_lifespan=False))
    r = client.post("/api/forensics/refresh")
    assert r.status_code == 200
    assert r.json()["model_generation_requests"] == 0

    r = client.get("/api/forensics/sessions/s-api")
    assert r.status_code == 200
    turn_id = r.json()["turns"][1]["turn_id"]

    r = client.get(f"/api/forensics/turns/{turn_id}")
    assert r.status_code == 200
    assert r.json()["turn"]["total_tokens"] == 6
    assert r.json()["raw_events"][0]["raw_json"]

    r = client.get("/api/forensics/hotspots")
    assert r.status_code == 200
    assert r.json()["tools"]

    r = client.post("/api/forensics/export?export_type=full&warning_ack=true")
    assert r.status_code == 200
    assert r.json()["path"].endswith(".zip")
