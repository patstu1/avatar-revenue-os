#!/usr/bin/env python3
"""Idempotent upsert of the 13 approved ProofHook packages into the Offer table.

This is the operator-side mirror of apps/web/src/lib/proofhook-packages.ts.
The frontend marketing surface, the backend service layer
(apps/api/services/ai_search_authority_service.PROOFHOOK_PACKAGES), and
the Offer rows seeded here MUST agree on the same package_slug values —
that slug is the cross-system join key on Stripe metadata,
ProposalLineItem.package_slug, and AISearchAuthorityReport.recommended_package_slug.

Idempotency:
  - Upsert keyed on (brand.id, Offer.name).
  - Re-running updates pricing/description/timeline; never deletes legacy
    offers from any other catalog (e.g. legacy seed_packages.py rows).
  - audience_fit_tags is set to ["proofhook_current", "<slug>", "<category>"]
    so reporting can filter to "current ProofHook catalog" without a
    schema migration.

Usage:
  docker-compose exec api python scripts/seed_proofhook_packages.py
  # or locally:
  DATABASE_URL_SYNC=postgresql://... python scripts/seed_proofhook_packages.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class _PackageDef:
    slug: str
    name: str
    category: str  # "ai_authority" | "creative_proof"
    price_cents: int
    timeline: str
    url_path: str
    description: str
    cta: str


# Mirrors apps/api/services/ai_search_authority_service.PROOFHOOK_PACKAGES
# and apps/web/src/lib/proofhook-packages.ts. Keep all three in sync.
PACKAGES: tuple[_PackageDef, ...] = (
    # ── AI Authority ──────────────────────────────────────────────
    _PackageDef(
        slug="ai_buyer_trust_test",
        name="AI Buyer Trust Test",
        category="ai_authority",
        price_cents=0,
        timeline="Free",
        url_path="/ai-buyer-trust-test",
        description=(
            "Free answer-based diagnostic that scores how easy your company is for "
            "AI search engines to understand and cite. Returns a score, top gaps, and "
            "a recommended next step."
        ),
        cta="Take the AI Buyer Trust Test — {url}",
    ),
    _PackageDef(
        slug="authority_snapshot",
        name="Authority Snapshot",
        category="ai_authority",
        price_cents=49500,
        timeline="3–5 days",
        url_path="/services/authority-snapshot",
        description=(
            "Hand-reviewed audit of your public AI search authority signals: machine "
            "readability, structured data, FAQ/proof/comparison surface, and crawler access. "
            "Delivers a prioritised gap report and a 30-day fix plan."
        ),
        cta="Book your Authority Snapshot — {url}",
    ),
    _PackageDef(
        slug="ai_search_authority_sprint",
        name="AI Search Authority Sprint",
        category="ai_authority",
        price_cents=450000,
        timeline="10–14 days",
        url_path="/ai-search-authority",
        description=(
            "10–14 day sprint that ships the full ProofHook foundation: Organization/Service/Product "
            "JSON-LD, FAQ, comparison + answer-engine pages, internal linking, robots/sitemap audit, "
            "and a referral-tracking plan. We do not promise rankings — we improve the inputs AI "
            "search engines and answer engines use."
        ),
        cta="Start the AI Search Authority Sprint — {url}",
    ),
    _PackageDef(
        slug="proof_infrastructure_buildout",
        name="Proof Infrastructure Buildout",
        category="ai_authority",
        price_cents=950000,
        timeline="3–4 weeks",
        url_path="/services/proof-infrastructure-buildout",
        description=(
            "Foundational buildout for companies missing the public proof surface AI search engines "
            "and buyers need: case studies, attributed testimonials, comparison pages, structured data, "
            "and the entity surfaces that make a company recognisable."
        ),
        cta="Begin the Proof Infrastructure Buildout — {url}",
    ),
    _PackageDef(
        slug="authority_monitoring_retainer",
        name="Authority Monitoring Retainer",
        category="ai_authority",
        price_cents=150000,
        timeline="Monthly",
        url_path="/services/authority-monitoring-retainer",
        description=(
            "Monthly retainer to keep AI search authority foundations in good standing: structured "
            "data drift checks, new-content review, FAQ refresh, internal-linking adjustments, and a "
            "monthly readiness report."
        ),
        cta="Start the Authority Monitoring Retainer — {url}",
    ),
    _PackageDef(
        slug="ai_authority_system",
        name="AI Authority System",
        category="ai_authority",
        price_cents=2500000,
        timeline="6–8 weeks",
        url_path="/services/ai-authority-system",
        description=(
            "End-to-end engagement combining the Sprint, the Buildout, and ongoing monitoring into a "
            "single system. For companies that need both the foundation and the maintenance handed off "
            "in one engagement."
        ),
        cta="Talk to us about the AI Authority System — {url}",
    ),
    # ── Creative Proof ────────────────────────────────────────────
    _PackageDef(
        slug="signal_entry",
        name="Signal Entry",
        category="creative_proof",
        price_cents=150000,
        timeline="7 days",
        url_path="/services/signal-entry",
        description=(
            "Lowest-friction entry into ProofHook short-form creative: 4 short-form video assets with "
            "hook variants, 7-day turnaround, asset delivery via download link."
        ),
        cta="Buy Signal Entry — {url}",
    ),
    _PackageDef(
        slug="momentum_engine",
        name="Momentum Engine",
        category="creative_proof",
        price_cents=250000,
        timeline="Monthly",
        url_path="/services/momentum-engine",
        description=(
            "Monthly creative engine producing 8–12 short-form assets per month with multiple hook "
            "variants per concept, two CTA angles, and a monthly refresh cadence."
        ),
        cta="Start the Momentum Engine — {url}",
    ),
    _PackageDef(
        slug="conversion_architecture",
        name="Conversion Architecture",
        category="creative_proof",
        price_cents=350000,
        timeline="10–14 days",
        url_path="/services/conversion-architecture",
        description=(
            "End-to-end creative audit and rebuild: hook/angle rebuild against the offer, offer "
            "alignment review, and a concrete production roadmap."
        ),
        cta="Book Conversion Architecture — {url}",
    ),
    _PackageDef(
        slug="paid_media_engine",
        name="Paid Media Engine",
        category="creative_proof",
        price_cents=450000,
        timeline="Monthly",
        url_path="/services/paid-media-engine",
        description=(
            "First-month build of 12–20 short-form assets with hook variations, plus offer/landing "
            "support and monthly optimization tied to paid-media performance."
        ),
        cta="Start the Paid Media Engine — {url}",
    ),
    _PackageDef(
        slug="launch_sequence",
        name="Launch Sequence",
        category="creative_proof",
        price_cents=500000,
        timeline="10–14 days",
        url_path="/services/launch-sequence",
        description=(
            "Compressed launch-focused asset batch with launch-specific hook set, CTA alignment with "
            "the launch offer, and compressed delivery on a launch timeline."
        ),
        cta="Book Launch Sequence — {url}",
    ),
    _PackageDef(
        slug="creative_command",
        name="Creative Command",
        category="creative_proof",
        price_cents=750000,
        timeline="Monthly",
        url_path="/services/creative-command",
        description=(
            "Recurring creative production at the upper end of throughput: multi-angle hooks, offer "
            "and landing support, priority turnaround, high-volume first-month build."
        ),
        cta="Start Creative Command — {url}",
    ),
    _PackageDef(
        slug="custom_growth_system",
        name="Custom Growth System",
        category="creative_proof",
        price_cents=2500000,
        timeline="Quoted per engagement",
        url_path="/services/custom-growth-system",
        description=(
            "Bespoke engagement combining AI search authority + creative proof + paid media into a "
            "single ProofHook system tailored to the company's growth model. Scoped per engagement."
        ),
        cta="Talk to us about a Custom Growth System — {url}",
    ),
)


def _safe_set_audience_tags(offer, slug: str, category: str) -> None:
    """Set audience_fit_tags to mark the offer as proofhook_current.

    audience_fit_tags is JSONB. We replace any prior list with the
    canonical marker triple. Non-list legacy values are overwritten.
    """
    offer.audience_fit_tags = [
        "proofhook_current",
        slug,
        category,
    ]


def main() -> int:
    import uuid as _uuid

    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session

    from packages.db.enums import MonetizationMethod
    from packages.db.models.core import Brand, Organization
    from packages.db.models.offers import Offer

    db_url = os.environ.get("DATABASE_URL_SYNC", "")
    if not db_url:
        print("ERROR: DATABASE_URL_SYNC is not set")
        return 2

    engine = create_engine(db_url)
    created = 0
    updated = 0
    unchanged = 0

    with Session(engine) as session:
        # Resolve org/brand IDs via raw SQL — selectin relationships on
        # Organization/Brand can pull in unmigrated columns (e.g. password
        # reset fields on users), and we don't need the relationships here.
        org_row = session.execute(
            text("SELECT id FROM organizations WHERE slug = :s LIMIT 1"),
            {"s": "proofhook"},
        ).fetchone()
        if org_row is None:
            org_row = session.execute(
                text("SELECT id FROM organizations WHERE is_active = true LIMIT 1")
            ).fetchone()
        if org_row is None:
            org_id = _uuid.uuid4()
            session.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, is_active) "
                    "VALUES (:id, :name, :slug, true)"
                ),
                {"id": org_id, "name": "ProofHook", "slug": "proofhook"},
            )
        else:
            org_id = org_row[0]

        brand_row = session.execute(
            text("SELECT id FROM brands WHERE slug = :s LIMIT 1"),
            {"s": "proofhook"},
        ).fetchone()
        if brand_row is None:
            brand_id = _uuid.uuid4()
            session.execute(
                text(
                    "INSERT INTO brands (id, organization_id, name, slug, niche, is_active, decision_mode) "
                    "VALUES (:id, :org, :name, :slug, :niche, true, :dm)"
                ),
                {
                    "id": brand_id,
                    "org": org_id,
                    "name": "ProofHook",
                    "slug": "proofhook",
                    "niche": "b2b_services",
                    "dm": "guarded_auto",
                },
            )
        else:
            brand_id = brand_row[0]

        # Bind the brand_id to a tiny object so the ORM upsert below stays
        # readable — we still use the Offer ORM for the upsert because the
        # column shape is non-trivial (JSONB tags, enum monetization).
        class _BrandRef:
            id = brand_id

        brand = _BrandRef()

        # Upsert each approved package.
        for pkg in PACKAGES:
            existing = session.execute(
                select(Offer).where(
                    Offer.brand_id == brand.id,
                    Offer.name == pkg.name,
                )
            ).scalar_one_or_none()

            if existing is None:
                offer = Offer(
                    brand_id=brand.id,
                    name=pkg.name,
                    description=pkg.description,
                    monetization_method=MonetizationMethod.CONSULTING,
                    payout_amount=pkg.price_cents / 100.0,
                    payout_type="fixed",
                    offer_url=pkg.url_path,
                    cta_template=pkg.cta,
                    rotation_weight=1.0,
                    is_active=True,
                    priority=PACKAGES.index(pkg),
                )
                _safe_set_audience_tags(offer, pkg.slug, pkg.category)
                session.add(offer)
                created += 1
                continue

            # Capture pre-update state so we can decide if we changed
            # anything observable to the caller.
            before = (
                existing.description,
                float(existing.payout_amount),
                existing.offer_url,
                existing.cta_template,
                existing.is_active,
                list(existing.audience_fit_tags or []),
                existing.monetization_method,
            )
            existing.description = pkg.description
            existing.monetization_method = MonetizationMethod.CONSULTING
            existing.payout_amount = pkg.price_cents / 100.0
            existing.payout_type = "fixed"
            existing.offer_url = pkg.url_path
            existing.cta_template = pkg.cta
            existing.is_active = True
            _safe_set_audience_tags(existing, pkg.slug, pkg.category)
            after = (
                existing.description,
                float(existing.payout_amount),
                existing.offer_url,
                existing.cta_template,
                existing.is_active,
                list(existing.audience_fit_tags or []),
                existing.monetization_method,
            )
            if before == after:
                unchanged += 1
            else:
                updated += 1

        session.commit()

    proof = {
        "organization_slug": "proofhook",
        "brand_slug": "proofhook",
        "packages_total": len(PACKAGES),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "approved_slugs": [p.slug for p in PACKAGES],
    }
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
