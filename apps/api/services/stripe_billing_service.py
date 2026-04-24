"""Stripe Billing Service — Handles subscriptions, credit purchases, checkout,
and operator-facing payment processing (payment links, invoices, checkout
sessions, subscription links) for the operator's offers and proposals.
"""

import os
import uuid
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from packages.db.models.monetization import (
    CreditLedger,
    CreditTransaction,
    PackPurchase,
    PlanSubscription,
)

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════
# STRIPE API KEY RESOLUTION
# ══════════════════════════════════════════════════════════════════════


async def _get_stripe_api_key(db: Optional[AsyncSession] = None, org_id: Optional[uuid.UUID] = None) -> str:
    """Resolve Stripe API key: integration_manager DB credential first, then env/settings fallback."""
    # Try integration_manager for org-specific key
    if db and org_id:
        try:
            from apps.api.services.integration_manager import get_credential

            db_key = await get_credential(db, org_id, "stripe")
            if db_key:
                return db_key
        except Exception:
            pass

    # Fall back to settings / env
    settings = get_settings()
    if settings.stripe_api_key:
        return settings.stripe_api_key
    return os.environ.get("STRIPE_API_KEY", "")


def _init_stripe(api_key: str):
    """Set stripe.api_key and return the module."""
    import stripe

    stripe.api_key = api_key
    return stripe


# ══════════════════════════════════════════════════════════════════════
# OPERATOR PAYMENT METHODS — for the operator's offers / proposals
# ══════════════════════════════════════════════════════════════════════


async def create_payment_link(
    amount_cents: int,
    currency: str,
    product_name: str,
    metadata: dict,
    *,
    db: Optional[AsyncSession] = None,
    org_id: Optional[uuid.UUID] = None,
) -> dict:
    """Create a Stripe Payment Link for a one-time payment.

    metadata must include brand_id, offer_id, content_item_id for attribution.
    Returns {url, id} or {error}.
    """
    api_key = await _get_stripe_api_key(db, org_id)
    if not api_key:
        return {"error": "Stripe API key not configured", "url": None, "id": None}

    stripe = _init_stripe(api_key)

    try:
        # Create a one-off product + price, then a payment link
        product = stripe.Product.create(
            name=product_name,
            metadata=metadata,
        )
        price = stripe.Price.create(
            unit_amount=amount_cents,
            currency=currency.lower(),
            product=product.id,
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            metadata=metadata,
        )
        logger.info(
            "stripe.payment_link_created",
            link_id=link.id,
            amount_cents=amount_cents,
            brand_id=metadata.get("brand_id"),
        )
        return {"url": link.url, "id": link.id}
    except Exception as e:
        logger.error("stripe.payment_link_failed", error=str(e))
        return {"error": str(e), "url": None, "id": None}


async def create_invoice(
    customer_email: str,
    line_items: list[dict],
    metadata: dict,
    *,
    db: Optional[AsyncSession] = None,
    org_id: Optional[uuid.UUID] = None,
    days_until_due: int = 30,
) -> dict:
    """Create and send a Stripe Invoice.

    line_items: list of {description, amount_cents, quantity}.
    Returns {invoice_url, invoice_id} or {error}.
    """
    api_key = await _get_stripe_api_key(db, org_id)
    if not api_key:
        return {"error": "Stripe API key not configured", "invoice_url": None, "invoice_id": None}

    stripe = _init_stripe(api_key)

    try:
        # Find or create customer by email
        customers = stripe.Customer.list(email=customer_email, limit=1)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=customer_email,
                metadata=metadata,
            )

        # Create invoice
        invoice = stripe.Invoice.create(
            customer=customer.id,
            collection_method="send_invoice",
            days_until_due=days_until_due,
            metadata=metadata,
        )

        # Add line items
        for item in line_items:
            stripe.InvoiceItem.create(
                customer=customer.id,
                invoice=invoice.id,
                description=item.get("description", "Service"),
                amount=item.get("amount_cents", 0),
                currency=item.get("currency", "usd"),
                quantity=item.get("quantity", 1),
            )

        # Finalize and send
        invoice = stripe.Invoice.finalize_invoice(invoice.id)
        stripe.Invoice.send_invoice(invoice.id)

        logger.info(
            "stripe.invoice_created",
            invoice_id=invoice.id,
            customer_email=customer_email,
            brand_id=metadata.get("brand_id"),
        )
        return {"invoice_url": invoice.hosted_invoice_url, "invoice_id": invoice.id}
    except Exception as e:
        logger.error("stripe.invoice_failed", error=str(e))
        return {"error": str(e), "invoice_url": None, "invoice_id": None}


