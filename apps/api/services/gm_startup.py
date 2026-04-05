"""GM Startup Service — Machine state scanning, blueprint generation, execution.

This is the strategic operating brain. It scans the full machine state,
generates launch blueprints via Claude, revises interactively, and
executes approved plans by creating real entities in the database.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, Organization
from packages.db.models.accounts import CreatorAccount
from packages.db.models.offers import Offer
from packages.db.models.content import ContentBrief
from packages.db.models.revenue_ledger import RevenueLedgerEntry
from packages.db.models.gm import GMSession, GMMessage, GMBlueprint
from apps.api.services.gm_system_prompt import (
    GM_STARTUP_PROMPT,
    GM_REVISION_PROMPT,
    GM_CONVERSATION_PROMPT,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Machine State Scanner
# ---------------------------------------------------------------------------

async def get_machine_state(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> dict[str, Any]:
    """Portfolio-level machine state scan. The GM's eyes."""

    # --- Providers ---
    providers_configured = 0
    provider_list: list[dict] = []
    try:
        from apps.api.services import secrets_service
        db_keys = await secrets_service.get_all_keys(db, org_id)
        providers_from_db = {k: v for k, v in db_keys.items() if v}

        critical_env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google_ai": "GOOGLE_AI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "elevenlabs": "ELEVENLABS_API_KEY",
            "heygen": "HEYGEN_API_KEY",
            "buffer": "BUFFER_API_KEY",
            "stripe": "STRIPE_API_KEY",
            "fal": "FAL_API_KEY",
            "runway": "RUNWAY_API_KEY",
        }
        for key, env_name in critical_env.items():
            source = "none"
            if key in providers_from_db:
                source = "dashboard"
            elif os.environ.get(env_name, ""):
                source = "server"
            if source != "none":
                providers_configured += 1
                provider_list.append({"key": key, "source": source})
    except Exception:
        pass

    # --- Brands ---
    brand_result = await db.execute(
        select(Brand).where(
            Brand.organization_id == org_id,
            Brand.is_active == True,  # noqa: E712
        ).order_by(Brand.created_at)
    )
    brands = brand_result.scalars().all()
    brand_count = len(brands)
    brand_details = [
        {"id": str(b.id), "name": b.name, "niche": b.niche, "slug": b.slug}
        for b in brands
    ]

    # --- Accounts ---
    account_count = 0
    accounts_by_platform: dict[str, int] = {}
    account_details: list[dict] = []
    if brand_count > 0:
        brand_ids = [b.id for b in brands]
        acct_result = await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id.in_(brand_ids),
                CreatorAccount.is_active == True,  # noqa: E712
            )
        )
        accounts = acct_result.scalars().all()
        account_count = len(accounts)
        for a in accounts:
            plat = a.platform.value if hasattr(a.platform, 'value') else str(a.platform)
            accounts_by_platform[plat] = accounts_by_platform.get(plat, 0) + 1
            account_details.append({
                "id": str(a.id),
                "platform": plat,
                "username": a.platform_username,
                "followers": a.follower_count,
                "revenue": float(a.total_revenue or 0),
                "credential_status": a.credential_status,
                "scale_role": a.scale_role,
            })

    # --- Offers ---
    offer_count = 0
    offer_details: list[dict] = []
    if brand_count > 0:
        offer_result = await db.execute(
            select(Offer).where(
                Offer.brand_id.in_(brand_ids),
                Offer.is_active == True,  # noqa: E712
            )
        )
        offers = offer_result.scalars().all()
        offer_count = len(offers)
        for o in offers:
            offer_details.append({
                "id": str(o.id),
                "name": o.name,
                "method": o.monetization_method.value if hasattr(o.monetization_method, 'value') else str(o.monetization_method),
                "payout": float(o.payout_amount or 0),
            })

    # --- Content ---
    content_count = 0
    if brand_count > 0:
        content_result = await db.execute(
            select(func.count()).select_from(ContentBrief).where(
                ContentBrief.brand_id.in_(brand_ids),
            )
        )
        content_count = content_result.scalar() or 0

    # --- Revenue (90 days) ---
    total_revenue = 0.0
    revenue_by_source: dict[str, float] = {}
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        rev_result = await db.execute(
            select(
                RevenueLedgerEntry.revenue_type,
                func.sum(RevenueLedgerEntry.amount_usd),
            ).where(
                RevenueLedgerEntry.organization_id == org_id,
                RevenueLedgerEntry.event_date >= cutoff,
            ).group_by(RevenueLedgerEntry.revenue_type)
        )
        for row in rev_result.fetchall():
            rtype = row[0] if isinstance(row[0], str) else str(row[0])
            amount = float(row[1] or 0)
            revenue_by_source[rtype] = amount
            total_revenue += amount
    except Exception:
        pass

    # --- Publishing connected? ---
    has_publishing = bool(os.environ.get("BUFFER_API_KEY", ""))
    if not has_publishing:
        try:
            has_publishing = bool(db_keys.get("buffer", ""))
        except Exception:
            pass

    # --- Determine machine phase ---
    if providers_configured == 0 and brand_count == 0:
        machine_phase = "pre_ignition"
    elif providers_configured > 0 and brand_count == 0:
        machine_phase = "configuring"
    elif brand_count > 0 and account_count == 0:
        machine_phase = "configuring"
    elif account_count > 0 and content_count == 0:
        machine_phase = "first_launch"
    elif content_count > 0 and total_revenue == 0:
        machine_phase = "warmup"
    elif total_revenue > 0 and total_revenue < 1000:
        machine_phase = "scaling"
    else:
        machine_phase = "portfolio_compounding"

    # --- Readiness score ---
    readiness = 0
    if providers_configured > 0:
        readiness += 20
    if brand_count > 0:
        readiness += 20
    if account_count > 0:
        readiness += 20
    if offer_count > 0:
        readiness += 15
    if has_publishing:
        readiness += 15
    if content_count > 0:
        readiness += 10

    return {
        "machine_phase": machine_phase,
        "readiness_score": readiness,
        "providers": {
            "configured": providers_configured,
            "list": provider_list,
            "has_llm": any(p["key"] in ("anthropic", "openai", "google_ai", "deepseek") for p in provider_list),
            "has_publishing": has_publishing,
            "has_video": any(p["key"] in ("heygen", "runway", "fal") for p in provider_list),
            "has_voice": any(p["key"] in ("elevenlabs",) for p in provider_list),
            "has_payments": any(p["key"] in ("stripe",) for p in provider_list),
        },
        "brands": {"count": brand_count, "details": brand_details},
        "accounts": {
            "count": account_count,
            "by_platform": accounts_by_platform,
            "details": account_details[:50],
        },
        "offers": {"count": offer_count, "details": offer_details[:30]},
        "content": {"count": content_count},
        "revenue": {
            "total_90d": total_revenue,
            "by_source": revenue_by_source,
        },
    }


