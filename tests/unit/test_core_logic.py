"""Unit tests — core business logic, no database or network required."""

from __future__ import annotations

import uuid
from decimal import Decimal

# ---------------------------------------------------------------------------
# Stage controller constants
# ---------------------------------------------------------------------------

VALID_STAGES = [
    "lead_in",
    "qualification",
    "proposal_sent",
    "negotiation",
    "closed_won",
    "closed_lost",
    "onboarding",
    "active",
    "at_risk",
    "churned",
    "reactivation",
]


def test_stage_list_non_empty():
    assert len(VALID_STAGES) > 0


def test_stage_list_has_closed_won():
    assert "closed_won" in VALID_STAGES


def test_stage_list_has_no_duplicates():
    assert len(VALID_STAGES) == len(set(VALID_STAGES))


# ---------------------------------------------------------------------------
# UUID / ID generation
# ---------------------------------------------------------------------------


def test_uuid4_is_unique():
    ids = {uuid.uuid4() for _ in range(1000)}
    assert len(ids) == 1000


def test_uuid_string_roundtrip():
    uid = uuid.uuid4()
    assert uuid.UUID(str(uid)) == uid


# ---------------------------------------------------------------------------
# Revenue math helpers
# ---------------------------------------------------------------------------


def cents_to_dollars(cents: int) -> Decimal:
    return Decimal(cents) / Decimal(100)


def apply_margin(revenue: Decimal, margin_pct: float) -> Decimal:
    return revenue * Decimal(str(margin_pct))


def test_cents_to_dollars_basic():
    assert cents_to_dollars(10000) == Decimal("100.00")


def test_cents_to_dollars_zero():
    assert cents_to_dollars(0) == Decimal("0")


def test_apply_margin_fifty_percent():
    result = apply_margin(Decimal("1000.00"), 0.50)
    assert result == Decimal("500.00")


def test_apply_margin_full():
    result = apply_margin(Decimal("500.00"), 1.0)
    assert result == Decimal("500.00")


# ---------------------------------------------------------------------------
# Proposal line item total
# ---------------------------------------------------------------------------


def compute_total(line_items: list[dict]) -> int:
    """Sum unit_price_cents * quantity for each line item."""
    return sum(item["unit_price_cents"] * item["quantity"] for item in line_items)


def test_compute_total_single_item():
    items = [{"unit_price_cents": 50000, "quantity": 1}]
    assert compute_total(items) == 50000


def test_compute_total_multiple_items():
    items = [
        {"unit_price_cents": 10000, "quantity": 3},
        {"unit_price_cents": 5000, "quantity": 2},
    ]
    assert compute_total(items) == 40000


def test_compute_total_empty():
    assert compute_total([]) == 0


# ---------------------------------------------------------------------------
# GM autonomy threshold logic
# ---------------------------------------------------------------------------


def can_auto_approve(amount_cents: int, auto_limit_cents: int) -> bool:
    return amount_cents <= auto_limit_cents


def test_auto_approve_under_limit():
    assert can_auto_approve(4999, 5000) is True


def test_auto_approve_at_limit():
    assert can_auto_approve(5000, 5000) is True


def test_auto_approve_over_limit():
    assert can_auto_approve(5001, 5000) is False


# ---------------------------------------------------------------------------
# Email reply-to fallback logic
# ---------------------------------------------------------------------------


def resolve_reply_to(reply_to: str | None, fallback: str) -> str:
    return reply_to if reply_to else fallback


def test_resolve_reply_to_provided():
    assert resolve_reply_to("custom@example.com", "fallback@example.com") == "custom@example.com"


def test_resolve_reply_to_none():
    assert resolve_reply_to(None, "reply@reply.proofhook.com") == "reply@reply.proofhook.com"


def test_resolve_reply_to_empty_string():
    assert resolve_reply_to("", "reply@reply.proofhook.com") == "reply@reply.proofhook.com"
