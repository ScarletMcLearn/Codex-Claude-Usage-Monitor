from __future__ import annotations

import json
import zipfile


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
                        "timestamp": "2026-09-12T00:00:02.500Z",
                        "ordinal": 4,
                        "type": "event_msg",
                        "payload": {
                            "type": "item_completed",
                            "item": {
                                "type": "UserMessage",
                                "content": [
                                    {"type": "text", "text": "nested rollout user text"}
                                ],
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:02.750Z",
                        "ordinal": 5,
                        "type": "event_msg",
                        "payload": {
                            "type": "item_completed",
                            "item": {
                                "type": "AgentMessage",
                                "content": [
                                    {"type": "text", "text": "nested rollout assistant text"}
                                ],
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-12T00:00:03Z",
                        "ordinal": 6,
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
    assert result["events_processed"] == 6
    assert detail is not None
    assert detail["session"]["agent"] == "codex"
    assert detail["session"]["provider"] == "openai"
    assert detail["session"]["raw_event_count"] == 6
    assert any(turn["total_tokens"] == 15 for turn in detail["turns"])
    assert detail["tools"][0]["tool_name"] == "exec_command"
    message_turn_ids = [
        turn["turn_id"]
        for turn in detail["turns"]
        if turn["user_preview"] or turn["assistant_preview"]
    ]
    messages = [
        message["preview"]
        for turn_id in message_turn_ids
        for message in service.turn_detail(turn_id)["messages"]
    ]
    assert "nested rollout user text" in messages
    assert "nested rollout assistant text" in messages
    token_turn_id = next(turn["turn_id"] for turn in detail["turns"] if turn["total_tokens"] == 15)
    token_messages = [message["preview"] for message in service.turn_detail(token_turn_id)["messages"]]
    assert "nested rollout user text" in token_messages
    assert "nested rollout assistant text" in token_messages

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
    assert detail["file_accesses"][0]["path"] == "README.md"
    assert detail["file_accesses"][0]["access_kind"] == "read"
    assert detail["relationships"][0]["relationship_type"] == "parent_message"
    assert any(row["role"] == "assistant" for row in detail["turns"])


def test_relationship_rollup_is_cycle_safe_and_conservative(tmp_data_dir):
    from claude_codex_monitor.db.store import Store

    store = Store(path=tmp_data_dir / "history.sqlite3")
    store.upsert_forensic_source({
        "source_id": "src",
        "agent": "claude",
        "source_type": "test",
        "source_path": "test",
        "parser_version": "test",
    })
    sessions = [
        {
            "session_id": sid,
            "agent": "claude",
            "provider": "anthropic",
            "source_id": "src",
            "raw_event_count": 1,
            "input_tokens": tokens,
            "output_tokens": 0,
            "total_tokens": tokens,
            "token_quality": "reported",
        }
        for sid, tokens in (("root", 100), ("child-a", 40), ("child-b", 20), ("provenance", 999))
    ]
    relationships = [
        {
            "relationship_id": "r1",
            "source": "test",
            "parent_session_id": "root",
            "child_session_id": "child-a",
            "child_agent": "claude",
            "relationship_type": "sidechain_parent_message",
            "evidence_json": "{}",
            "confidence": "observed",
        },
        {
            "relationship_id": "r1-dupe",
            "source": "test",
            "parent_session_id": "root",
            "child_session_id": "child-a",
            "child_agent": "claude",
            "relationship_type": "sidechain_parent_message",
            "evidence_json": "{}",
            "confidence": "observed",
        },
        {
            "relationship_id": "r2",
            "source": "test",
            "parent_session_id": "child-a",
            "child_session_id": "child-b",
            "child_agent": "claude",
            "relationship_type": "sidechain_parent_message",
            "evidence_json": "{}",
            "confidence": "observed",
        },
        {
            "relationship_id": "cycle",
            "source": "test",
            "parent_session_id": "child-b",
            "child_session_id": "root",
            "child_agent": "claude",
            "relationship_type": "sidechain_parent_message",
            "evidence_json": "{}",
            "confidence": "observed",
        },
        {
            "relationship_id": "self",
            "source": "test",
            "parent_session_id": "root",
            "child_session_id": "root",
            "child_agent": "claude",
            "relationship_type": "sidechain_parent_message",
            "evidence_json": "{}",
            "confidence": "observed",
        },
        {
            "relationship_id": "parent-only",
            "source": "test",
            "parent_session_id": "root",
            "child_session_id": "provenance",
            "child_agent": "claude",
            "relationship_type": "parent_message",
            "evidence_json": "{}",
            "confidence": "observed",
        },
    ]
    store.insert_forensic_rows(
        sessions=sessions,
        turns=[],
        messages=[],
        tools=[],
        commands=[],
        contexts=[],
        raw_events=[],
        relationships=relationships,
    )

    rollup = store.forensic_usage_rollup("root")

    assert rollup["direct_usage"]["total_tokens"] == 100
    assert rollup["descendant_usage"]["total_tokens"] == 60
    assert rollup["inclusive_usage"]["total_tokens"] == 160
    assert rollup["descendant_session_ids"] == ["child-a", "child-b"]
    assert rollup["quality"] == "derived"
    assert rollup["cycles"]
    assert {edge["reason"] for edge in rollup["skipped_edges"]} >= {
        "duplicate_edge",
        "ineligible_relationship_type",
        "self_or_missing_endpoint",
    }


def test_relationship_rollup_preserves_unknown_usage(tmp_data_dir):
    from claude_codex_monitor.db.store import Store

    store = Store(path=tmp_data_dir / "history.sqlite3")
    store.upsert_forensic_source({
        "source_id": "src",
        "agent": "claude",
        "source_type": "test",
        "source_path": "test",
        "parser_version": "test",
    })
    store.insert_forensic_rows(
        sessions=[
            {
                "session_id": "root",
                "agent": "claude",
                "provider": "anthropic",
                "source_id": "src",
                "raw_event_count": 1,
                "token_quality": "unknown",
            },
            {
                "session_id": "child",
                "agent": "claude",
                "provider": "anthropic",
                "source_id": "src",
                "raw_event_count": 1,
                "input_tokens": 7,
                "total_tokens": 7,
                "token_quality": "reported",
            },
        ],
        turns=[],
        messages=[],
        tools=[],
        commands=[],
        contexts=[],
        raw_events=[],
        relationships=[
            {
                "relationship_id": "r1",
                "source": "test",
                "parent_session_id": "root",
                "child_session_id": "child",
                "child_agent": "claude",
                "relationship_type": "sidechain_parent_message",
                "evidence_json": "{}",
                "confidence": "observed",
            }
        ],
    )

    overview = store.forensic_overview()
    rollup = store.forensic_usage_rollup("root")
    exported_agents = store.list_forensic_table("agents")

    assert overview["agents"][0]["total_tokens"] == 7
    assert exported_agents[0]["total_tokens"] == 7
    assert rollup["direct_usage"]["total_tokens"] is None
    assert rollup["descendant_usage"]["total_tokens"] == 7
    assert rollup["inclusive_usage"]["total_tokens"] == 7
    assert rollup["direct_usage"]["output_tokens"] is None
    assert rollup["inclusive_usage"]["output_tokens"] is None


def test_all_unknown_agent_total_remains_unavailable(tmp_data_dir):
    from claude_codex_monitor.db.store import Store

    store = Store(path=tmp_data_dir / "history.sqlite3")
    store.upsert_forensic_source({
        "source_id": "src",
        "agent": "codex",
        "source_type": "test",
        "source_path": "test",
        "parser_version": "test",
    })
    store.insert_forensic_rows(
        sessions=[
            {
                "session_id": "unknown",
                "agent": "codex",
                "provider": "openai",
                "source_id": "src",
                "raw_event_count": 1,
                "token_quality": "unknown",
            }
        ],
        turns=[],
        messages=[],
        tools=[],
        commands=[],
        contexts=[],
        raw_events=[],
    )

    assert store.forensic_overview()["agents"][0]["total_tokens"] is None
    assert store.list_forensic_table("agents")[0]["total_tokens"] is None


def test_collector_checkpoint_resilience_matrix(tmp_path, tmp_data_dir, monkeypatch):
    codex_home = tmp_path / "codex_home"
    session_dir = codex_home / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "session.jsonl"
    event1 = {"timestamp": "2026-09-12T00:00:00Z", "type": "user_message", "session_id": "s1", "content": "a"}
    event2 = {"timestamp": "2026-09-12T00:00:01Z", "type": "assistant_message", "session_id": "s1", "content": "b"}
    session_file.write_text(json.dumps(event1) + "\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    store = Store(path=tmp_data_dir / "history.sqlite3")
    service = ForensicsService(store)

    assert service.refresh()["events_processed"] == 1
    assert service.refresh()["events_processed"] == 0

    with session_file.open("a", encoding="utf-8") as fh:
        fh.write('{"type":"message","pay')
    assert service.refresh()["events_processed"] == 0
    assert service.overview()["counts"]["forensic_raw_events"] == 1

    with session_file.open("a", encoding="utf-8") as fh:
        fh.write('load":{}}\n')
    assert service.refresh()["events_processed"] == 1

    with session_file.open("a", encoding="utf-8") as fh:
        fh.write("{not json}\n")
        fh.write(json.dumps(event2) + "\n")
    result = service.refresh()
    assert result["events_processed"] == 1
    assert result["malformed_events"] == 1

    session_file.write_text(json.dumps(event1) + "\n", encoding="utf-8")
    assert service.refresh()["events_processed"] == 1
    diag = service.source_diagnostics()[0]
    assert diag["checkpoint_reset_count"] >= 1
    assert diag["replacement_detected"] or diag["truncation_detected"]
    assert diag["reset_reason"] in {"replacement_or_rewrite_detected", "truncation_detected"}


def test_duplicate_raw_event_replay_does_not_increment_session_count(tmp_path, tmp_data_dir, monkeypatch):
    codex_home = tmp_path / "codex_home"
    session_dir = codex_home / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "session.jsonl"
    event = {
        "timestamp": "2026-09-12T00:00:00Z",
        "type": "assistant_message",
        "session_id": "s1",
        "content": "answer",
        "usage": {"input_tokens": 3, "output_tokens": 2},
    }
    session_file.write_text(json.dumps(event) + "\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    store = Store(path=tmp_data_dir / "history.sqlite3")
    service = ForensicsService(store)
    assert service.refresh()["events_processed"] == 1

    source = service.source_diagnostics()[0]
    store.update_forensic_source_checkpoint(
        source["source_id"],
        checkpoint_offset=0,
        events_processed=0,
        events_skipped=0,
        malformed_events=0,
    )
    replay = service.refresh()
    detail = service.session_detail("s1")

    assert replay["events_processed"] == 1
    assert service.source_diagnostics()[0]["duplicate_events"] == 1
    assert detail is not None
    assert detail["session"]["raw_event_count"] == 1
    assert service.overview()["counts"]["forensic_raw_events"] == 1


def test_full_export_zip_scope_counts_and_summary_safety(tmp_path, tmp_data_dir, monkeypatch):
    codex_home = tmp_path / "codex_home"
    session_dir = codex_home / "sessions"
    session_dir.mkdir(parents=True)
    (session_dir / "session.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"timestamp": "2026-09-12T00:00:00Z", "type": "user_message", "session_id": "keep", "content": "keep prompt"}),
                json.dumps({"timestamp": "2026-09-12T00:00:01Z", "type": "assistant_message", "session_id": "drop", "content": "drop prompt"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing_claude"))
    monkeypatch.setenv("CCM_FREE_AI_REPO", str(tmp_path / "missing_free_ai"))
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(tmp_path / "missing_antigravity_usage.txt"))
    monkeypatch.setenv("CCM_DATA_DIR", str(tmp_data_dir))

    from claude_codex_monitor.db.store import Store
    from claude_codex_monitor.services.forensics_service import ForensicsService

    service = ForensicsService(Store(path=tmp_data_dir / "history.sqlite3"))
    service.refresh()
    full = service.export(export_type="full", warning_ack=True, filters={"session_id": "keep"})
    summary = service.export(export_type="summary", warning_ack=False, filters={"session_id": "keep"})

    with zipfile.ZipFile(full["path"]) as zf:
        names = set(zf.namelist())
        assert {
            "manifest.json",
            "summary.json",
            "sessions.jsonl",
            "turns.jsonl",
            "messages.jsonl",
            "tools.jsonl",
            "commands.jsonl",
            "context-blocks.jsonl",
            "file-accesses.jsonl",
            "relationships.jsonl",
            "raw-events.jsonl",
            "report.md",
        } <= names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["scope"]["session_ids"] == ["keep"]
        sessions = [json.loads(line) for line in zf.read("sessions.jsonl").decode().splitlines()]
        assert [row["session_id"] for row in sessions] == ["keep"]
        assert manifest["record_counts"]["sessions"] == len(sessions)
        assert all(row["session_id"] == "keep" for row in [json.loads(line) for line in zf.read("raw-events.jsonl").decode().splitlines()])

    with zipfile.ZipFile(summary["path"]) as zf:
        assert "raw-events.jsonl" not in set(zf.namelist())
        assert "messages.jsonl" not in set(zf.namelist())


def test_structural_revalidation_reports_counts_hashes_only(tmp_path):
    telemetry = tmp_path / "telemetry"
    telemetry.mkdir()
    (telemetry / "session.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "s1",
                "uuid": "a1",
                "parentUuid": "u1",
                "isSidechain": True,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "secret.py"}}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from claude_codex_monitor.services.telemetry_revalidation import revalidate_jsonl_roots

    result = revalidate_jsonl_roots([telemetry])

    assert result["model_generation_requests"] == 0
    assert result["file_count"] == 1
    assert result["event_count"] == 1
    assert result["tool_count"] == 1
    assert result["relationship_count"] == 1
    assert result["token_field_presence_counts"] == {"input_tokens": 1, "output_tokens": 1}
    dumped = json.dumps(result)
    assert "secret.py" not in dumped
