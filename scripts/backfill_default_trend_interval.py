"""One-shot backfill: ensure every existing brand carries the default trend scan interval.

Cosmetic only — _light_scan applies the default at runtime when missing.
This script makes the value visible in the dashboard so operators see it
as a configured setting rather than an absent one.

Idempotent. Safe to run multiple times.

Usage:
    python3 scripts/backfill_default_trend_interval.py
"""
from __future__ import annotations

from sqlalchemy import text

from apps.api.services.onboarding_service import DEFAULT_BRAND_GUIDELINES
from packages.db.session import get_sync_engine


def main() -> None:
    interval = DEFAULT_BRAND_GUIDELINES["trend_scan_interval_seconds"]
    engine = get_sync_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE brands
                SET brand_guidelines = COALESCE(brand_guidelines, '{}'::jsonb)
                                       || jsonb_build_object('trend_scan_interval_seconds', :interval)
                WHERE (brand_guidelines->>'trend_scan_interval_seconds') IS NULL
                """
            ),
            {"interval": interval},
        )
        print(f"updated brands: {result.rowcount}")


if __name__ == "__main__":
    main()
