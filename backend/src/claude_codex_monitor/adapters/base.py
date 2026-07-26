"""Provider adapter interface. Claude and Codex adapters both implement this."""

from __future__ import annotations

from typing import Any, Protocol

from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus
from ..models.usage import UsageLimit


class ProviderAdapter(Protocol):
    provider_name: str

    def discover_profiles(self) -> list[ProfileStatus]:
        """Enumerate profiles for this provider on the local machine.

        Must not raise for missing/inaccessible files - unreadable candidates
        are simply excluded (with a reason logged), not surfaced as errors.
        """
        ...

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        """Return (is_valid, reason) - cheap, filesystem-only check."""
        ...

    def fetch_usage(self, profile: ProfileStatus) -> Any:
        """Actively fetch raw usage data for one profile (subprocess/DB read).

        Must apply an explicit timeout and never leak env between profiles.
        Returns provider-specific raw payload; never raises for expected
        failure modes (auth required, timeout, no data yet) - instead returns
        a result object/tuple the caller can pass to parse_usage.
        """
        ...

    def parse_usage(self, profile: ProfileStatus, raw: Any) -> list[UsageLimit]:
        """Convert a raw fetch result into normalised UsageLimit rows.

        Never fabricates a value: missing data becomes a DataQuality.UNAVAILABLE
        UsageLimit with a reason, not a UsageLimit with used_percent=0.
        """
        ...

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        """Non-secret account metadata only (e.g. plan type) - never tokens."""
        ...

    def diagnose_error(self, profile: ProfileStatus, error: Exception | str) -> ProfileDiagnostics:
        """Build a sanitized diagnostics record explaining the current state."""
        ...