# ---------------------------------------------------------------------------
# Blueprint Generation (calls Claude)
# ---------------------------------------------------------------------------

async def generate_launch_blueprint(
    db: AsyncSession,
    org_id: uuid.UUID,
    machine_state: dict[str, Any],
    operator_context: str = "",
) -> dict[str, Any]:
    """Generate a full launch blueprint using Claude with GM doctrine.

    Returns the raw Claude response text + parsed blueprint sections.
    """
    context_block = f"""
## MACHINE STATE
{json.dumps(machine_state, indent=2, default=str)}

## OPERATOR CONTEXT
{operator_context or "No additional operator context provided yet. Generate the best initial blueprint based on machine state alone."}
"""

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            from apps.api.services import secrets_service
            db_keys = await secrets_service.get_all_keys(db, org_id)
            api_key = db_keys.get("anthropic", "")

        if not api_key:
            return {
                "success": False,
                "error": "No Anthropic API key configured",
                "content": "I need an Anthropic API key to generate the launch blueprint. Please configure it in Settings → API Keys.",
                "blueprint": None,
            }

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=GM_STARTUP_PROMPT,
            messages=[
                {"role": "user", "content": f"Here is the current machine state. Generate the full launch blueprint.\n\n{context_block}"}
            ],
        )

        content = response.content[0].text
        blueprint_data = _parse_blueprint_sections(content)

        return {
            "success": True,
            "content": content,
            "blueprint": blueprint_data,
            "model": "claude-sonnet-4-20250514",
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
    except Exception as e:
        logger.error("gm.blueprint_generation_failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "content": f"Blueprint generation failed: {str(e)}. Check API key and try again.",
            "blueprint": None,
        }


async def revise_blueprint(
    db: AsyncSession,
    org_id: uuid.UUID,
    machine_state: dict[str, Any],
    current_blueprint_content: str,
    operator_feedback: str,
    conversation_history: list[dict],
) -> dict[str, Any]:
    """Revise an existing blueprint based on operator feedback."""
    messages = []

    # Include conversation history (last 10 turns)
    for msg in conversation_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add the revision request
    revision_context = f"""
## CURRENT MACHINE STATE
{json.dumps(machine_state, indent=2, default=str)}

## OPERATOR FEEDBACK
{operator_feedback}

Revise the blueprint to incorporate this feedback while maintaining maximum-ceiling revenue optimization.
"""
    messages.append({"role": "user", "content": revision_context})

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            from apps.api.services import secrets_service
            db_keys = await secrets_service.get_all_keys(db, org_id)
            api_key = db_keys.get("anthropic", "")

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=GM_REVISION_PROMPT,
            messages=messages,
        )

        content = response.content[0].text
        blueprint_data = _parse_blueprint_sections(content)

        return {
            "success": True,
            "content": content,
            "blueprint": blueprint_data,
            "model": "claude-sonnet-4-20250514",
        }
    except Exception as e:
        logger.error("gm.revision_failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "content": f"Blueprint revision failed: {str(e)}",
            "blueprint": None,
        }


