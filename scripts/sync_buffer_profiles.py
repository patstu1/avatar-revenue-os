#!/usr/bin/env python3
"""Sync Buffer profiles into the database.

Fetches all connected profiles from Buffer's API and creates/updates
BufferProfile records in the DB, mapped to a specific brand.

Usage:
  docker exec aro-api python scripts/sync_buffer_profiles.py [--brand-id UUID]

Without --brand-id, uses the first active brand.
"""

import argparse
import asyncio
import sys
import uuid

sys.path.insert(0, "/app")


async def main(brand_id_str: str | None = None):
    from sqlalchemy import select

    from apps.api.services import secrets_service
    from packages.clients.external_clients import BufferClient
    from packages.db.models.buffer_distribution import BufferProfile
    from packages.db.models.core import Brand
    from packages.db.session import get_async_session_factory

    async with get_async_session_factory()() as db:
        # Resolve brand
        if brand_id_str:
            brand_id = uuid.UUID(brand_id_str)
            brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        else:
            brand = (
                await db.execute(select(Brand).where(Brand.is_active.is_(True)).order_by(Brand.created_at).limit(1))
            ).scalar_one_or_none()

        if not brand:
            print("FAIL: No active brand found.")
            return

        brand_id = brand.id
        print(f"Brand: {brand.name} ({brand_id})")
        print(f"Org:   {brand.organization_id}")

        # Resolve Buffer API key (DB first, then env)
        db_key = await secrets_service.get_key(db, brand.organization_id, "buffer")
        import os

        api_key = db_key or os.environ.get("BUFFER_API_KEY", "")

        if not api_key:
            print("FAIL: No Buffer API key found. Add it via /dashboard/settings or BUFFER_API_KEY env var.")
            return

        print(f"Buffer API key: {secrets_service.mask_key(api_key)}")

        # Fetch profiles from Buffer
        client = BufferClient(api_key=api_key)
        result = await client.get_profiles()

        if not result.get("success"):
            print(f"FAIL: Buffer API error: {result.get('error')}")
            return

        profiles = result.get("data", [])
        if not profiles:
            print("FAIL: Buffer returned 0 profiles. Connect channels in Buffer first.")
            return

        print(f"\nBuffer returned {len(profiles)} profiles:\n")

        # Get existing DB profiles for this brand
        existing_q = await db.execute(select(BufferProfile).where(BufferProfile.brand_id == brand_id))
        existing = {p.buffer_profile_id: p for p in existing_q.scalars().all()}

        created = 0
        updated = 0
        for p in profiles:
            buf_id = p.get("id", "")
            service = p.get("service", "unknown")
            service_username = p.get("service_username", "")
            formatted_service = p.get("formatted_service", service)
            avatar_url = p.get("avatar_https", "")

            display_name = f"{service_username} ({formatted_service})"

            # Map Buffer service names to our platform enum
            platform_map = {
                "twitter": "x",
                "facebook": "facebook",
                "instagram": "instagram",
                "linkedin": "linkedin",
                "tiktok": "tiktok",
                "youtube": "youtube",
                "pinterest": "pinterest",
                "mastodon": "mastodon",
                "threads": "threads",
                "bluesky": "bluesky",
                "googlebusiness": "google_business",
            }
            platform_str = platform_map.get(service, service)

            print(f"  [{service}] {service_username} — id: {buf_id}")

            if buf_id in existing:
                # Update existing
                ep = existing[buf_id]
                ep.display_name = display_name
                ep.credential_status = "connected"
                ep.is_active = True
                ep.config_json = {"service": service, "avatar_url": avatar_url}
                updated += 1
            else:
                # Create new
                bp = BufferProfile(
                    brand_id=brand_id,
                    platform=platform_str,
                    display_name=display_name,
                    buffer_profile_id=buf_id,
                    credential_status="connected",
                    is_active=True,
                    config_json={"service": service, "avatar_url": avatar_url},
                )
                db.add(bp)
                created += 1

        await db.commit()
        print(f"\nDone: {created} created, {updated} updated, {len(profiles)} total in Buffer")
        print("\nProfiles are now mapped. The system can publish to these channels.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand-id", default=None, help="Brand UUID to map profiles to")
    args = parser.parse_args()
    asyncio.run(main(args.brand_id))
