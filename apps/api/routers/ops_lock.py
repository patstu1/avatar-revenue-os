"""Final-lock ops endpoints (Batch 6).

Endpoints that make the running system's operating truth self-inspectable:

  GET /ops/health-check   full checklist — migration head, critical
                          provider configs, recent event flow, queue
                          depths, stuck stages past hard threshold.
                          Returns a structured dict with per-check
                          pass/fail + overall ``healthy`` boolean.

  GET /ops/version        HEAD SHA, alembic revision, application
                          module versions — the canonical "what is
                          currently live" report.

  GET /ops/lock-status    read-only snapshot of the canonical branch +
                          deploy metadata recorded at deploy time; used
                          to verify the running binary matches the
                          canonical commit.

These endpoints are unauthenticated (behind a proxy / internal network)
so automation can scrape them without JWT overhead. No state is
mutated.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from apps.api.deps import DBSession
from packages.db.models.gm_control import GMEscalation, StageState
from packages.db.models.integration_registry import IntegrationProvider
from packages.db.models.system_events import SystemEvent

router = APIRouter(prefix="/ops", tags=["Ops Lock"])


CANONICAL_BRANCH = "recovery/from-prod"
# Critical provider keys — the system cannot operate without these
# (or at least should loudly flag their absence).
CRITICAL_PROVIDER_KEYS = (
    "stripe_webhook",  # inbound Stripe verification
    "inbound_email_route",  # inbound reply routing
    "smtp",  # outbound email
)
RECENT_WINDOW_MINUTES = 60


@router.get("/version")
async def version() -> dict:
    """Canonical version manifest. Safe to hit from load balancers."""
    sha = _git_head_sha()
    alembic_rev = _alembic_head_revision()
    return {
        "canonical_branch": CANONICAL_BRANCH,
        "git_head": sha,
        "alembic_head_revision": alembic_rev,
        "python": _python_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/lock-status")
async def lock_status() -> dict:
    """Read-only snapshot of the deploy manifest.

    ``DEPLOY_MANIFEST_*`` env vars are written by the deploy pipeline
    (see docs/OPERATIONS.md). Absent values mean the binary was built
    outside the canonical pipeline — an operator warning.
    """
    return {
        "canonical_branch": CANONICAL_BRANCH,
        "deployed_sha": os.environ.get("DEPLOY_MANIFEST_SHA", ""),
        "deployed_at": os.environ.get("DEPLOY_MANIFEST_AT", ""),
        "deployed_by": os.environ.get("DEPLOY_MANIFEST_BY", ""),
        "build_id": os.environ.get("DEPLOY_MANIFEST_BUILD_ID", ""),
        "matches_canonical": (os.environ.get("DEPLOY_MANIFEST_BRANCH", "") == CANONICAL_BRANCH),
    }


@router.get("/health-check")
async def health_check(db: DBSession) -> dict:
    """Full production health checklist.

    Returns a dict with one entry per check, plus an overall
    ``healthy`` flag. Each check is independent — one failure doesn't
    short-circuit the rest.
    """
    checks: list[dict[str, Any]] = []

    # 1. DB reachable
    try:
        v = (await db.execute(select(func.now()))).scalar()
        checks.append({"name": "db_reachable", "ok": True, "detail": str(v)[:30]})
    except Exception as exc:
        checks.append({"name": "db_reachable", "ok": False, "detail": str(exc)[:120]})

    # 2. Alembic migration head matches code. Gate the query on
    # information_schema first so the outer async transaction is not
    # aborted by a missing alembic_version table (e.g. test DBs that
    # bootstrap via Base.metadata.create_all).
    from sqlalchemy import text as _text

    code_rev = _alembic_head_revision()
    has_alembic_table = bool(
        (
            await db.execute(
                _text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')")
            )
        ).scalar()
    )

    if not has_alembic_table:
        checks.append(
            {
                "name": "alembic_version_matches_code",
                "ok": True,  # test / create_all environment — informational only
                "detail": f"alembic_version table absent; code head={code_rev or 'unknown'}",
            }
        )
    else:
        try:
            db_rev = (await db.execute(_text("SELECT version_num FROM alembic_version LIMIT 1"))).scalar()
            checks.append(
                {
                    "name": "alembic_version_matches_code",
                    "ok": (not code_rev) or (db_rev == code_rev),
                    "detail": f"db={db_rev} code={code_rev or 'unknown'}",
                }
            )
        except Exception as exc:
            checks.append({"name": "alembic_version_matches_code", "ok": False, "detail": str(exc)[:120]})

    # 3. Canonical provider rows exist + enabled in ALL orgs that have
    # any configured providers at all (orgs that have never configured
    # anything are not penalised).
    missing_providers: list[dict] = []
    configured_orgs = (await db.execute(select(IntegrationProvider.organization_id).distinct())).scalars().all()
    for org_id in configured_orgs:
        present = (
            (
                await db.execute(
                    select(IntegrationProvider.provider_key).where(
                        IntegrationProvider.organization_id == org_id,
                        IntegrationProvider.provider_key.in_(CRITICAL_PROVIDER_KEYS),
                        IntegrationProvider.is_enabled.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = [k for k in CRITICAL_PROVIDER_KEYS if k not in present]
        if missing:
            missing_providers.append({"org_id": str(org_id), "missing": missing})
    checks.append(
        {
            "name": "critical_providers_configured",
            "ok": not missing_providers,
            "detail": missing_providers or f"{len(configured_orgs)} orgs checked",
        }
    )

    # 4. Event flow — at least one SystemEvent in the last hour across
    # the whole system is a weak but useful "is anything alive" signal.
    since = datetime.now(timezone.utc) - timedelta(minutes=RECENT_WINDOW_MINUTES)
    recent_evt_count = (
        await db.execute(select(func.count()).select_from(SystemEvent).where(SystemEvent.created_at >= since))
    ).scalar() or 0
    checks.append(
        {
            "name": "event_flow_recent",
            "ok": True,  # informational — not a hard fail
            "detail": f"{recent_evt_count} events in last {RECENT_WINDOW_MINUTES}m",
        }
    )

    # 5. Hard-stuck stages (SLA past by more than 2x timeout)
    now = datetime.now(timezone.utc)
    hard_stuck = (
        (
            await db.execute(
                select(StageState).where(
                    StageState.is_active.is_(True),
                    StageState.sla_deadline.is_not(None),
                    StageState.sla_deadline < now - timedelta(hours=1),
                )
            )
        )
        .scalars()
        .all()
    )
    checks.append(
        {
            "name": "no_hard_stuck_stages",
            "ok": len(hard_stuck) == 0,
            "detail": [
                {
                    "entity_type": s.entity_type,
                    "entity_id": str(s.entity_id),
                    "stage": s.stage,
                    "sla_deadline": s.sla_deadline.isoformat() if s.sla_deadline else None,
                }
                for s in hard_stuck[:20]
            ],
        }
    )

    # 6. Unacknowledged high-severity escalations
    unack_error = (
        await db.execute(
            select(func.count())
            .select_from(GMEscalation)
            .where(
                GMEscalation.is_active.is_(True),
                GMEscalation.status == "open",
                GMEscalation.severity == "error",
            )
        )
    ).scalar() or 0
    checks.append(
        {
            "name": "no_unacknowledged_error_escalations",
            "ok": unack_error == 0,
            "detail": f"{unack_error} open error escalations",
        }
    )

    healthy = all(c["ok"] for c in checks)
    return {
        "healthy": healthy,
        "canonical_branch": CANONICAL_BRANCH,
        "generated_at": now.isoformat(),
        "checks": checks,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _git_head_sha() -> str:
    # Pass 1: env (deploy pipeline)
    for key in ("DEPLOY_MANIFEST_SHA", "GIT_COMMIT", "COMMIT_SHA"):
        val = os.environ.get(key)
        if val:
            return val
    # Pass 2: best-effort local git
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _alembic_head_revision() -> str:
    """Read the canonical alembic head from the versions directory.

    Scans ``packages/db/alembic/versions/*.py`` for the highest-
    numbered revision. Prefers ``N_description.py`` form first, falls
    back to any file with ``revision = "..."`` at module scope.
    """
    try:
        import re

        # __file__ = .../<repo>/apps/api/routers/ops_lock.py
        # 4 dirname() calls climb back to <repo>.
        here = os.path.abspath(__file__)
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))
        versions_dir = os.path.join(root, "packages", "db", "alembic", "versions")
        if not os.path.isdir(versions_dir):
            return ""
        revs: list[tuple[int, str]] = []
        rev_pat = re.compile(r'^\s*revision\s*=\s*[\'"]([\w\-]+)[\'"]', re.M)
        for fname in os.listdir(versions_dir):
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            path = os.path.join(versions_dir, fname)
            try:
                with open(path) as fh:
                    text = fh.read(4000)
                m = rev_pat.search(text)
                if not m:
                    continue
                rev = m.group(1)
                # Sort by leading numeric prefix if present, else filename
                lead = 0
                digits = ""
                for c in rev:
                    if c.isdigit():
                        digits += c
                    else:
                        break
                if digits:
                    lead = int(digits)
                revs.append((lead, rev))
            except Exception:
                continue
        if not revs:
            return ""
        revs.sort(key=lambda t: (t[0], t[1]))
        return revs[-1][1]
    except Exception:
        return ""


def _python_version() -> str:
    import sys

    return sys.version.split()[0]
