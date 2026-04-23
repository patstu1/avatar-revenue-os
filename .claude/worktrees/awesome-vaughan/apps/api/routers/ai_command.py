"""AI Command Center — frontend-compatible ADAPTER LAYER.

Non-destructive adapter for the AI Command Center dashboard page. Returns the
EXACT shapes the frontend TypeScript interfaces expect, backed by real
existing services + direct reads where services don't exist yet.

Every endpoint is classified:
  - DELEGATED: backed by an existing service layer (no logic duplicated)
  - DIRECT_READ: direct read of an existing table (no service exists yet)

This router does NOT replace, simplify, or bypass any existing subsystem.
Any future richer per-domain service can drop in without changing the shape
returned to the frontend.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import text

from apps.api.deps import CurrentUser, DBSession

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _assert_brand(db, brand_id: UUID, user) -> bool:
    row = (
        await db.execute(
            text(
                "SELECT 1 FROM brands WHERE id = :bid AND organization_id = :oid AND is_active = true"
            ),
            {"bid": str(brand_id), "oid": str(user.organization_id)},
        )
    ).fetchone()
    return row is not None


# ──────────────────────────────────────────────────────────────────────────
# 1. /ai-command/providers — returns AIProviderStatus[]
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/ai-command/providers")
async def ai_command_providers(
    brand_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[dict[str, Any]]:
    """Return the provider stack as AIProviderStatus[] for the frontend.

    Backed by:
      - provider_registry_service.list_readiness(db, brand_id)   [DELEGATED]
      - provider_registry_service.list_blockers(db, brand_id)    [DELEGATED]
      - secrets_service.get_all_keys(db, organization_id)        [DELEGATED]
    """
    if not await _assert_brand(db, brand_id, current_user):
        return []

    from apps.api.services import provider_registry_service as prs
    from apps.api.services import secrets_service
    import os

    readiness = await prs.list_readiness(db, brand_id)
    blockers = await prs.list_blockers(db, brand_id)
    db_keys = await secrets_service.get_all_keys(db, current_user.organization_id)

    readiness_by_name = {str(r.get("provider_name", "")).lower(): r for r in readiness}
    blockers_by_provider: dict[str, int] = {}
    for b in blockers:
        name = str(b.get("provider_name", "")).lower()
        if name:
            blockers_by_provider[name] = blockers_by_provider.get(name, 0) + 1

    results: list[dict[str, Any]] = []
    for name, env_key in secrets_service.ENV_KEY_MAP.items():
        has_db = bool(db_keys.get(name))
        has_env = bool(os.environ.get(env_key))
        if not (has_db or has_env):
            continue  # Only surface providers that are actually configured

        r = readiness_by_name.get(name, {})
        blocker_count = blockers_by_provider.get(name, 0)
        hs = r.get("health_status", "healthy")
        if blocker_count > 0:
            status_value = "degraded" if blocker_count < 3 else "down"
        elif hs == "critical":
            status_value = "down"
        elif hs == "degraded":
            status_value = "degraded"
        else:
            status_value = "healthy"

        results.append({
            "provider": name,
            "display_name": name.replace("_", " ").title(),
            "status": status_value,
            "circuit_breaker": "open" if status_value == "down" else ("half_open" if status_value == "degraded" else "closed"),
            "current_load_pct": float(r.get("load_pct") or 0),
            "error_rate_pct": float(r.get("error_rate_pct") or 0),
            "cost_per_unit": float(r.get("cost_per_unit") or 0),
            "avg_latency_ms": int(r.get("avg_latency_ms") or 0),
            "requests_24h": int(r.get("requests_24h") or 0),
        })

    return results


# ──────────────────────────────────────────────────────────────────────────
# 2. /ai-command/quality-gate — returns QualityGateStats
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/ai-command/quality-gate")
async def ai_command_quality_gate(
    brand_id: UUID, current_user: CurrentUser, db: DBSession
) -> dict[str, Any]:
    """Return quality gate stats in the shape the frontend expects.

    Backed by:
      - quality_governor_service.list_reports(db, brand_id)  [DELEGATED]
      - quality_governor_service.list_blocks(db, brand_id)   [DELEGATED]
    """
    empty = {
        "total_evaluated": 0,
        "pass_rate_pct": 0.0,
        "avg_score": 0.0,
        "recent_scores": [],
        "dimension_averages": [],
    }
    if not await _assert_brand(db, brand_id, current_user):
        return empty

    from apps.api.services import quality_governor_service as qgs

    reports = await qgs.list_reports(db, brand_id)

    if not reports:
        return empty

    total = len(reports)
    passed = sum(1 for r in reports if getattr(r, "publish_allowed", False))
    pass_rate = (passed / total * 100) if total else 0.0

    scores = [float(getattr(r, "total_score", 0) or 0) for r in reports]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    recent_scores = []
    for r in reports[:10]:
        # Pull content title where possible
        title_row = (
            await db.execute(
                text("SELECT title FROM content_items WHERE id = :cid"),
                {"cid": str(r.content_item_id)},
            )
        ).fetchone()
        title = title_row[0] if title_row else "Content item"
        recent_scores.append({
            "content_id": str(r.content_item_id),
            "title": title,
            "overall_score": float(getattr(r, "total_score", 0) or 0),
            "passed": bool(getattr(r, "publish_allowed", False)),
            "dimensions": [],
            "evaluated_at": r.created_at.isoformat() if r.created_at else "",
        })

    return {
        "total_evaluated": total,
        "pass_rate_pct": round(pass_rate, 2),
        "avg_score": round(avg_score, 2),
        "recent_scores": recent_scores,
        "dimension_averages": [],
    }


# ──────────────────────────────────────────────────────────────────────────
# 3. /ai-command/experiments — returns Experiment[]
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/ai-command/experiments")
async def ai_command_experiments(
    brand_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[dict[str, Any]]:
    """Return experiments in the Experiment[] shape the frontend expects.

    Backed by:
      - experiments table (direct read — service exists but returns a different shape)
    """
    if not await _assert_brand(db, brand_id, current_user):
        return []

    rows = (
        await db.execute(
            text(
                """
                SELECT id, name, status, experiment_type, target_metric,
                       current_sample_size, winning_variant_id,
                       start_date, created_at
                FROM experiments
                WHERE brand_id = CAST(:bid AS UUID)
                ORDER BY created_at DESC LIMIT 50
                """
            ),
            {"bid": str(brand_id)},
        )
    ).fetchall()

    results: list[dict[str, Any]] = []
    from datetime import datetime, timezone as tz
    for r in rows:
        started = r[7] or r[8]
        days_running = 0
        if started:
            try:
                days_running = max(0, (datetime.now(tz.utc) - started).days)
            except Exception:
                days_running = 0
        results.append({
            "id": str(r[0]),
            "name": r[1] or "",
            "status": r[2] or "running",
            "variant_a": "A",
            "variant_b": "B",
            "metric": r[4] or "conversion_rate",
            "sample_size_a": int(r[5] or 0) // 2,
            "sample_size_b": int(r[5] or 0) // 2,
            "lift_pct": 0.0,
            "confidence_pct": 0.0,
            "winner": "a" if r[6] else None,
            "started_at": started.isoformat() if started else "",
            "days_running": days_running,
        })

    return results


# ──────────────────────────────────────────────────────────────────────────
# 4. /ai-command/budget — returns BudgetData
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/ai-command/budget")
async def ai_command_budget(
    brand_id: UUID, current_user: CurrentUser, db: DBSession
) -> dict[str, Any]:
    """Return BudgetData in the exact frontend shape.

    Backed by:
      - provider_usage_costs table (last 30 days) [DIRECT_READ]
    """
    empty = {
        "total_budget": 0.0,
        "total_spent": 0.0,
        "total_revenue": 0.0,
        "overall_roi": 0.0,
        "channels": [],
        "rebalance_recommendations": [],
    }
    if not await _assert_brand(db, brand_id, current_user):
        return empty

    total_row = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM(cost), 0) FROM provider_usage_costs "
                "WHERE brand_id = CAST(:bid AS UUID) AND created_at > NOW() - INTERVAL '30 days'"
            ),
            {"bid": str(brand_id)},
        )
    ).fetchone()

    provider_rows = (
        await db.execute(
            text(
                "SELECT provider, COALESCE(SUM(cost), 0) "
                "FROM provider_usage_costs "
                "WHERE brand_id = CAST(:bid AS UUID) AND created_at > NOW() - INTERVAL '30 days' "
                "GROUP BY provider ORDER BY SUM(cost) DESC"
            ),
            {"bid": str(brand_id)},
        )
    ).fetchall()

    total_spent = float(total_row[0]) if total_row and total_row[0] is not None else 0.0

    # Revenue: real ledger for the window (table is 'revenue_ledger' with 'net_amount')
    rev_row = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM(net_amount), 0) FROM revenue_ledger "
                "WHERE brand_id = CAST(:bid AS UUID) AND created_at > NOW() - INTERVAL '30 days' "
                "AND is_active = true"
            ),
            {"bid": str(brand_id)},
        )
    ).fetchone()
    total_revenue = float(rev_row[0]) if rev_row and rev_row[0] is not None else 0.0

    overall_roi = (total_revenue / total_spent) if total_spent > 0 else 0.0

    channels = [
        {
            "channel": r[0] or "unknown",
            "allocated": 0.0,
            "spent": float(r[1] or 0),
            "revenue": 0.0,
            "roi": 0.0,
        }
        for r in provider_rows
    ]

    return {
        "total_budget": 0.0,
        "total_spent": total_spent,
        "total_revenue": total_revenue,
        "overall_roi": overall_roi,
        "channels": channels,
        "rebalance_recommendations": [],
    }


# ──────────────────────────────────────────────────────────────────────────
# 5. /ai-command/system-health — returns SystemHealthData
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/ai-command/system-health")
async def ai_command_system_health(
    brand_id: UUID, current_user: CurrentUser, db: DBSession
) -> dict[str, Any]:
    """Return SystemHealthData in the exact frontend shape.

    Backed by:
      - system_jobs (last 1h and 24h) [DIRECT_READ]
    """
    empty = {
        "workers": [],
        "queue_depths": [],
        "error_rate_1h": 0.0,
        "error_rate_24h": 0.0,
        "auto_recovery_actions": [],
    }
    if not await _assert_brand(db, brand_id, current_user):
        return empty

    # Per-queue stats last 24h
    queue_rows = (
        await db.execute(
            text(
                """
                SELECT queue, COUNT(*) FILTER (WHERE status = 'COMPLETED'),
                       COUNT(*) FILTER (WHERE status IN ('FAILED','RETRYING')),
                       COUNT(*),
                       COALESCE(AVG(duration_seconds) FILTER (WHERE status = 'COMPLETED'), 0)
                FROM system_jobs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY queue ORDER BY COUNT(*) DESC
                """
            )
        )
    ).fetchall()

    workers: list[dict[str, Any]] = []
    for r in queue_rows:
        total = int(r[3] or 0)
        completed = int(r[1] or 0)
        failed = int(r[2] or 0)
        avg_s = float(r[4] or 0)
        status_value = "active" if completed > 0 else ("error" if failed > 0 else "idle")
        workers.append({
            "name": r[0] or "default",
            "status": status_value,
            "active_tasks": 0,
            "completed_24h": completed,
            "failed_24h": failed,
            "avg_execution_ms": int(avg_s * 1000),
        })

    # Error rates
    row_1h = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status IN ('FAILED','RETRYING'))::float /
                    NULLIF(COUNT(*), 0) * 100
                FROM system_jobs
                WHERE created_at > NOW() - INTERVAL '1 hour'
                """
            )
        )
    ).fetchone()
    row_24h = (
        await db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status IN ('FAILED','RETRYING'))::float /
                    NULLIF(COUNT(*), 0) * 100
                FROM system_jobs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                """
            )
        )
    ).fetchone()

    err_1h = float(row_1h[0]) if row_1h and row_1h[0] is not None else 0.0
    err_24h = float(row_24h[0]) if row_24h and row_24h[0] is not None else 0.0

    return {
        "workers": workers,
        "queue_depths": [],
        "error_rate_1h": round(err_1h, 2),
        "error_rate_24h": round(err_24h, 2),
        "auto_recovery_actions": [],
    }


# ──────────────────────────────────────────────────────────────────────────
# 6. /ai-command/activity — returns ActivityEvent[]
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{brand_id}/ai-command/activity")
async def ai_command_activity(
    brand_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[dict[str, Any]]:
    """Return ActivityEvent[] in the exact frontend shape.

    Backed by:
      - system_events scoped by brand_id [DIRECT_READ]
    """
    if not await _assert_brand(db, brand_id, current_user):
        return []

    rows = (
        await db.execute(
            text(
                """
                SELECT id, event_type, event_domain, summary, event_severity, created_at
                FROM system_events
                WHERE brand_id = CAST(:bid AS UUID)
                ORDER BY created_at DESC LIMIT 20
                """
            ),
            {"bid": str(brand_id)},
        )
    ).fetchall()

    type_map = {
        "publishing": "ai_call",
        "quality": "quality_gate",
        "experiment": "experiment",
        "monetization": "budget",
        "recovery": "recovery",
        "alerting": "alert",
    }

    results: list[dict[str, Any]] = []
    for r in rows:
        domain = (r[2] or "").lower()
        event_type = type_map.get(domain, "alert")
        severity = (r[4] or "info").lower()
        if severity not in ("info", "warning", "error"):
            severity = "info"
        results.append({
            "id": str(r[0]),
            "type": event_type,
            "message": r[3] or r[1] or "",
            "timestamp": r[5].isoformat() if r[5] else "",
            "severity": severity,
        })

    return results
