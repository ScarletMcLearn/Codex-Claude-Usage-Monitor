from __future__ import annotations

import json


def test_forensics_refresh_ingests_jsonl_without_generation(tmp_path, tmp_data_dir, monkeypatch):
    codex_home = tmp_path / "codex_home"
    session_dir = codex_home / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "session.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:00Z",
                        "type": "user_message",
                        "session_id": "s1",
                        "model": "gpt-test",
                        "role": "user",
                        "content": "Read src/foo.py twice",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:01Z",
                        "type": "assistant_message",
                        "session_id": "s1",
                        "model": "gpt-test",
                        "role": "assistant",
                        "content": "Done",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 20,
                            "total_tokens": 120,
                            "cached_tokens": 10,
                            "reasoning_tokens": 5,
                        },
                        "tool": "exec_command",
                        "command": "pytest",
                        "stdout": "ok",
                        "exit_code": 0,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    service = ForensicsService(Store(path=tmp_data_dir / "history.sqlite3"))
    result = service.refresh()
    overview = service.overview()
    detail = service.session_detail("s1")

    assert result["model_generation_requests"] == 0
    assert result["events_processed"] == 2
    assert overview["zero_token_counters"]["monitor_model_generation_requests"] == 0
    assert overview["counts"]["forensic_sessions"] == 1
    assert detail is not None
    assert detail["session"]["total_tokens"] == 120
    assert detail["turns"][1]["token_quality"] == "reported"
    assert detail["commands"][0]["command"] == "pytest"

    second = service.refresh()
    assert second["events_processed"] == 0
    assert service.overview()["counts"]["forensic_raw_events"] == 2


def test_full_export_requires_warning_ack(tmp_path, tmp_data_dir, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty_codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))
    monkeypatch.setenv("CCM_DATA_DIR", str(tmp_data_dir))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    service = ForensicsService(Store(path=tmp_data_dir / "history.sqlite3"))
    try:
        service.export(export_type="full", warning_ack=False)
    except ValueError as exc:
        assert "may contain prompts" in str(exc)
    else:
        raise AssertionError("full export must require warning acknowledgment")

    exported = service.export(export_type="summary", warning_ack=False)
    assert exported["path"].endswith(".zip")


def test_codex_real_shape_fixture_parses_semantics(tmp_path, tmp_data_dir, monkeypatch):
    codex_home = tmp_path / "codex_home"
    session_dir = codex_home / "sessions" / "2026" / "09" / "12"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "rollout-2026-09-12T01-02-03-12345678-1234-1234-1234-123456789abc.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:00Z",
                        "ordinal": 0,
                        "type": "session_meta",
                        "payload": {
                            "id": "12345678-1234-1234-1234-123456789abc",
                            "cwd": str(tmp_path / "repo"),
                            "model_provider": "openai",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:01Z",
                        "ordinal": 1,
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "sanitized user ask"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:02Z",
                        "ordinal": 2,
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "exec_command",
                            "call_id": "call_1",
                            "arguments": {"cmd": "pytest"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:03Z",
                        "ordinal": 3,
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "input_tokens": 10,
                                "output_tokens": 5,
                                "cached_tokens": 2,
                                "reasoning_tokens": 1,
                            },
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    service = ForensicsService(Store(path=tmp_data_dir / "history.sqlite3"))
    result = service.refresh()
    detail = service.session_detail("12345678-1234-1234-1234-123456789abc")

    assert result["model_generation_requests"] == 0
    assert result["events_processed"] == 4
    assert detail is not None
    assert detail["session"]["agent"] == "codex"
    assert detail["session"]["provider"] == "openai"
    assert any(turn["total_tokens"] == 15 for turn in detail["turns"])
    assert detail["tools"][0]["tool_name"] == "exec_command"

    second = service.refresh()
    assert second["events_processed"] == 0


def test_claude_real_shape_fixture_parses_usage_and_tools(tmp_path, tmp_data_dir, monkeypatch):
    claude_home = tmp_path / "claude_home"
    project_dir = claude_home / "projects" / "C--repo"
    project_dir.mkdir(parents=True)
    session_file = project_dir / "claude-session.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "u1",
                        "sessionId": "s-claude",
                        "timestamp": "2026-09-12T00:00:00Z",
                        "cwd": str(tmp_path / "repo"),
                        "gitBranch": "main",
                        "message": {"role": "user", "content": "sanitized request"},
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "a1",
                        "parentUuid": "u1",
                        "sessionId": "s-claude",
                        "requestId": "req1",
                        "timestamp": "2026-09-12T00:00:01Z",
                        "cwd": str(tmp_path / "repo"),
                        "message": {
                            "id": "msg1",
                            "model": "claude-test",
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "sanitized answer"},
                                {"type": "tool_use", "id": "tool1", "name": "Read", "input": {"file_path": "README.md"}},
                            ],
                            "usage": {
                                "input_tokens": 100,
                                "output_tokens": 20,
                                "cache_creation_input_tokens": 7,
                                "cache_read_input_tokens": 3,
                            },
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing_codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    service = ForensicsService(Store(path=tmp_data_dir / "history.sqlite3"))
    result = service.refresh()
    detail = service.session_detail("s-claude")

    assert result["model_generation_requests"] == 0
    assert detail is not None
    assert detail["session"]["agent"] == "claude"
    assert detail["session"]["model"] == "claude-test"
    assert detail["session"]["total_tokens"] == 120
    assert detail["session"]["cached_tokens"] == 3
    assert detail["tools"][0]["tool_name"] == "Read"
    assert any(row["role"] == "assistant" for row in detail["turns"])
