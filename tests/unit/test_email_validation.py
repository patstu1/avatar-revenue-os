"""Email validation tests for the AI Buyer Trust Test."""

import pytest

from apps.api.services.email_validation import (
    EmailValidationError,
    validate_contact_email,
)


class TestAccept:
    @pytest.mark.parametrize(
        "email",
        [
            "pat@acme.com",
            "Pat.Jones+leads@sub.acme.io",
            "ceo@startup.ai",
        ],
    )
    def test_accepts_real_emails_lowercased(self, email):
        normalized = validate_contact_email(email)
        assert normalized == email.lower()


class TestReject:
    @pytest.mark.parametrize(
        "email",
        [
            "",
            None,
            "not-an-email",
            "two@@ats.com",
            "@nodomain.com",
            "missing@.com",
            "missing@tld",
        ],
    )
    def test_rejects_malformed(self, email):
        with pytest.raises(EmailValidationError):
            validate_contact_email(email)

    @pytest.mark.parametrize(
        "email",
        [
            "test@example.com",
            "anyone@example.net",
            "x@example.org",
            "user@test.com",
            "throwaway@mailinator.com",
            "tmp@throwaway.email",
            "burn@10minutemail.com",
            "u@yopmail.com",
        ],
    )
    def test_rejects_throwaway_and_example_domains(self, email):
        with pytest.raises(EmailValidationError):
            validate_contact_email(email)

    @pytest.mark.parametrize(
        "email",
        [
            "noreply@acme.com",
            "no-reply@acme.com",
            "donotreply@acme.com",
            "test@acme.com",
            "postmaster@acme.com",
        ],
    )
    def test_rejects_blocked_local_parts(self, email):
        with pytest.raises(EmailValidationError):
            validate_contact_email(email)
