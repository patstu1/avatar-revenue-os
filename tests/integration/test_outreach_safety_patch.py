"""Cold-outbound safety patch — minimum-scope tests.

Verifies the three hardenings landed in workers/outreach_worker/tasks.py
without rebuilding the outbound system or adding a new suppression table:

  1. Test/synthetic recipient guard fires BEFORE SMTP send in both
     _send_outreach_email_impl and _send_follow_up_impl.
  2. _send_smtp_email sets the List-Unsubscribe header on every send
     (parity with the API-side SmtpEmailClient).
  3. _send_smtp_email blocks when PROOFHOOK_MAILING_ADDRESS env is unset
     and appends a visible footer (address + opt-out line) when set.
  4. The existing send path (DB-backed SMTP, Reply-To, MIME structure)
     is preserved — the patch is additive only.

These tests do NOT send real email. They patch aiosmtplib.send and
inspect the MIME message that would have been transmitted.
"""

from __future__ import annotations

import os
import uuid
from email import message_from_string

import pytest


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


SMTP_CREDS_OK = {
    "configured": True,
    "host": "smtp.sendgrid.net",
    "port": 587,
    "username": "apikey",
    "password": "SG.fake.test_key_for_unit_test",
    "from_email": "hello@proofhook.com",
    "reply_to": "reply@reply.proofhook.com",
}


class _CapturingSmtpStub:
    """Stub for aiosmtplib.send that captures the outgoing MIMEMultipart
    so tests can assert on its headers and parts without touching SMTP."""

    def __init__(self):
        self.calls: list[dict] = []

    async def __call__(self, msg, **kwargs):
        # Re-parse from string to ensure all headers are emitted as they
        # would be on the wire.
        wire = msg.as_string()
        parsed = message_from_string(wire)
        text_parts = []
        html_parts = []
        if parsed.is_multipart():
            for part in parsed.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    text_parts.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
                elif ct == "text/html":
                    html_parts.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
        self.calls.append(
            {
                "kwargs": kwargs,
                "From": parsed.get("From"),
                "To": parsed.get("To"),
                "Subject": parsed.get("Subject"),
                "Reply-To": parsed.get("Reply-To"),
                "List-Unsubscribe": parsed.get("List-Unsubscribe"),
                "body_text": "\n".join(text_parts),
                "body_html": "\n".join(html_parts),
            }
        )
        return None


