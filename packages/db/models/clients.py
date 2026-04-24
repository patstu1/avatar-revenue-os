"""Client activation + intake objects.

Introduced in Batch 3B. Closes the loop between a successful Payment
and the start of fulfillment by persisting:

    clients                    — the paying B2B customer record
    client_onboarding_events   — audit trail of onboarding transitions
    intake_requests            — a form/questionnaire we ask the client
                                 to complete
    intake_submissions         — the client's submitted responses

Schema is narrow — no speculative fields. All four tables are org-scoped.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base

CLIENT_STATUSES = ["active", "paused", "churned", "archived"]
INTAKE_REQUEST_STATUSES = ["pending", "sent", "viewed", "completed", "expired"]


# ── 1. Client ────────────────────────────────────────────────────────────────


class Client(Base):
    """A paying B2B customer. Created exactly once per (org_id, primary_email)
    when the first successful payment is captured.
    """

    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("org_id", "primary_email", name="uq_clients_org_email"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )

    primary_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), default="")

    # Source attribution
    first_proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )
    first_payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_paid_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Batch 9: avenue attribution carried from the originating payment.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # Batch 11: retention / renewal / reactivation fields.
    # retention_state values: active / renewal_due / renewal_overdue /
    #                        lapsed / churned / expansion_candidate
    retention_state: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    next_renewal_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_retention_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    churn_risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Set to True by client_activation for clients whose source proposal
    # carries a recurring-package slug; keeps the retention scanner
    # scoped only to clients whose business model expects renewal.
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurring_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 2. ClientOnboardingEvent ─────────────────────────────────────────────────


class ClientOnboardingEvent(Base):
    """Per-client audit trail of onboarding transitions. One row per
    meaningful event: onboarding.started, intake.sent, reminder sent,
    intake.completed, etc.
    """

    __tablename__ = "client_onboarding_events"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )
    intake_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_requests.id"), nullable=True, index=True
    )
    intake_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_submissions.id"), nullable=True, index=True
    )

    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(30), default="system")
    actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 3. IntakeRequest ─────────────────────────────────────────────────────────


class IntakeRequest(Base):
    """A form / questionnaire we ask a client to complete during onboarding.

    The ``token`` column is the unguessable URL-safe identifier the client
    uses to access the public form endpoint (no auth required — token IS
    the auth).
    """

    __tablename__ = "intake_requests"
    __table_args__ = (UniqueConstraint("token", name="uq_intake_requests_token"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )

    token: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="")
    schema_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Batch 9: avenue attribution carried from the parent Client.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 4. IntakeSubmission ──────────────────────────────────────────────────────


class IntakeSubmission(Base):
    """A completed submission of an IntakeRequest.

    ``is_complete`` is computed at submit time by comparing the
    responses against the request's required fields (in ``schema_json``).
    Incomplete submissions still persist so the operator can chase the
    missing fields.
    """

    __tablename__ = "intake_submissions"

    intake_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_requests.id"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    responses_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    missing_fields_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    submitted_via: Mapped[str] = mapped_column(String(30), default="form", nullable=False)
    submitter_email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    submitter_ip: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 5. ClientRetentionEvent ──────────────────────────────────────────────────


class ClientRetentionEvent(Base):
    """Audit trail for every retention action (renewal, reactivation,
    upsell, cancellation, state evaluation) on a Client.

    Introduced in Batch 11. Every GM write retention endpoint and the
    scan_retention_states beat task appends a row here so GM's
    retention book reads a canonical history, not scattered
    event_bus emissions.
    """

    __tablename__ = "client_retention_events"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # state_evaluated / renewal_triggered / reactivation_sent /
    # upsell_offered / subscription_cancelled
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    triggered_by_actor_type: Mapped[str] = mapped_column(String(30), default="system", nullable=False)
    triggered_by_actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Linkage to the proposals created when a renew/upsell fires.
    source_proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Batch 12: promoted to first-class so credit/adjustment rollups
    # (SUM amount_cents WHERE event_type='high_ticket.credit_issued') do
    # not require JSONB extraction. NULL for non-financial events.
    amount_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 6. ClientHighTicketProfile ───────────────────────────────────────────────


class ClientHighTicketProfile(Base):
    """High-ticket onboarding state per Client.

    Introduced in Batch 12. Exists only for Clients whose
    ``avenue_slug == 'high_ticket'``. Holds the operational-daily
    fields (discovery_call_at, sow_url, sow_sent_at,
    sow_countersigned_at, counterparty_name, kickoff_at) as first-
    class columns so GM surfaces can filter, sort and aggregate
    them without JSONB extraction. Rare-access context
    (attendees, team members, notes) stays in JSONB.
    """

    __tablename__ = "client_high_ticket_profiles"
    __table_args__ = (UniqueConstraint("client_id", name="uq_htp_client"),)

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        unique=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # status values: discovery_pending / sow_drafted / sow_sent /
    #                sow_signed / kickoff_scheduled / kickoff_complete
    status: Mapped[str] = mapped_column(String(30), default="discovery_pending", nullable=False, index=True)

    discovery_call_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    discovery_attendees_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sow_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    sow_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sow_signer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sow_countersigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    kickoff_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    kickoff_team_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
