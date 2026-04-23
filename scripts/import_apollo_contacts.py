#!/usr/bin/env python3
"""Import Apollo.io contact exports into the revenue OS.

Creates:
  1. LeadOpportunity records (scored, qualified)
  2. CloserAction records (email follow-up queued for the outreach worker)

Usage:
  python scripts/import_apollo_contacts.py /path/to/apollo-contacts-export.csv [--brand-slug=proofhook]

Requires DATABASE_URL_SYNC in env or .env file.
"""
from __future__ import annotations

import csv
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env if present
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def score_lead(row: dict) -> dict:
    """Compute lead qualification scores from Apollo data."""
    title = (row.get("Title") or "").lower()
    employees = int(row.get("# Employees") or "0") if row.get("# Employees") else 0
    email_status = row.get("Email Status", "").lower()
    seniority = (row.get("Seniority") or "").lower()

    # Urgency: higher for decision-makers
    urgency = 0.3
    if any(t in title for t in ("ceo", "founder", "owner", "president", "cto", "coo")):
        urgency = 0.9
    elif any(t in title for t in ("director", "vp", "head of", "chief")):
        urgency = 0.7
    elif any(t in title for t in ("manager", "lead")):
        urgency = 0.5

    # Budget proxy: company size
    budget = 0.3
    if employees > 50:
        budget = 0.8
    elif employees > 10:
        budget = 0.6
    elif employees > 3:
        budget = 0.4

    # Sophistication: based on seniority + keywords
    sophistication = 0.5
    if "founder" in seniority or "c-suite" in seniority:
        sophistication = 0.8
    elif "director" in seniority:
        sophistication = 0.7

    # Trust readiness: verified email = higher trust
    trust = 0.7 if email_status == "verified" else 0.4

    # Composite
    composite = round(urgency * 0.3 + budget * 0.2 + sophistication * 0.2 + trust * 0.3, 3)

    # Qualification tier
    if composite >= 0.65:
        tier = "hot"
    elif composite >= 0.45:
        tier = "warm"
    else:
        tier = "cold"

    return {
        "urgency_score": urgency,
        "budget_proxy_score": budget,
        "sophistication_score": sophistication,
        "trust_readiness_score": trust,
        "offer_fit_score": 0.6,  # Default — unknown fit until conversation
        "composite_score": composite,
        "qualification_tier": tier,
        "expected_value": employees * 50 if employees > 0 else 100,  # Rough estimate
        "likelihood_to_close": composite * 0.5,
    }


def classify_vertical(row: dict) -> str:
    """Classify a contact into a vertical: aesthetic-theory, body-theory, or tool-signal."""
    keywords = (row.get("Keywords", "") + " " + row.get("Industry", "") + " " + row.get("Title", "")).lower()
    if any(k in keywords for k in ("beauty", "skincare", "cosmetic", "aesthetic", "wellness", "spa", "hair", "nail")):
        return "aesthetic-theory"
    if any(k in keywords for k in ("fitness", "supplement", "gym", "workout", "recovery", "nutrition", "sport", "health")):
        return "body-theory"
    # Default to tool-signal for tech/SaaS/general
    return "tool-signal"


def build_outreach_subject(row: dict, vertical: str) -> str:
    first = row.get("First Name", "")
    company = row.get("Company Name", "")
    title = row.get("Title", "")

    if vertical == "aesthetic-theory":
        return f"{first}, stronger beauty creative for {company}"
    elif vertical == "body-theory":
        return f"{first}, fitness content engine for {company}"
    elif "content" in title.lower() or "marketing" in title.lower():
        return f"{first}, quick question about {company}'s content strategy"
    elif any(t in title.lower() for t in ("founder", "ceo", "owner")):
        return f"{first}, AI content engine for {company}?"
    else:
        return f"{first}, idea for {company}'s content pipeline"