# ─────────────────────────────────────────────────────────────────────
# 1. Test/synthetic recipient guard — initial outreach
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outreach_send_blocks_test_email(monkeypatch):
    """An outreach call that resolves to a @b10test.com (or any blocked
    test domain) recipient must return status=blocked, reason
    test_or_synthetic_email, never reach SMTP, and never mark the
    sequence step as sent."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1 Test St, Test City, CA 90028")

    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker import tasks as t

    # Patch the worker's session factory + DB-side selects to return a
    # synthetic outreach + target with a @b10test.com address. We don't
    # need a real DB for this guard test.
    class _FakeSequence:
        id = uuid.uuid4()
        sponsor_target_id = uuid.uuid4()
        confidence = 0.9
        steps = [{"subject": "x", "body": "y", "autonomous_send": True}]

    class _FakeTarget:
        id = uuid.uuid4()
        target_company_name = "B10 Test Co"
        contact_info = {"email": "blocked@b10test.com"}

    class _FakeResult:
        def __init__(self, value):
            self._v = value

        def scalar_one_or_none(self):
            return self._v

    class _FakeSession:
        def __init__(self):
            self._return_seq = True
            self.flushed = False
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def execute(self, _q):
            # Alternate: first execute → sequence, second → target.
            if self._return_seq:
                self._return_seq = False
                return _FakeResult(_FakeSequence())
            return _FakeResult(_FakeTarget())

        def add(self, *a, **k):
            pass

        async def flush(self):
            self.flushed = True

        async def commit(self):
            self.committed = True

    sess = _FakeSession()
    monkeypatch.setattr(t, "get_async_session_factory", lambda: lambda: sess)

    # Stub event_bus.emit_event to avoid hitting the real DB
    async def _noop_emit(*a, **k):
        return None

    from apps.api.services import event_bus

    monkeypatch.setattr(event_bus, "emit_event", _noop_emit)

    result = await t._send_outreach_email_impl(
        outreach_id=str(_FakeSequence.id),
        brand_id=str(uuid.uuid4()),
        org_id=str(uuid.uuid4()),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "test_or_synthetic_email"
    assert result["to_email"] == "blocked@b10test.com"
    # SMTP stub never invoked
    assert smtp_stub.calls == []


# ─────────────────────────────────────────────────────────────────────
# 2. Test/synthetic recipient guard — follow-up
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_follow_up_send_blocks_test_email(monkeypatch):
    """Same guard fires in _send_follow_up_impl. Even if step 0 somehow
    slipped past, every follow-up step re-checks before sending."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1 Test St, Test City, CA 90028")

    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker import tasks as t

    class _FakeSequence:
        id = uuid.uuid4()
        sponsor_target_id = uuid.uuid4()
        steps = [
            {"subject": "x", "body": "y", "status": "sent"},
            {"subject": "follow", "body": "up", "status": None, "delay_days": 7},
        ]

    class _FakeTarget:
        id = uuid.uuid4()
        target_company_name = "Synth Fixture"
        contact_info = {"email": "x@example.com"}

    class _FakeResult:
        def __init__(self, value):
            self._v = value

        def scalar_one_or_none(self):
            return self._v

    class _FakeSession:
        def __init__(self):
            self._return_seq = True
            self.flushed = False
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def execute(self, _q):
            if self._return_seq:
                self._return_seq = False
                return _FakeResult(_FakeSequence())
            return _FakeResult(_FakeTarget())

        def add(self, *a, **k):
            pass

        async def flush(self):
            self.flushed = True

        async def commit(self):
            self.committed = True

    monkeypatch.setattr(t, "get_async_session_factory", lambda: lambda: _FakeSession())

    async def _noop_emit(*a, **k):
        return None

    from apps.api.services import event_bus

    monkeypatch.setattr(event_bus, "emit_event", _noop_emit)

    result = await t._send_follow_up_impl(
        outreach_id=str(_FakeSequence.id),
        sequence_step=1,
        org_id=str(uuid.uuid4()),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "test_or_synthetic_email"
    assert result["to_email"] == "x@example.com"
    assert result["step"] == 1
    assert smtp_stub.calls == []


# ─────────────────────────────────────────────────────────────────────
# 3. _send_smtp_email — List-Unsubscribe + footer + Reply-To preserved
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_smtp_email_sets_list_unsubscribe_header(monkeypatch):
    """Every outreach SMTP send carries List-Unsubscribe: <mailto:from?subject=unsubscribe>
    matching the API-side SmtpEmailClient behavior."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1 Test St, Test City, CA 90028")
    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker.tasks import _send_smtp_email

    result = await _send_smtp_email(
        SMTP_CREDS_OK,
        to_email="real-buyer@example-company.io",
        subject="Test subject",
        body_html="<p>Hello there</p>",
        body_text="Hello there",
    )

    assert result["success"] is True
    assert len(smtp_stub.calls) == 1
    sent = smtp_stub.calls[0]
    assert sent["List-Unsubscribe"] == "<mailto:hello@proofhook.com?subject=unsubscribe>"
    # Reply-To preserved from smtp_creds
    assert sent["Reply-To"] == "reply@reply.proofhook.com"
    # From preserved
    assert sent["From"] == "hello@proofhook.com"


@pytest.mark.asyncio
async def test_send_smtp_email_blocks_when_address_missing(monkeypatch):
    """No PROOFHOOK_MAILING_ADDRESS env set → block before SMTP. Returns
    a structured non-success result. SMTP transport never invoked."""
    monkeypatch.delenv("PROOFHOOK_MAILING_ADDRESS", raising=False)
    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker.tasks import _send_smtp_email

    result = await _send_smtp_email(
        SMTP_CREDS_OK,
        to_email="real-buyer@example-company.io",
        subject="Test subject",
        body_html="<p>Hello there</p>",
        body_text="Hello there",
    )

    assert result["success"] is False
    assert result["blocked"] is True
    assert result["error"] == "missing_physical_mailing_address"
    assert "PROOFHOOK_MAILING_ADDRESS" in result["hint"]
    assert smtp_stub.calls == []


@pytest.mark.asyncio
async def test_send_smtp_email_appends_address_and_unsub_line(monkeypatch):
    """Footer enforcement appends the configured address + visible
    opt-out line to BOTH text and html bodies."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1234 Verified Way, Burbank, CA 91505")
    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker.tasks import _send_smtp_email

    await _send_smtp_email(
        SMTP_CREDS_OK,
        to_email="real-buyer@example-company.io",
        subject="Test subject",
        body_html="<p>Hi there.</p>",
        body_text="Hi there.",
    )

    assert len(smtp_stub.calls) == 1
    sent = smtp_stub.calls[0]

    # Plain-text body carries the footer text + unsubscribe line
    assert "ProofHook" in sent["body_text"]
    assert "1234 Verified Way, Burbank, CA 91505" in sent["body_text"]
    assert "Reply UNSUBSCRIBE to opt out." in sent["body_text"]
    # Original body still present
    assert "Hi there." in sent["body_text"]

    # HTML body carries the footer + unsubscribe line
    assert "1234 Verified Way, Burbank, CA 91505" in sent["body_html"]
    assert "Reply UNSUBSCRIBE to opt out." in sent["body_html"]
    assert "Hi there." in sent["body_html"]


