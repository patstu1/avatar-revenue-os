"""Provider Registry service — audit, list, readiness, blockers, dependencies."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.provider_registry import (
    ProviderBlocker,
    ProviderCapability,
    ProviderDependency,
    ProviderReadinessReport,
    ProviderRegistryEntry,
    ProviderUsageEvent,
)
from packages.scoring.provider_registry_engine import (
    audit_all_providers,
    get_dependency_map,
    get_provider_blockers,
)


# ---------------------------------------------------------------------------
# WRITE: Full audit (idempotent upsert from engine)
# ---------------------------------------------------------------------------

async def audit_providers(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Run the full provider audit, persist all rows, return summary."""
    audited = audit_all_providers()

    # ── Registry entries (upsert by provider_key) ──────────────────────
    for p in audited:
        existing = (
            await db.execute(
                select(ProviderRegistryEntry).where(
                    ProviderRegistryEntry.provider_key == p["provider_key"]
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.display_name = p["display_name"]
            existing.category = p["category"]
            existing.provider_type = p["provider_type"]
            existing.description = p.get("description")
            existing.env_keys = p.get("env_keys", [])
            existing.credential_status = p["credential_status"]
            existing.integration_status = p["integration_status"]
            existing.is_primary = p.get("is_primary", False)
            existing.is_fallback = p.get("is_fallback", False)
            existing.is_optional = p.get("is_optional", False)
            existing.capabilities_json = p.get("capabilities", [])
        else:
            db.add(ProviderRegistryEntry(
                provider_key=p["provider_key"],
                display_name=p["display_name"],
                category=p["category"],
                provider_type=p["provider_type"],
                description=p.get("description"),
                env_keys=p.get("env_keys", []),
                credential_status=p["credential_status"],
                integration_status=p["integration_status"],
                is_primary=p.get("is_primary", False),
                is_fallback=p.get("is_fallback", False),
                is_optional=p.get("is_optional", False),
                capabilities_json=p.get("capabilities", []),
            ))

    # ── Capabilities (replace all) ─────────────────────────────────────
    await db.execute(delete(ProviderCapability))
    cap_count = 0
    for p in audited:
        for cap in p.get("capabilities", []):
            db.add(ProviderCapability(
                provider_key=p["provider_key"],
                capability=cap,
                description=f"{p['display_name']}: {cap}",
            ))
            cap_count += 1

    # ── Dependencies (replace all) ─────────────────────────────────────
    await db.execute(delete(ProviderDependency))
    deps = get_dependency_map()
    for d in deps:
        db.add(ProviderDependency(
            provider_key=d["provider_key"],
            module_path=d["module_path"],
            dependency_type=d["dependency_type"],
            description=d.get("description"),
        ))

    # ── Readiness reports (replace for brand) ──────────────────────────
    await db.execute(
        delete(ProviderReadinessReport).where(
            ProviderReadinessReport.brand_id == brand_id
        )
    )
    readiness_count = 0
    for p in audited:
        missing = p.get("missing_keys", [])
        action = None
        if missing:
            action = f"Set environment variable(s): {', '.join(missing)}"
        db.add(ProviderReadinessReport(
            brand_id=brand_id,
            provider_key=p["provider_key"],
            credential_status=p["credential_status"],
            integration_status=p["integration_status"],
            is_ready=p["is_ready"],
            missing_env_keys=missing,
            operator_action=action,
            details_json={
                "effective_status": p.get("effective_status"),
                "capabilities": p.get("capabilities", []),
            },
        ))
        readiness_count += 1

    # ── Blockers (replace for brand) ───────────────────────────────────
    await db.execute(
        delete(ProviderBlocker).where(
            ProviderBlocker.brand_id == brand_id,
            ProviderBlocker.resolved.is_(False),
        )
    )
    blocker_data = get_provider_blockers(str(brand_id))
    for b in blocker_data:
        db.add(ProviderBlocker(
            brand_id=brand_id,
            provider_key=b["provider_key"],
            blocker_type=b["blocker_type"],
            severity=b["severity"],
            description=b["description"],
            operator_action_needed=b["operator_action_needed"],
        ))

    await db.flush()

    return {
        "providers_audited": len(audited),
        "capabilities_written": cap_count,
        "dependencies_written": len(deps),
        "readiness_reports_written": readiness_count,
        "blockers_found": len(blocker_data),
    }


# ---------------------------------------------------------------------------
# READ: All side-effect free
# ---------------------------------------------------------------------------

async def list_providers(db: AsyncSession) -> list[dict]:
    rows = list(
        (await db.execute(
            select(ProviderRegistryEntry)
            .where(ProviderRegistryEntry.is_active.is_(True))
            .order_by(ProviderRegistryEntry.category, ProviderRegistryEntry.provider_key)
        )).scalars().all()
    )
    return [_ser_entry(r) for r in rows]


async def list_readiness(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list(
        (await db.execute(
            select(ProviderReadinessReport)
            .where(
                ProviderReadinessReport.brand_id == brand_id,
                ProviderReadinessReport.is_active.is_(True),
            )
            .order_by(ProviderReadinessReport.provider_key)
        )).scalars().all()
    )
    return [_ser_readiness(r) for r in rows]


async def list_dependencies(db: AsyncSession) -> list[dict]:
    rows = list(
        (await db.execute(
            select(ProviderDependency)
            .where(ProviderDependency.is_active.is_(True))
            .order_by(ProviderDependency.provider_key, ProviderDependency.module_path)
        )).scalars().all()
    )
    return [_ser_dependency(r) for r in rows]


async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list(
        (await db.execute(
            select(ProviderBlocker)
            .where(
                ProviderBlocker.brand_id == brand_id,
                ProviderBlocker.is_active.is_(True),
                ProviderBlocker.resolved.is_(False),
            )
            .order_by(ProviderBlocker.severity, ProviderBlocker.provider_key)
        )).scalars().all()
    )
    return [_ser_blocker(r) for r in rows]


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _ser_entry(r: ProviderRegistryEntry) -> dict:
    return {
        "id": str(r.id),
        "provider_key": r.provider_key,
        "display_name": r.display_name,
        "category": r.category,
        "provider_type": r.provider_type,
        "description": r.description,
        "env_keys": r.env_keys or [],
        "credential_status": r.credential_status,
        "integration_status": r.integration_status,
        "is_primary": r.is_primary,
        "is_fallback": r.is_fallback,
        "is_optional": r.is_optional,
        "capabilities_json": r.capabilities_json,
        "config_json": r.config_json,
        "is_active": r.is_active,
        "created_at": str(r.created_at) if r.created_at else None,
    }


def _ser_readiness(r: ProviderReadinessReport) -> dict:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "provider_key": r.provider_key,
        "credential_status": r.credential_status,
        "integration_status": r.integration_status,
        "is_ready": r.is_ready,
        "missing_env_keys": r.missing_env_keys or [],
        "operator_action": r.operator_action,
        "details_json": r.details_json,
        "is_active": r.is_active,
        "created_at": str(r.created_at) if r.created_at else None,
    }


def _ser_dependency(r: ProviderDependency) -> dict:
    return {
        "id": str(r.id),
        "provider_key": r.provider_key,
        "module_path": r.module_path,
        "dependency_type": r.dependency_type,
        "description": r.description,
        "is_active": r.is_active,
    }


def _ser_blocker(r: ProviderBlocker) -> dict:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "provider_key": r.provider_key,
        "blocker_type": r.blocker_type,
        "severity": r.severity,
        "description": r.description,
        "operator_action_needed": r.operator_action_needed,
        "resolved": r.resolved,
        "is_active": r.is_active,
        "created_at": str(r.created_at) if r.created_at else None,
    }
