"""Brain Operations router — exposes real runtime outputs from the brain/autonomous layer.

Reads the latest row from each brain subsystem table and returns a unified panel.
No new data. No reports generated. Pure surfacing of what's already running.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from apps.api.deps import CurrentUser, DBSession

router = APIRouter()


# (display_name, table_name) pairs — ordered for display
BRAIN_SUBSYSTEMS: list[tuple[str, str]] = [
    ("Signal Scanning", "signal_scan_runs"),
    ("Trend Signals", "tv_signals"),
    ("Trend Velocity", "tv_velocity"),
    ("Viral Opportunities", "tv_opportunities"),
    ("Brain Memory", "brain_memory_entries"),
    ("Brain Decisions", "brain_decisions"),
    ("Policy Evaluations", "policy_evaluations"),
    ("Confidence Reports", "confidence_reports"),
    ("Meta Monitoring", "meta_monitoring_reports"),
    ("Self Corrections", "self_correction_actions"),
    ("Workflow Coordination", "workflow_coordination_runs"),
    ("Blocker Detection", "blocker_detection_reports"),
    ("Revenue Pressure", "revenue_pressure_reports"),
    ("Escalation Events", "escalation_events"),
    ("Account State Snapshots", "account_state_snapshots"),
    ("Opportunity State Snapshots", "opportunity_state_snapshots"),
    ("Gatekeeper Reports", "gatekeeper_completion_reports"),
    ("Quality Governor", "qg_reports"),
    ("Provider Readiness", "provider_readiness_reports"),
    ("Capacity Reports", "hs_capacity_reports"),
    ("Experiment Decisions", "experiment_decisions"),
    ("Funnel Runs", "funnel_execution_runs"),
    ("Recovery Incidents", "recovery_incidents"),
    ("Operator Alerts", "operator_alerts"),
    ("System Events", "system_events"),
    ("System Jobs", "system_jobs"),
    ("Auto Queue Items", "auto_queue_items"),
    ("Distribution Plans", "distribution_plans"),
    ("Monetization Routes", "monetization_routes"),
    ("Autonomous Runs", "autonomous_runs"),
    ("Revenue Leaks", "revenue_leak_reports"),
    ("Winning Patterns", "winning_pattern_memory"),
    ("Content Routing", "content_routing_decisions"),
    ("Portfolio Allocation", "portfolio_allocations"),
]


@router.get("/brain-ops/status")
async def get_brain_ops_status(current_user: CurrentUser, db: DBSession) -> dict[str, Any]:
    """Return real runtime state of every brain subsystem.

    For each subsystem:
      - total row count
      - rows created in last 6 hours
      - timestamp of latest row
      - status: LIVE (recent activity), IDLE (has data, none recent), EMPTY (no data)
    """
    subsystems = []
    producing_count = 0
    idle_count = 0
    empty_count = 0
    missing_count = 0

    for display_name, table_name in BRAIN_SUBSYSTEMS:
        entry: dict[str, Any] = {
            "name": display_name,
            "table": table_name,
            "total": 0,
            "recent_6h": 0,
            "latest_at": None,
            "status": "EMPTY",
        }
        try:
            total = (
                await db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            ).scalar() or 0
            entry["total"] = int(total)

            if total > 0:
                latest = (
                    await db.execute(
                        text(f'SELECT MAX(created_at) FROM "{table_name}"')
                    )
                ).scalar()
                if latest:
                    entry["latest_at"] = latest.isoformat() if hasattr(latest, "isoformat") else str(latest)

                recent = (
                    await db.execute(
                        text(
                            f"SELECT COUNT(*) FROM \"{table_name}\" "
                            f"WHERE created_at > NOW() - INTERVAL '6 hours'"
                        )
                    )
                ).scalar() or 0
                entry["recent_6h"] = int(recent)

                if recent > 0:
                    entry["status"] = "LIVE"
                    producing_count += 1
                else:
                    entry["status"] = "IDLE"
                    idle_count += 1
            else:
                empty_count += 1
        except Exception as e:
            entry["status"] = "MISSING"
            entry["error"] = str(e)[:100]
            missing_count += 1

        subsystems.append(entry)

    # Job summary — how many jobs ran in last hour / last 6h
    jobs_1h = (
        await db.execute(
            text(
                "SELECT COUNT(DISTINCT job_name) FROM system_jobs "
                "WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
        )
    ).scalar() or 0

    jobs_6h = (
        await db.execute(
            text(
                "SELECT COUNT(DISTINCT job_name) FROM system_jobs "
                "WHERE created_at > NOW() - INTERVAL '6 hours'"
            )
        )
    ).scalar() or 0

    jobs_completed_1h = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM system_jobs "
                "WHERE status = 'COMPLETED' AND created_at > NOW() - INTERVAL '1 hour'"
            )
        )
    ).scalar() or 0

    jobs_failed_6h = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM system_jobs "
                "WHERE status IN ('FAILED','RETRYING') AND created_at > NOW() - INTERVAL '6 hours'"
            )
        )
    ).scalar() or 0

    # Published post proof
    real_publishes = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM publish_jobs "
                "WHERE platform_post_url LIKE 'https://%'"
            )
        )
    ).scalar() or 0

    latest_publish = (
        await db.execute(
            text(
                "SELECT platform, platform_post_url, published_at FROM publish_jobs "
                "WHERE platform_post_url LIKE 'https://%' "
                "ORDER BY published_at DESC NULLS LAST LIMIT 5"
            )
        )
    ).fetchall()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_subsystems": len(BRAIN_SUBSYSTEMS),
            "live": producing_count,
            "idle": idle_count,
            "empty": empty_count,
            "missing": missing_count,
        },
        "scheduler": {
            "distinct_jobs_last_1h": int(jobs_1h),
            "distinct_jobs_last_6h": int(jobs_6h),
            "completed_last_1h": int(jobs_completed_1h),
            "failed_or_retrying_last_6h": int(jobs_failed_6h),
        },
        "destination_publishing": {
            "real_posts_published": int(real_publishes),
            "latest": [
                {
                    "platform": r[0].value if hasattr(r[0], "value") else str(r[0]),
                    "url": r[1],
                    "published_at": r[2].isoformat() if r[2] else None,
                }
                for r in latest_publish
            ],
        },
        "subsystems": subsystems,
    }


@router.get("/brain-ops/recent-jobs")
async def get_recent_jobs(current_user: CurrentUser, db: DBSession, limit: int = 50) -> dict[str, Any]:
    """Return the latest completed jobs with timestamps for live operator view."""
    rows = (
        await db.execute(
            text(
                """
                SELECT job_name, status, queue, created_at, duration_seconds
                FROM system_jobs
                WHERE created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).fetchall()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": [
            {
                "name": r[0],
                "status": r[1],
                "queue": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "duration_seconds": float(r[4]) if r[4] is not None else None,
            }
            for r in rows
        ],
    }