@pytest.mark.asyncio
async def test_send_smtp_email_footer_is_idempotent(monkeypatch):
    """Body that already includes the unsubscribe sentinel is not
    double-stamped — the sentinel acts as the idempotency key."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1 X, Y, Z")
    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker.tasks import _send_smtp_email

    body_with_footer = (
        "Hi there.\n\n--\nProofHook\n1 X, Y, Z\nReply UNSUBSCRIBE to opt out.\n"
    )
    await _send_smtp_email(
        SMTP_CREDS_OK,
        to_email="real-buyer@example-company.io",
        subject="Test subject",
        body_html=body_with_footer,
        body_text=body_with_footer,
    )

    assert len(smtp_stub.calls) == 1
    sent = smtp_stub.calls[0]
    # Sentinel appears exactly once
    assert sent["body_text"].count("Reply UNSUBSCRIBE to opt out.") == 1
    assert sent["body_html"].count("Reply UNSUBSCRIBE to opt out.") == 1


# ─────────────────────────────────────────────────────────────────────
# 4. Existing send path preserved — DB-backed SMTP + Reply-To headers
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_smtp_email_preserves_db_smtp_credentials(monkeypatch):
    """Existing path: when caller passes smtp_creds resolved from DB-backed
    integration_providers (host, port, username, password, from_email,
    reply_to), aiosmtplib.send is invoked with those exact kwargs and the
    Message uses From/Reply-To from creds."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1 X, Y, Z")
    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker.tasks import _send_smtp_email

    creds = {
        "configured": True,
        "host": "smtp.sendgrid.net",
        "port": 587,
        "username": "apikey",
        "password": "SG.fake_password",
        "from_email": "hello@proofhook.com",
        "reply_to": "reply@reply.proofhook.com",
    }
    await _send_smtp_email(
        creds,
        to_email="real-buyer@example-company.io",
        subject="Test subject",
        body_html="<p>Body</p>",
        body_text="Body",
    )

    sent = smtp_stub.calls[0]
    # MIME headers came straight from creds — patch did not change this
    assert sent["From"] == "hello@proofhook.com"
    assert sent["Reply-To"] == "reply@reply.proofhook.com"
    assert sent["To"] == "real-buyer@example-company.io"
    assert sent["Subject"] == "Test subject"
    # Transport kwargs match the credential shape (port 587 → start_tls=True)
    kw = sent["kwargs"]
    assert kw["hostname"] == "smtp.sendgrid.net"
    assert kw["port"] == 587
    assert kw["username"] == "apikey"
    assert kw["password"] == "SG.fake_password"
    # Port 587 is STARTTLS, not direct TLS
    assert kw.get("start_tls") is True
    assert kw.get("use_tls") is not True


@pytest.mark.asyncio
async def test_send_smtp_email_unconfigured_creds_short_circuit(monkeypatch):
    """If smtp_creds.configured is False, return non-success WITHOUT
    touching env or invoking SMTP. Preserves existing fail-fast behavior."""
    monkeypatch.setenv("PROOFHOOK_MAILING_ADDRESS", "1 X, Y, Z")
    smtp_stub = _CapturingSmtpStub()
    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", smtp_stub)

    from workers.outreach_worker.tasks import _send_smtp_email

    creds = {"configured": False}
    result = await _send_smtp_email(
        creds,
        to_email="anybody@example-company.io",
        subject="x",
        body_html="<p>x</p>",
        body_text="x",
    )

    assert result["success"] is False
    assert "SMTP not configured" in result["error"]
    assert smtp_stub.calls == []