async def gm_conversation(
    db: AsyncSession,
    org_id: uuid.UUID,
    machine_state: dict[str, Any],
    blueprint_content: Optional[str],
    conversation_history: list[dict],
    user_message: str,
) -> dict[str, Any]:
    """Handle a general GM conversation turn."""
    messages = []

    for msg in conversation_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    context = f"""
## CURRENT MACHINE STATE
{json.dumps(machine_state, indent=2, default=str)}
"""
    if blueprint_content:
        context += f"\n## ACTIVE BLUEPRINT\n{blueprint_content[:3000]}\n"

    messages.append({"role": "user", "content": f"{context}\n\nOperator message: {user_message}"})

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            from apps.api.services import secrets_service
            db_keys = await secrets_service.get_all_keys(db, org_id)
            api_key = db_keys.get("anthropic", "")

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=GM_CONVERSATION_PROMPT,
            messages=messages,
        )

        return {
            "success": True,
            "content": response.content[0].text,
            "model": "claude-sonnet-4-20250514",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": f"GM response failed: {str(e)}",
        }


# ---------------------------------------------------------------------------
# Blueprint Execution
# ---------------------------------------------------------------------------

async def execute_blueprint_step(
    db: AsyncSession,
    org_id: uuid.UUID,
    blueprint: GMBlueprint,
    step_key: str,
) -> dict[str, Any]:
    """Execute a specific step from an approved blueprint."""
    results: list[str] = []
    errors: list[str] = []

    if step_key == "create_brands":
        niches = blueprint.niche_blueprint or {}
        niche_list = niches.get("niches", [])
        if not niche_list:
            return {"success": False, "error": "No niches in blueprint"}

        for niche_entry in niche_list:
            niche_name = niche_entry.get("niche", "Unknown")
            brand_name = niche_entry.get("brand_name", niche_name.replace(" ", "").title())
            slug = re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-")
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

            brand = Brand(
                organization_id=org_id,
                name=brand_name,
                slug=slug,
                niche=niche_name,
                target_audience=niche_entry.get("target_audience", ""),
                description=niche_entry.get("content_angle", ""),
                decision_mode="guarded_auto",
            )
            db.add(brand)
            await db.flush()
            results.append(f"Created brand: {brand_name} ({niche_name})")

        return {"success": True, "results": results, "created": len(results)}

    elif step_key == "create_accounts":
        accounts_bp = blueprint.account_blueprint or {}
        account_list = accounts_bp.get("accounts", [])
        if not account_list:
            return {"success": False, "error": "No accounts in blueprint"}

        # Get brands to assign accounts to
        brand_result = await db.execute(
            select(Brand).where(
                Brand.organization_id == org_id,
                Brand.is_active == True,  # noqa: E712
            )
        )
        brands = brand_result.scalars().all()
        brand_by_niche = {(b.niche or "").lower(): b for b in brands}
        default_brand = brands[0] if brands else None

        if not default_brand:
            return {"success": False, "error": "No brands exist. Create brands first."}

        from packages.db.enums import Platform, AccountType

        for acct in account_list:
            platform_str = acct.get("platform", "youtube").lower()
            niche = (acct.get("niche", "") or "").lower()
            brand = brand_by_niche.get(niche, default_brand)

            try:
                platform = Platform(platform_str)
            except ValueError:
                platform = Platform.YOUTUBE

            account = CreatorAccount(
                brand_id=brand.id,
                platform=platform,
                account_type=AccountType.ORGANIC,
                platform_username=acct.get("username", f"user_{uuid.uuid4().hex[:6]}"),
                niche_focus=acct.get("niche", ""),
                scale_role=acct.get("role", "experimental"),
                posting_capacity_per_day=acct.get("posting_capacity", 2),
            )
            db.add(account)
            results.append(f"Created {platform_str} account: @{acct.get('username', '?')}")

        await db.flush()
        return {"success": True, "results": results, "created": len(results)}

    elif step_key == "create_offers":
        mon_bp = blueprint.monetization_blueprint or {}
        paths = mon_bp.get("paths", [])
        if not paths:
            return {"success": False, "error": "No monetization paths in blueprint"}

        brand_result = await db.execute(
            select(Brand).where(
                Brand.organization_id == org_id,
                Brand.is_active == True,  # noqa: E712
            ).limit(1)
        )
        brand = brand_result.scalar_one_or_none()
        if not brand:
            return {"success": False, "error": "No brands exist"}

        from packages.db.enums import MonetizationMethod

        METHOD_MAP = {
            "affiliate": MonetizationMethod.AFFILIATE,
            "ad_revenue": MonetizationMethod.ADSENSE,
            "adsense": MonetizationMethod.ADSENSE,
            "sponsor": MonetizationMethod.SPONSOR,
            "product": MonetizationMethod.PRODUCT,
            "course": MonetizationMethod.COURSE,
            "consulting": MonetizationMethod.CONSULTING,
            "membership": MonetizationMethod.MEMBERSHIP,
            "lead_gen": MonetizationMethod.LEAD_GEN,
        }

        for path in paths:
            method_str = (path.get("method", "affiliate") or "affiliate").lower()
            method = METHOD_MAP.get(method_str, MonetizationMethod.AFFILIATE)

            offer = Offer(
                brand_id=brand.id,
                name=path.get("offer_name", path.get("cluster", "Offer")),
                monetization_method=method,
                offer_url=path.get("url", ""),
                payout_amount=float(path.get("expected_payout", 0)),
                payout_type="cpa",
                is_active=True,
                priority=1,
            )
            db.add(offer)
            results.append(f"Created offer: {offer.name} ({method_str})")

        await db.flush()
        return {"success": True, "results": results, "created": len(results)}

    else:
        return {"success": False, "error": f"Unknown step: {step_key}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_blueprint_sections(content: str) -> dict[str, Any]:
    """Best-effort extraction of blueprint sections from GM response text."""
    sections: dict[str, Any] = {}

    section_markers = {
        "machine_assessment": ["MACHINE ASSESSMENT", "ASSESSMENT"],
        "account_blueprint": ["ACCOUNT BLUEPRINT"],
        "niche_blueprint": ["NICHE BLUEPRINT"],
        "identity_blueprint": ["IDENTITY BLUEPRINT"],
        "platform_blueprint": ["PLATFORM BLUEPRINT"],
        "monetization_blueprint": ["MONETIZATION BLUEPRINT"],
        "scaling_blueprint": ["SCALING BLUEPRINT"],
        "operator_inputs_needed": ["WHAT I NEED", "OPERATOR INPUTS", "INPUTS NEEDED"],
    }

    for key, markers in section_markers.items():
        for marker in markers:
            pattern = rf"##\s*{re.escape(marker)}(.*?)(?=##\s|\Z)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                sections[key] = {"raw": match.group(1).strip()}
                break

    return sections
