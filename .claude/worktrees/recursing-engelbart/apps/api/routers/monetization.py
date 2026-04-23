"""Monetization Machine API — Credits, plans, packs, telemetry, and upgrade triggers."""
import uuid
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from apps.api.deps import CurrentUser, DBSession
from apps.api.services import monetization_service as ms
from apps.api.services import stripe_billing_service as sbs

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SpendCreditsRequest(BaseModel):
    amount: int = Field(0, ge=0, description="Credits to spend (0 = auto from meter cost)")
    meter_type: str = Field(..., description="What the credits are spent on")
    reference_id: Optional[str] = None
    description: Optional[str] = None


class PurchaseCreditsRequest(BaseModel):
    pack_id: str = Field(..., description="ID of the pack to purchase")
    payment_id: Optional[str] = Field(None, description="Stripe payment intent ID")


class SubscribeRequest(BaseModel):
    plan_tier: str = Field(..., description="Plan tier: starter, professional, or business")
    billing_interval: str = Field("monthly", description="monthly or annual")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class PurchasePackRequest(BaseModel):
    pack_id: str = Field(..., description="Credit pack ID to purchase")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class TelemetryRequest(BaseModel):
    event_name: str
    event_value: float = 0.0
    properties: Optional[dict] = None
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Credit endpoints
# ---------------------------------------------------------------------------

@router.get("/credits/balance")
async def get_credit_balance(
    current_user: CurrentUser,
    db: DBSession,
):
    """Current credit balance for the user's organization."""
    return await ms.get_credit_balance(db, current_user.organization_id)


@router.post("/credits/spend")
async def spend_credits(
    body: SpendCreditsRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Spend credits on an action."""
    return await ms.spend_credits(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        amount=body.amount,
        meter_type=body.meter_type,
        reference_id=body.reference_id,
        description=body.description,
    )


@router.post("/credits/purchase")
async def purchase_credits(
    body: PurchaseCreditsRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Buy a credit pack."""
    return await ms.purchase_credits(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        pack_id=body.pack_id,
        payment_id=body.payment_id,
    )


# ---------------------------------------------------------------------------
# Usage & plan endpoints
# ---------------------------------------------------------------------------

@router.get("/usage")
async def get_usage(
    current_user: CurrentUser,
    db: DBSession,
):
    """Current period usage across all meters."""
    return await ms.get_usage_summary(db, current_user.organization_id)


@router.get("/plan")
async def get_plan(
    current_user: CurrentUser,
    db: DBSession,
):
    """Current plan details with limits."""
    return await ms.get_plan_details(db, current_user.organization_id)


@router.get("/pricing")
async def get_pricing():
    """Full pricing ladder."""
    return ms.get_pricing_ladder()


@router.get("/packs")
async def get_packs():
    """Available outcome and credit packs."""
    return ms.get_outcome_packs()


# ---------------------------------------------------------------------------
# Ascension & multiplication
# ---------------------------------------------------------------------------

@router.get("/ascension")
async def get_ascension(
    current_user: CurrentUser,
    db: DBSession,
):
    """User's ascension profile and upgrade triggers."""
    return await ms.get_ascension_profile(db, current_user.organization_id, current_user.id)


@router.get("/multiplication-opportunities")
async def get_multiplication_opportunities(
    current_user: CurrentUser,
    db: DBSession,
    current_action: Optional[str] = Query(None, description="Current action context for targeting"),
):
    """Real-time upsell opportunities."""
    return await ms.get_multiplication_opportunities(
        db, current_user.organization_id, current_user.id, current_action
    )


# ---------------------------------------------------------------------------
# Health & telemetry
# ---------------------------------------------------------------------------

@router.get("/health")
async def get_health(
    current_user: CurrentUser,
    db: DBSession,
):
    """Monetization machine health report."""
    return await ms.get_monetization_health(db, current_user.organization_id)


@router.post("/telemetry")
async def record_telemetry(
    body: TelemetryRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Record a monetization telemetry event."""
    return await ms.record_telemetry(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        event_name=body.event_name,
        event_value=body.event_value,
        properties=body.properties,
        session_id=body.session_id,
    )


# ---------------------------------------------------------------------------
# Stripe Billing
# ---------------------------------------------------------------------------

@router.post("/subscribe")
async def subscribe(
    body: SubscribeRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Create a Stripe Checkout session for plan subscription."""
    return await sbs.create_checkout_session(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        plan_tier=body.plan_tier,
        billing_interval=body.billing_interval,
        success_url=body.success_url or "",
        cancel_url=body.cancel_url or "",
    )


@router.post("/purchase-pack")
async def purchase_pack(
    body: PurchasePackRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Create a Stripe Checkout session for credit pack purchase."""
    return await sbs.create_credit_purchase_session(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        pack_id=body.pack_id,
        success_url=body.success_url or "",
        cancel_url=body.cancel_url or "",
    )
