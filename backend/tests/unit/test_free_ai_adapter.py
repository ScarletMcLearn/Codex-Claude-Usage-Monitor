from __future__ import annotations

import json
from pathlib import Path

from claude_codex_monitor.adapters.free_ai_adapter import (
    FreeAIProviderAdapter,
    parse_attempt_line,
    read_dotenv_flags,
    read_usage_samples,
)
from claude_codex_monitor.models.usage import DataQuality


def _write_free_ai_repo(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "artifacts" / "logs").mkdir(parents=True)
    (root / "package.json").write_text('{"name":"free-ai"}', encoding="utf-8")
    (root / ".env.example").write_text("GEMINI_API_KEY=\nGROQ_API_KEY=\n", encoding="utf-8")
    (root / ".env").write_text(
        "GEMINI_API_KEY=secret-gemini\nGROQ_API_KEY=\nCLOUDFLARE_API_TOKEN=secret-token\n",
        encoding="utf-8",
    )
    (root / "config" / "free-providers.json").write_text(
        json.dumps(
            {
                "route": [
                    {
                        "id": "gemini",
                        "label": "Gemini",
                        "model": "gemini-3.6-flash",
                        "credentialEnv": "GEMINI_API_KEY",
                        "free": True,
                        "costUsd": 0,
                    },
                    {
                        "id": "groq",
                        "label": "Groq",
                        "model": "openai/gpt-oss-120b",
                        "credentialEnv": "GROQ_API_KEY",
                        "free": True,
                        "costUsd": 0,
                    },
                    {
                        "id": "cloudflare",
                        "label": "Cloudflare",
                        "model": "@cf/zai-org/glm-4.7-flash",
                        "credentialEnvs": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"],
                        "free": True,
                        "costUsd": 0,
                    },
                    {
                        "id": "paid",
                        "label": "Paid",
                        "model": "paid-model",
                        "credentialEnv": "PAID_API_KEY",
                        "free": False,
                        "costUsd": 1,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def test_discovery_finds_free_ai_repo(tmp_path):
    _write_free_ai_repo(tmp_path)
    adapter = FreeAIProviderAdapter(repo=tmp_path)

    profiles = adapter.discover_profiles()

    assert len(profiles) == 1
    assert profiles[0].provider == "free_ai"
    assert profiles[0].label == "Free-AI"


def test_missing_repo_returns_no_profile(tmp_path):
    adapter = FreeAIProviderAdapter(repo=tmp_path / "missing")

    assert adapter.discover_profiles() == []


def test_dotenv_detects_presence_without_exposing_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=secret\nGROQ_API_KEY=\n", encoding="utf-8")

    flags = read_dotenv_flags(env_file)

    assert flags == {"GEMINI_API_KEY": True, "GROQ_API_KEY": False}
    assert "secret" not in repr(flags)


def test_parse_attempt_line_accepts_success_only():
    assert parse_attempt_line(
        "router provider=gemini model=gemini-3.6-flash attempt=1 status=200 result=success"
    ) == {"provider": "gemini", "model": "gemini-3.6-flash"}
    assert parse_attempt_line(
        "router provider=gemini model=gemini-3.6-flash attempt=1 status=429 result=retryable"
    ) is None
    assert parse_attempt_line("router provider=gemini status=skipped result=configuration") is None


def test_log_parser_counts_successes_and_ignores_failures(tmp_path):
    _write_free_ai_repo(tmp_path)
    log = tmp_path / "artifacts" / "logs" / "free-ai-1.log"
    log.write_text(
        "\n".join(
            [
                "free-ai launch",
                "router provider=gemini model=gemini-3.6-flash attempt=1 status=200 result=success",
                "router provider=gemini model=gemini-3.6-flash attempt=1 status=429 result=retryable",
                "router provider=groq model=openai/gpt-oss-120b attempt=1 status=200 result=success",
                "router provider=gemini model=gemini-3.6-flash attempt=2 status=200 result=success",
                "router provider=groq model=openai/gpt-oss-120b attempt=0 status=skipped result=configuration",
            ]
        ),
        encoding="utf-8",
    )

    samples = read_usage_samples(tmp_path)

    counts = {(sample.provider_id, sample.model): sample.count for sample in samples}
    assert counts == {
        ("gemini", "gemini-3.6-flash"): 2,
        ("groq", "openai/gpt-oss-120b"): 1,
    }


def test_fetch_parse_reports_counts_without_secret_values(tmp_path):
    _write_free_ai_repo(tmp_path)
    (tmp_path / "artifacts" / "logs" / "free-ai-1.log").write_text(
        "router provider=gemini model=gemini-3.6-flash attempt=1 status=200 result=success\n",
        encoding="utf-8",
    )
    adapter = FreeAIProviderAdapter(repo=tmp_path)
    profile = adapter.discover_profiles()[0]

    raw = adapter.fetch_usage(profile)
    limits = adapter.parse_usage(profile, raw)

    assert raw["ok"] is True
    assert limits[0].provider == "free_ai"
    assert limits[0].quality == DataQuality.VERIFIED
    assert limits[0].used_units == 1.0
    assert limits[0].used_percent is None
    assert limits[0].remaining_percent is None
    assert limits[0].source_detail["secret_values_exposed"] is False
    detail_json = json.dumps(limits[0].source_detail)
    assert "secret-gemini" not in detail_json
    assert "secret-token" not in detail_json


def test_no_logs_returns_unavailable_with_configured_metadata(tmp_path):
    _write_free_ai_repo(tmp_path)
    adapter = FreeAIProviderAdapter(repo=tmp_path)
    profile = adapter.discover_profiles()[0]

    limits = adapter.parse_usage(profile, adapter.fetch_usage(profile))

    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert limits[0].unavailable_reason == "No Free-AI router usage logs found yet."
    assert limits[0].source_detail["configured_provider_ids"] == ["gemini"]
    assert limits[0].source_detail["secret_values_exposed"] is False