async def create_checkout_session_for_offer(
    amount_cents: int,
    currency: str,
    product_name: str,
    success_url: str,
    cancel_url: str,
    metadata: dict,
    *,
    db: Optional[AsyncSession] = None,
    org_id: Optional[uuid.UUID] = None,
) -> dict:
    """Create a Stripe Checkout Session for a one-time offer payment.

    Returns {session_url, session_id} or {error}.
    """
    api_key = await _get_stripe_api_key(db, org_id)
    if not api_key:
        return {"error": "Stripe API key not configured", "session_url": None, "session_id": None}

    stripe = _init_stripe(api_key)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {"name": product_name},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
        )
        logger.info(
            "stripe.offer_checkout_created",
            session_id=session.id,
            amount_cents=amount_cents,
            brand_id=metadata.get("brand_id"),
        )
        return {"session_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error("stripe.offer_checkout_failed", error=str(e))
        return {"error": str(e), "session_url": None, "session_id": None}


async def create_subscription_link(
    price_id: str,
    metadata: dict,
    *,
    db: Optional[AsyncSession] = None,
    org_id: Optional[uuid.UUID] = None,
) -> dict:
    """Create a Stripe Payment Link for a recurring subscription price.

    Returns {url} or {error}.
    """
    api_key = await _get_stripe_api_key(db, org_id)
    if not api_key:
        return {"error": "Stripe API key not configured", "url": None}

    stripe = _init_stripe(api_key)

    try:
        link = stripe.PaymentLink.create(
            line_items=[{"price": price_id, "quantity": 1}],
            metadata=metadata,
        )
        logger.info(
            "stripe.subscription_link_created",
            link_id=link.id,
            price_id=price_id,
            brand_id=metadata.get("brand_id"),
        )
        return {"url": link.url}
    except Exception as e:
        logger.error("stripe.subscription_link_failed", error=str(e))
        return {"error": str(e), "url": None}


# ══════════════════════════════════════════════════════════════════════
# OUTREACH PIPELINE HELPER
# ══════════════════════════════════════════════════════════════════════


async def generate_payment_link_for_proposal(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
    offer_id: uuid.UUID,
    amount: float,
    product_name: str,
    *,
    content_item_id: Optional[uuid.UUID] = None,
    currency: str = "usd",
) -> str:
    """Create a Stripe payment link with proper attribution metadata,
    ready for injection into outreach emails / proposals.

    Returns the payment URL, or an error string starting with 'error:'.
    """
    metadata = {
        "brand_id": str(brand_id),
        "offer_id": str(offer_id),
        "org_id": str(org_id),
        "source": "outreach_proposal",
    }
    if content_item_id:
        metadata["content_item_id"] = str(content_item_id)

    amount_cents = int(round(amount * 100))

    result = await create_payment_link(
        amount_cents=amount_cents,
        currency=currency,
        product_name=product_name,
        metadata=metadata,
        db=db,
        org_id=org_id,
    )

    if result.get("error"):
        logger.warning(
            "stripe.proposal_link_failed",
            brand_id=str(brand_id),
            offer_id=str(offer_id),
            error=result["error"],
        )
        return f"error: {result['error']}"

    logger.info(
        "stripe.proposal_link_generated",
        brand_id=str(brand_id),
        offer_id=str(offer_id),
        amount=amount,
        url=result["url"],
    )
    return result["url"]


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
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": pack.name,
                            "description": f"{pack.credits + pack.bonus_credits} credits",
                        },
                        "unit_amount": int(pack.price * 100),
                    },
                    "quantity": 1,
                }
            ],
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

    existing = (
        (
            await db.execute(
                select(PlanSubscription).where(
                    PlanSubscription.organization_id == uuid.UUID(org_id),
                    PlanSubscription.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for e in existing:
        e.status = "superseded"
        e.is_active = False

    monthly_price = (
        plan_config.monthly_price if billing_interval == "monthly" else round(plan_config.annual_price / 12, 2)
    )

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

    ledger = (
        await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == uuid.UUID(org_id),
                CreditLedger.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

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

    db.add(
        CreditTransaction(
            organization_id=uuid.UUID(org_id),
            transaction_type="earn",
            amount=plan_config.included_credits,
            balance_after=ledger.remaining_credits,
            description=f"Plan activation: {plan_config.name}",
        )
    )

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

    db.add(
        PackPurchase(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id) if user_id else uuid.UUID(org_id),
            pack_type="credit_pack",
            pack_id=pack_id,
            pack_name=f"Credit Pack: {credits} credits",
            price=float(event_data.get("amount_total", 0)) / 100.0,
            credits_awarded=credits,
            stripe_payment_id=event_data.get("payment_intent", ""),
            status="completed",
        )
    )

    ledger = (
        await db.execute(
            select(CreditLedger).where(
                CreditLedger.organization_id == uuid.UUID(org_id),
                CreditLedger.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

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

    db.add(
        CreditTransaction(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id) if user_id else None,
            transaction_type="purchase",
            amount=credits,
            balance_after=ledger.remaining_credits,
            reference_id=pack_id,
            description=f"Credit pack purchase: {credits} credits",
        )
    )

    await db.flush()
    logger.info("stripe.credits_purchased", org_id=org_id, credits=credits)


async def handle_subscription_cancelled(db: AsyncSession, event_data: dict):
    """Handle customer.subscription.deleted webhook."""
    stripe_sub_id = event_data.get("id", "")
    if not stripe_sub_id:
        return

    sub = (
        await db.execute(
            select(PlanSubscription).where(
                PlanSubscription.stripe_subscription_id == stripe_sub_id,
            )
        )
    ).scalar_one_or_none()

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

        ledger = (
            await db.execute(
                select(CreditLedger).where(
                    CreditLedger.organization_id == sub.organization_id,
                    CreditLedger.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if ledger:
            ledger.replenishment_rate = free_credits

        await db.flush()
        logger.info("stripe.subscription_cancelled", org_id=str(sub.organization_id))
