"""Stripe Billing Service — Handles subscriptions, credit purchases, and checkout."""
import uuid
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from packages.db.models.monetization import (
    CreditLedger, CreditTransaction, PlanSubscription, PackPurchase,
)

logger = structlog.get_logger()


async def create_checkout_session(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    plan_tier: str,
    billing_interval: str = "monthly",
    success_url: str = "",
    cancel_url: str = "",
) -> dict:
    """Create a Stripe Checkout session for plan subscription."""
    settings = get_settings()
    if not settings.stripe_api_key:
        return {"error": "Stripe not configured", "checkout_url": None}

    import stripe
    stripe.api_key = settings.stripe_api_key

    price_map = {
        ("starter", "monthly"): settings.stripe_price_starter_monthly,
        ("starter", "annual"): settings.stripe_price_starter_annual,
        ("professional", "monthly"): settings.stripe_price_professional_monthly,
        ("professional", "annual"): settings.stripe_price_professional_annual,
        ("business", "monthly"): settings.stripe_price_business_monthly,
        ("business", "annual"): settings.stripe_price_business_annual,
    }

    price_id = price_map.get((plan_tier, billing_interval))
    if not price_id:
        return {"error": f"No Stripe price configured for {plan_tier}/{billing_interval}", "checkout_url": None}

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url or f"{settings.api_cors_origins[0]}/dashboard/monetization?success=true",
            cancel_url=cancel_url or f"{settings.api_cors_origins[0]}/dashboard/monetization?cancelled=true",
            metadata={
                "organization_id": str(org_id),
                "user_id": str(user_id),
                "plan_tier": plan_tier,
                "billing_interval": billing_interval,
            },
            subscription_data={
                "metadata": {
                    "organization_id": str(org_id),
                    "plan_tier": plan_tier,
                },
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error("stripe.checkout_failed", error=str(e))
        return {"error": str(e), "checkout_url": None}


async def create_credit_purchase_session(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    pack_id: str,
    success_url: str = "",
    cancel_url: str = "",
) -> dict:
    """Create a one-time Stripe Checkout for credit pack purchase."""
    from packages.scoring.monetization_machine import design_pricing_ladder

    settings = get_settings()
    if not settings.stripe_api_key:
        return {"error": "Stripe not configured", "checkout_url": None}

    import stripe
    stripe.api_key = settings.stripe_api_key

    ladder = design_pricing_ladder()
    pack = None
    for p in ladder["credit_packs"].values():
        if p.pack_id == pack_id:
            pack = p
            break

    if not pack:
        return {"error": f"Unknown pack: {pack_id}", "checkout_url": None}

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": pack.name,
                        "description": f"{pack.credits + pack.bonus_credits} credits",
                    },
                    "unit_amount": int(pack.price * 100),
                },
                "quantity": 1,
            }],
            success_url=success_url or f"{settings.api_cors_origins[0]}/dashboard/monetization?credit_success=true",
            cancel_url=cancel_url or f"{settings.api_cors_origins[0]}/dashboard/monetization",
            metadata={
                "organization_id": str(org_id),
                "user_id": str(user_id),
                "pack_id": pack_id,
                "credits": str(pack.credits + pack.bonus_credits),
                "type": "credit_purchase",
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error("stripe.credit_purchase_failed", error=str(e))
        return {"error": str(e), "checkout_url": None}


async def handle_subscription_created(db: AsyncSession, event_data: dict):
    """Process checkout.session.completed for subscriptions."""
    metadata = event_data.get("metadata", {})
    org_id = metadata.get("organization_id")
    plan_tier = metadata.get("plan_tier", "starter")
    billing_interval = metadata.get("billing_interval", "monthly")
    stripe_sub_id = event_data.get("subscription", "")

    if not org_id:
        logger.warning("stripe.subscription.no_org_id")
        return

    from packages.scoring.monetization_machine import design_pricing_ladder
    ladder = design_pricing_ladder()
    plan_config = ladder["plans"].get(plan_tier)
    if not plan_config:
        return

    existing = (await db.execute(
        select(PlanSubscription).where(
            PlanSubscription.organization_id == uuid.UUID(org_id),
            PlanSubscription.is_active.is_(True),
        )
    )).scalars().all()
    for e in existing:
        e.status = "superseded"
        e.is_active = False

    monthly_price = plan_config.monthly_price if billing_interval == "monthly" else round(plan_config.annual_price / 12, 2)

    max_brands_map = {"free": 1, "starter": 1, "professional": 5, "business": 25, "enterprise": -1}

    sub = PlanSubscription(
        organization_id=uuid.UUID(org_id),
        plan_tier=plan_tier,
        plan_name=plan_config.name,
        monthly_price=monthly_price,
        billing_interval=billing_interval,
        included_credits=plan_config.included_credits,
        max_seats=plan_config.max_seats,
        max_brands=max_brands_map.get(plan_tier, 5),
        features_json=plan_config.features,
        meter_limits_json={k: v for k, v in plan_config.meter_limits.items()},
        stripe_subscription_id=stripe_sub_id,
        status="active",
    )
    db.add(sub)

    ledger = (await db.execute(
        select(CreditLedger).where(
            CreditLedger.organization_id == uuid.UUID(org_id),
            CreditLedger.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if ledger:
        ledger.total_credits += plan_config.included_credits
        ledger.remaining_credits += plan_config.included_credits
        ledger.replenishment_rate = plan_config.included_credits
    else:
        ledger = CreditLedger(
            organization_id=uuid.UUID(org_id),
            total_credits=plan_config.included_credits,
            used_credits=0,
            remaining_credits=plan_config.included_credits,
            replenishment_rate=plan_config.included_credits,
        )
        db.add(ledger)

    db.add(CreditTransaction(
        organization_id=uuid.UUID(org_id),
        transaction_type="earn",
        amount=plan_config.included_credits,
        balance_after=ledger.remaining_credits,
        description=f"Plan activation: {plan_config.name}",
    ))

    await db.flush()
    logger.info("stripe.subscription_activated", org_id=org_id, plan=plan_tier)


async def handle_credit_purchase(db: AsyncSession, event_data: dict):
    """Process checkout.session.completed for credit pack purchases."""
    metadata = event_data.get("metadata", {})
    org_id = metadata.get("organization_id")
    user_id = metadata.get("user_id")
    pack_id = metadata.get("pack_id")
    credits = int(metadata.get("credits", 0))

    if not org_id or not credits:
        return

    db.add(PackPurchase(
        organization_id=uuid.UUID(org_id),
        user_id=uuid.UUID(user_id) if user_id else uuid.UUID(org_id),
        pack_type="credit_pack",
        pack_id=pack_id,
        pack_name=f"Credit Pack: {credits} credits",
        price=float(event_data.get("amount_total", 0)) / 100.0,
        credits_awarded=credits,
        stripe_payment_id=event_data.get("payment_intent", ""),
        status="completed",
    ))

    ledger = (await db.execute(
        select(CreditLedger).where(
            CreditLedger.organization_id == uuid.UUID(org_id),
            CreditLedger.is_active.is_(True),
        )
    )).scalar_one_or_none()

    if ledger:
        ledger.total_credits += credits
        ledger.remaining_credits += credits
    else:
        ledger = CreditLedger(
            organization_id=uuid.UUID(org_id),
            total_credits=credits,
            remaining_credits=credits,
        )
        db.add(ledger)

    db.add(CreditTransaction(
        organization_id=uuid.UUID(org_id),
        user_id=uuid.UUID(user_id) if user_id else None,
        transaction_type="purchase",
        amount=credits,
        balance_after=ledger.remaining_credits,
        reference_id=pack_id,
        description=f"Credit pack purchase: {credits} credits",
    ))

    await db.flush()
    logger.info("stripe.credits_purchased", org_id=org_id, credits=credits)


async def handle_subscription_cancelled(db: AsyncSession, event_data: dict):
    """Handle customer.subscription.deleted webhook."""
    stripe_sub_id = event_data.get("id", "")
    if not stripe_sub_id:
        return

    sub = (await db.execute(
        select(PlanSubscription).where(
            PlanSubscription.stripe_subscription_id == stripe_sub_id,
        )
    )).scalar_one_or_none()

    if sub:
        sub.status = "cancelled"
        sub.is_active = False

        from packages.scoring.monetization_machine import design_pricing_ladder
        free_plan = design_pricing_ladder()["plans"].get("free")
        free_credits = free_plan.included_credits if free_plan else 50

        free_sub = PlanSubscription(
            organization_id=sub.organization_id,
            plan_tier="free",
            plan_name="Free",
            monthly_price=0,
            billing_interval="monthly",
            included_credits=free_credits,
            max_seats=1,
            max_brands=1,
            status="active",
        )
        db.add(free_sub)

        ledger = (await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == sub.organization_id,
                CreditLedger.is_active.is_(True),
            )
        )).scalar_one_or_none()
        if ledger:
            ledger.replenishment_rate = free_credits

        await db.flush()
        logger.info("stripe.subscription_cancelled", org_id=str(sub.organization_id))
