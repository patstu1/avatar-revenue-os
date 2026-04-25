"""Unit tests for test_record_guard — live-payment safety guardrail.

Pure-function tests; no DB, no network, no fixtures required.
Run with: pytest tests/test_test_record_guard_unit.py -v
"""

import pytest

from apps.api.services.test_record_guard import (
    is_test_or_synthetic_email,
    is_test_or_synthetic_record,
    is_test_or_synthetic_text,
)


# ─────────────────────────────────────────────────────────────────────────────
# is_test_or_synthetic_email
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailGuard:
    # Blocked — domain patterns
    @pytest.mark.parametrize("email", [
        "user@test.com",
        "ops@internal.test",
        "hello@example.com",
        "anyone@localhost",
        "alpha@b10test.com",   # batch-10 test domain
        "x@sub.test",
        "x@sub.example",
        "x@sub.invalid",
        "x@sub.localhost",
        # Case variants
        "User@TEST.COM",
        "OPS@INTERNAL.TEST",
    ])
    def test_blocked_domain(self, email):
        assert is_test_or_synthetic_email(email) is True

    # Blocked — marker in local-part
    @pytest.mark.parametrize("email", [
        "testreplier@realbrand.com",
        "synth_user@realbrand.com",
        "synthetic.client@agency.io",
        "fixture_lead@brand.co",
        "proof_test@proofhook.com",
        "b11_client@company.com",
        "b12@company.com",
        "batch_fixture@company.com",
        "demo_client@company.com",
        "democlient@company.com",
    ])
    def test_blocked_marker_in_local(self, email):
        assert is_test_or_synthetic_email(email) is True

    # Blocked — empty / None
    @pytest.mark.parametrize("email", [
        "",
        None,
        "   ",
    ])
    def test_blocked_empty(self, email):
        assert is_test_or_synthetic_email(email) is True  # type: ignore[arg-type]

    # Allowed — real emails
    @pytest.mark.parametrize("email", [
        "founder@realbrand.com",
        "client@realagency.io",
        "sarah.jones@gmail.com",
        "ops@proofhook.com",
        "contact@company.co.uk",
        "hello@startup.ai",
        # "demo" alone in domain is NOT a blocker (only demo_client/demo_fixture)
        "user@demobrand.com",
        "info@brandemo.com",
    ])
    def test_allowed_real_email(self, email):
        assert is_test_or_synthetic_email(email) is False


# ─────────────────────────────────────────────────────────────────────────────
# is_test_or_synthetic_text
# ─────────────────────────────────────────────────────────────────────────────

class TestTextGuard:
    @pytest.mark.parametrize("value", [
        "synth",
        "synthetic_retainer",
        "proof_test",
        "b11",
        "b12",
        "fixture",
        "batch_fixture",
        "testreplier",
        "SYNTHETIC",   # case-insensitive
    ])
    def test_blocked_text(self, value):
        assert is_test_or_synthetic_text(value) is True

    @pytest.mark.parametrize("value", [
        "real_retainer",
        "momentum_engine",
        "b2b_retainer_monthly",
        "ugc_monthly",
        "",
        None,
    ])
    def test_allowed_text(self, value):
        assert is_test_or_synthetic_text(value) is False  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# is_test_or_synthetic_record
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordGuard:
    def test_blocked_by_email(self):
        blocked, reason = is_test_or_synthetic_record(
            email="user@test.com",
            source="retainer_renewal",
            metadata={"client_id": "abc-123"},
        )
        assert blocked is True
        assert "email" in reason

    def test_blocked_by_source(self):
        blocked, reason = is_test_or_synthetic_record(
            email="founder@realbrand.com",
            source="b11_retainer",
            metadata=None,
        )
        assert blocked is True
        assert "source" in reason

    def test_blocked_by_metadata_value(self):
        blocked, reason = is_test_or_synthetic_record(
            email="founder@realbrand.com",
            source="retainer_renewal",
            metadata={"batch": "b12_fixture"},
        )
        assert blocked is True
        assert "metadata" in reason

    def test_allowed_real_record(self):
        blocked, reason = is_test_or_synthetic_record(
            email="sarah@realbrand.com",
            source="retainer_renewal",
            metadata={"client_id": "real-uuid-here", "org": "production"},
        )
        assert blocked is False
        assert reason == ""

    def test_none_source_and_metadata_allowed(self):
        blocked, _ = is_test_or_synthetic_record(
            email="ops@proofhook.com",
            source=None,
            metadata=None,
        )
        assert blocked is False

    def test_empty_email_always_blocked(self):
        blocked, _ = is_test_or_synthetic_record(email="")
        assert blocked is True