def build_outreach_rationale(row: dict, vertical: str) -> str:
    company = row.get("Company Name", "")
    title = row.get("Title", "")
    industry = row.get("Industry", "")

    if vertical == "aesthetic-theory":
        return (
            f"Outreach to {title} at {company} ({industry}). "
            f"ProofHook builds short-form beauty content — UGC-style videos, hooks, and campaign assets — "
            f"for brands like {company} that need stronger creative without a full production team."
        )
    elif vertical == "body-theory":
        return (
            f"Outreach to {title} at {company} ({industry}). "
            f"ProofHook builds fitness content packages — short-form assets, hook variations, and campaign-ready creative — "
            f"for brands like {company} that need more usable content at speed."
        )
    else:
        return (
            f"Outreach to {title} at {company} ({industry}). "
            f"ProofHook builds AI-powered content packages — short-form video, hooks, and offer-aligned creative — "
            f"for software and AI brands like {company} that need stronger top-of-funnel proof."
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import Apollo contacts")
    parser.add_argument("csv_files", nargs="+", help="Path to Apollo CSV export(s)")
    parser.add_argument("--brand-slug", default=None, help="Force all leads to one brand (otherwise auto-classifies by vertical)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be imported without writing to DB")
    args = parser.parse_args()

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC", "")
    if not db_url:
        print("ERROR: DATABASE_URL_SYNC not set")
        sys.exit(1)

    engine = create_engine(db_url)

    # Collect all rows from all CSV files
    all_rows = []
    for csv_path in args.csv_files:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_rows.append(row)

    print(f"Loaded {len(all_rows)} contacts from {len(args.csv_files)} file(s)")

    # Filter to verified/extrapolated emails only
    valid_rows = [r for r in all_rows if r.get("Email") and r.get("Email Status", "").lower() in ("verified", "extrapolated")]
    print(f"  → {len(valid_rows)} with verified/extrapolated emails")

    if args.dry_run:
        verticals = {"aesthetic-theory": 0, "body-theory": 0, "tool-signal": 0}
        for r in valid_rows:
            verticals[classify_vertical(r)] += 1
        for r in valid_rows[:5]:
            scores = score_lead(r)
            v = classify_vertical(r)
            print(f"  [{v}] {r['First Name']} {r['Last Name']} ({r['Title']}) @ {r['Company Name']} — {r['Email']} — {scores['qualification_tier']} (score={scores['composite_score']:.2f})")
        print(f"  ... and {len(valid_rows) - 5} more")
        print(f"  Vertical split: {verticals}")
        return

    with Session(engine) as session:
        from packages.db.models.core import Brand
        from packages.db.models.expansion_pack2_phase_a import LeadOpportunity, CloserAction

        # Load brand map by vertical
        brand_map = {}
        if args.brand_slug:
            b = session.execute(select(Brand).where(Brand.slug == args.brand_slug, Brand.is_active.is_(True))).scalar_one_or_none()
            if b:
                for v in ("aesthetic-theory", "body-theory", "tool-signal"):
                    brand_map[v] = b
        else:
            for slug in ("aesthetic-theory", "body-theory", "tool-signal"):
                b = session.execute(select(Brand).where(Brand.slug == slug, Brand.is_active.is_(True))).scalar_one_or_none()
                if b:
                    brand_map[slug] = b

        if not brand_map:
            b = session.execute(select(Brand).where(Brand.is_active.is_(True)).limit(1)).scalar_one_or_none()
            if b:
                for v in ("aesthetic-theory", "body-theory", "tool-signal"):
                    brand_map[v] = b

        if not brand_map:
            print("ERROR: No active brands found. Run seed_packages.py first.")
            sys.exit(1)

        print(f"Brand map: {', '.join(f'{k}={v.name}' for k, v in brand_map.items())}")

        leads_created = 0
        actions_created = 0
        skipped = 0

        for row in valid_rows:
            email = row["Email"].strip()
            first = row.get("First Name", "").strip()
            last = row.get("Last Name", "").strip()
            company = row.get("Company Name", "").strip()
            title = row.get("Title", "").strip()

            # Skip if no email
            if not email:
                skipped += 1
                continue

            # Classify vertical
            vertical = classify_vertical(row)
            brand = brand_map.get(vertical)
            if not brand:
                skipped += 1
                continue

            # Check for duplicate
            existing = session.execute(
                select(LeadOpportunity).where(
                    LeadOpportunity.brand_id == brand.id,
                    LeadOpportunity.message_text.contains(email),
                ).limit(1)
            ).scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            scores = score_lead(row)

            # Create LeadOpportunity
            lead = LeadOpportunity(
                brand_id=brand.id,
                lead_source=f"apollo_import:{row.get('Apollo Contact Id', '')}",
                message_text=(
                    f"Name: {first} {last}\n"
                    f"Email: {email}\n"
                    f"Company: {company}\n"
                    f"Title: {title}\n"
                    f"Industry: {row.get('Industry', '')}\n"
                    f"Employees: {row.get('# Employees', '')}\n"
                    f"LinkedIn: {row.get('Person Linkedin Url', '')}\n"
                    f"Website: {row.get('Website', '')}\n"
                    f"City: {row.get('City', '')}, {row.get('State', '')}, {row.get('Country', '')}\n"
                    f"Phone: {row.get('Mobile Phone', '') or row.get('Corporate Phone', '')}\n"
                ),
                urgency_score=scores["urgency_score"],
                budget_proxy_score=scores["budget_proxy_score"],
                sophistication_score=scores["sophistication_score"],
                trust_readiness_score=scores["trust_readiness_score"],
                offer_fit_score=scores["offer_fit_score"],
                composite_score=scores["composite_score"],
                qualification_tier=scores["qualification_tier"],
                expected_value=scores["expected_value"],
                likelihood_to_close=scores["likelihood_to_close"],
                recommended_action=f"Email outreach to {first} {last} at {company}",
                channel_preference="email",
                confidence=0.7 if row.get("Email Status", "").lower() == "verified" else 0.5,
                explanation=f"Apollo import: {title} at {company} ({row.get('Industry', '')})",
                is_active=True,
            )
            session.add(lead)
            session.flush()
            leads_created += 1

            # Create CloserAction for email follow-up
            subject = build_outreach_subject(row, vertical)
            rationale = build_outreach_rationale(row, vertical)

            action = CloserAction(
                brand_id=brand.id,
                lead_opportunity_id=lead.id,
                action_type="apollo_outreach",
                priority=1 if scores["qualification_tier"] == "hot" else 2 if scores["qualification_tier"] == "warm" else 3,
                channel="email",
                subject_or_opener=subject,
                timing="immediate",
                rationale=rationale,
                expected_outcome=f"Initial contact with {first} at {company}. Goal: book a call or get a reply.",
                is_completed=False,
                is_active=True,
            )
            session.add(action)
            actions_created += 1

        session.commit()

    print(f"\nDone!")
    print(f"  Leads created: {leads_created}")
    print(f"  CloserActions queued: {actions_created}")
    print(f"  Skipped (duplicate/empty): {skipped}")
    print(f"\nThe outreach worker runs every 15 minutes and will send these via Brevo SMTP.")


if __name__ == "__main__":
    main()
