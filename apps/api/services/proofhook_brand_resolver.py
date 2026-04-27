"""Resolve the canonical ProofHook organization + brand from the DB.

Doctrine: attribution UUIDs do not live on the frontend. The Stripe lock
already proved the operator's org from ``integration_providers`` for
webhook routing; this resolver does the same for marketing-side lead
attribution by looking up the seeded ``organizations.slug='proofhook'``
row and the matching brand. Single-tenant assumption matches the rest
of the system.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand, Organization

logger = structlog.get_logger()

PROOFHOOK_ORG_SLUG = "proofhook"
PROOFHOOK_BRAND_SLUG = "proofhook"


class ProofHookBrandNotConfigured(Exception):
    """Raised when neither the seeded ProofHook org nor a unique active
    organization can be resolved. Operator-safe message."""


async def resolve_proofhook_org_and_brand(
    db: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    """Return (organization_id, brand_id|None) for the canonical ProofHook
    operator entity. Raises ProofHookBrandNotConfigured when nothing fits.

    Resolution order:
      1. Organization with slug='proofhook' → match Brand with slug='proofhook'
         under it. Brand may be None if the operator has not yet created it.
      2. Organization with name='ProofHook' (case-insensitive).
      3. Single active Organization in the DB (single-tenant fallback).

    The brand is preferred but optional — the AuthorityScoreReport's brand_id
    column is nullable, and LeadOpportunity.brand_id is required so we'll
    only upsert a LeadOpportunity if a brand is resolved.
    """
    org = (
        await db.execute(
            select(Organization).where(Organization.slug == PROOFHOOK_ORG_SLUG)
        )
    ).scalar_one_or_none()

    if org is None:
        org = (
            await db.execute(
                select(Organization).where(Organization.name.ilike("ProofHook"))
            )
        ).scalar_one_or_none()

    if org is None:
        # Last fallback — single active org (single-tenant assumption).
        active_orgs = (
            (
                await db.execute(
                    select(Organization)
                    .where(Organization.is_active.is_(True))
                    .order_by(Organization.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        if len(active_orgs) == 1:
            org = active_orgs[0]
            logger.info(
                "proofhook_brand.resolved_via_single_active_org",
                org_id=str(org.id),
                org_slug=org.slug,
            )
        elif len(active_orgs) > 1:
            logger.warning(
                "proofhook_brand.ambiguous_org",
                count=len(active_orgs),
                hint=f"No Organization has slug='{PROOFHOOK_ORG_SLUG}' and there is more than one active org. Earliest by created_at chosen.",
            )
            org = active_orgs[0]

    if org is None:
        raise ProofHookBrandNotConfigured(
            "ProofHook organization is not configured. "
            "Seed an Organization with slug='proofhook' or run scripts/seed_packages.py."
        )

    brand = (
        await db.execute(
            select(Brand).where(
                Brand.organization_id == org.id,
                Brand.slug == PROOFHOOK_BRAND_SLUG,
                Brand.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if brand is None:
        # Fall back to brand named 'ProofHook' under this org.
        brand = (
            await db.execute(
                select(Brand).where(
                    Brand.organization_id == org.id,
                    Brand.name.ilike("ProofHook"),
                    Brand.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    if brand is None:
        # Final fallback — earliest active brand under this org.
        brand = (
            await db.execute(
                select(Brand)
                .where(
                    Brand.organization_id == org.id,
                    Brand.is_active.is_(True),
                )
                .order_by(Brand.created_at.asc())
            )
        ).scalar_one_or_none()

    return org.id, (brand.id if brand else None)
