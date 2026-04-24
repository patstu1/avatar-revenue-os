"""GM situation computations (Batch 7A-WIDE — FULL MACHINE).

Pure read-only aggregations across the FULL doctrine universe — every
revenue avenue and every strategic engine. Zero narrowing, zero
collapsing, zero ignored surfaces.

Exposed via the ``/gm/*`` router. Consumed by the GM LLM as its
situational ground truth.

Computations:

    compute_floor_status        trailing-30d revenue vs floor, COMBINED
                                across payments + creator_revenue_events
                                with per-avenue breakdown
    compute_avenue_portfolio    per-avenue status + revenue + activity
                                + strongest + weakest-unlockable
    compute_engine_status       per-engine row count + recent activity
                                + status flag
    compute_pipeline_state      B2B stage entity counts (avenue 1 only)
    compute_bottlenecks         stuck stage_states past SLA
    compute_closest_revenue     one-action-from-money items
    compute_blocking_floors     floor gap + in-flight potential combined
    compute_ask_operator        concrete list of operator inputs needed
    compute_unlock_plans        LIVE_BUT_DORMANT avenues + canonical plans
    compute_game_plan           priority-engine-ranked action list across
                                the FULL universe (not just B2B)

All org-scoped. No mutations. No LLM calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.gm_doctrine import (
    FLOOR_MONTH_1_CENTS,
    FLOOR_MONTH_12_CENTS,
    REVENUE_AVENUES,
    STAGE_MACHINE,
    STATUS_DISABLED_BY_OPERATOR,
    STATUS_LIVE_AND_ACTIVE,
    STATUS_LIVE_AND_VERY_ACTIVE,
    STATUS_LIVE_BUT_DORMANT,
    STATUS_PRESENT_IN_CODE_ONLY,
    STRATEGIC_ENGINES,
    floor_for_month,
)
from packages.db.models.clients import Client, IntakeRequest
from packages.db.models.email_pipeline import (
    EmailClassification,
    EmailReplyDraft,
)
from packages.db.models.fulfillment import ProductionJob
from packages.db.models.gm_control import GMApproval, GMEscalation, StageState
from packages.db.models.integration_registry import IntegrationProvider
from packages.db.models.proposals import Payment, Proposal

# ═══════════════════════════════════════════════════════════════════════════
#  Helper: safely fetch row counts from arbitrary table names
# ═══════════════════════════════════════════════════════════════════════════


async def _table_exists(db: AsyncSession, name: str) -> bool:
    return bool(
        (
            await db.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=:n)"
                ),
                {"n": name},
            )
        ).scalar()
    )


async def _count_table(db: AsyncSession, name: str, where: str = "") -> int | None:
    """Return row count for a table, or None if the table doesn't exist.

    Uses a savepoint so a column-mismatch (e.g. schema drift between test
    DB and prod) doesn't poison the outer transaction.
    """
    if not await _table_exists(db, name):
        return None
    sql = f'SELECT COUNT(*) FROM "{name}"'
    if where:
        sql += f" WHERE {where}"
    try:
        async with db.begin_nested():
            return int((await db.execute(text(sql))).scalar() or 0)
    except Exception:
        return None


async def _recent_activity_cutoff(db: AsyncSession, table: str, since: datetime) -> int | None:
    """Count rows in ``table`` with created_at >= since, if column exists.
    Returns None if table missing, 0 if no column or count zero. Savepoint
    -protected so column mismatches do not abort the outer transaction.
    """
    if not await _table_exists(db, table):
        return None
    try:
        async with db.begin_nested():
            res = await db.execute(
                text(f'SELECT COUNT(*) FROM "{table}" WHERE created_at >= :s'),
                {"s": since},
            )
            return int(res.scalar() or 0)
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
#  FLOOR STATUS — combined across ALL revenue ledgers, per-avenue breakdown
# ═══════════════════════════════════════════════════════════════════════════


#: Stripe / Shopify event_type values in creator_revenue_events that
#: indicate the revenue is already captured in ``payments``. Rows with
#: these event_types are EXCLUDED from recognized revenue to prevent
#: double counting.
STRIPE_ORIGIN_EVENT_TYPES: frozenset = frozenset(
    {
        "stripe_payment",
        "stripe_charge_sync",
        "stripe_invoice_paid",
        "shopify_order",
        "shopify_refund",
    }
)


def _attribute_payment_to_avenue(payment_metadata: dict | None) -> str:
    """Map a Payment row's metadata to its canonical avenue_id.

    Precedence:
      1. metadata_json->>'avenue' explicit tag (if set by caller).
      2. metadata_json->>'source' mapped (proposal → b2b_services,
         outreach_proposal → b2b_services, ugc → ugc_services, etc.).
      3. default: b2b_services (Payment was introduced for that flow
         in Batch 3A, so unattributed rows belong there).
    """
    if not isinstance(payment_metadata, dict):
        return "b2b_services"
    explicit = payment_metadata.get("avenue")
    if isinstance(explicit, str) and explicit:
        return explicit
    source = str(payment_metadata.get("source", "") or "")
    source_map = {
        "proposal": "b2b_services",
        "outreach_proposal": "b2b_services",
        "ugc": "ugc_services",
        "consulting": "consulting",
        "premium": "premium_access",
        "licensing": "licensing",
        "syndication": "syndication",
        "data_product": "data_products",
        "merch": "merchandise",
        "live_event": "live_events",
        "sponsor": "sponsor_deals",
    }
    return source_map.get(source, "b2b_services")


async def compute_floor_status(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    """Canonical recognized-revenue calculation.

    Enforces the RECOGNIZED_REVENUE_RULE from gm_doctrine:

      recognized_cents =
        SUM(payments.amount_cents WHERE status='succeeded' AND
            completed_at >= since)
      + SUM(creator_revenue_events.revenue*100 WHERE created_at >= since
            AND event_type NOT IN STRIPE_ORIGIN_EVENT_TYPES
            AND event_type NOT LIKE 'stripe_%'
            AND event_type NOT LIKE 'shopify_%')

    No other ledgers contribute. Per-avenue attribution is derived from
    each row's own metadata/tag. Plan-data ledgers (high_ticket_deals,
    sponsor_opportunities, af_commissions, af_own_partner_conversions,
    subscription_events, credit_transactions, pack_purchases,
    recurring_revenue_models) are SURFACED separately in
    ``plan_data_ledgers`` for visibility but do NOT add to the floor.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)
    since_7 = now - timedelta(days=7)

    # ── PRIMARY LEDGER: payments (Stripe + webhook ingress) ────────
    payment_rows = (
        await db.execute(
            select(Payment.amount_cents, Payment.metadata_json).where(
                Payment.org_id == org_id,
                Payment.status == "succeeded",
                Payment.is_active.is_(True),
                Payment.completed_at >= since,
            )
        )
    ).all()

    payments_total_cents = 0
    payments_by_avenue: dict[str, int] = {}
    payments_count_by_avenue: dict[str, int] = {}
    for amount_cents, metadata in payment_rows:
        amount = int(amount_cents or 0)
        payments_total_cents += amount
        avenue = _attribute_payment_to_avenue(metadata)
        payments_by_avenue[avenue] = payments_by_avenue.get(avenue, 0) + amount
        payments_count_by_avenue[avenue] = payments_count_by_avenue.get(avenue, 0) + 1

    # 7-day payments for run-rate projection
    payments_7d_cents = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                    Payment.org_id == org_id,
                    Payment.status == "succeeded",
                    Payment.completed_at >= since_7,
                )
            )
        ).scalar()
        or 0
    )

    # ── SUPPLEMENTAL LEDGER: creator_revenue_events (non-Stripe only) ──
    supplemental_by_avenue: dict[str, dict] = {}
    excluded_stripe_origin_count = 0
    excluded_stripe_origin_cents = 0

    if await _table_exists(db, "creator_revenue_events"):
        try:
            async with db.begin_nested():
                rows = (
                    await db.execute(
                        text(
                            "SELECT COALESCE(avenue_type, 'unspecified') AS avenue_type, "
                            "       COALESCE(event_type, '') AS event_type, "
                            "       COUNT(*) AS n, "
                            "       COALESCE(SUM(revenue * 100)::bigint, 0) AS cents "
                            "FROM creator_revenue_events "
                            "WHERE created_at >= :s "
                            "GROUP BY avenue_type, event_type"
                        ),
                        {"s": since},
                    )
                ).all()
        except Exception:
            rows = []

        for avenue_type, event_type, n, cents in rows:
            n = int(n or 0)
            cents = int(cents or 0)
            evt = str(event_type or "")
            is_stripe_origin = (
                evt in STRIPE_ORIGIN_EVENT_TYPES or evt.startswith("stripe_") or evt.startswith("shopify_")
            )
            if is_stripe_origin:
                excluded_stripe_origin_count += n
                excluded_stripe_origin_cents += cents
                continue
            avenue_id = _tag_to_avenue_id(avenue_type)
            bucket = supplemental_by_avenue.setdefault(
                avenue_id,
                {"cents": 0, "count": 0, "event_types": set()},
            )
            bucket["cents"] += cents
            bucket["count"] += n
            if evt:
                bucket["event_types"].add(evt)

    supplemental_total_cents = sum(b["cents"] for b in supplemental_by_avenue.values())

    # ── RECOGNIZED TOTAL (no double-count) ─────────────────────────
    recognized_total_cents = payments_total_cents + supplemental_total_cents

    # ── Per-avenue breakdown (recognized revenue only) ────────────
    all_avenue_ids: set[str] = set(payments_by_avenue.keys()) | set(supplemental_by_avenue.keys())
    avenue_breakdown: list[dict] = []
    for avenue_id in sorted(all_avenue_ids):
        p_cents = payments_by_avenue.get(avenue_id, 0)
        s_entry = supplemental_by_avenue.get(avenue_id, {"cents": 0, "count": 0, "event_types": set()})
        s_cents = s_entry["cents"]
        total = p_cents + s_cents
        if total == 0:
            continue
        avenue_breakdown.append(
            {
                "avenue_id": avenue_id,
                "display_name": avenue_id.replace("_", " ").title(),
                "recognized_cents_30d": total,
                "recognized_usd_30d": total / 100.0,
                "from_payments_cents": p_cents,
                "from_payments_count": payments_count_by_avenue.get(avenue_id, 0),
                "from_creator_events_cents": s_cents,
                "from_creator_events_count": s_entry["count"],
                "creator_event_types": sorted(s_entry["event_types"]),
            }
        )
    avenue_breakdown.sort(key=lambda b: -b["recognized_cents_30d"])

    strongest_avenue = avenue_breakdown[0] if avenue_breakdown else None

    # ── PLAN DATA (surfaced but NOT counted) ──────────────────────
    plan_data: list[dict] = []

    async def _plan_row(avenue_id: str, display: str, table: str, where: str, sum_col: str):
        cents = await _safe_sum(db, table, where, {"s": since}, sum_col=sum_col)
        if cents > 0:
            plan_data.append(
                {
                    "avenue_id": avenue_id,
                    "display_name": display,
                    "source_table": table,
                    "plan_cents_30d": cents,
                    "plan_usd_30d": cents / 100.0,
                    "note": "PLAN DATA — not counted in recognized revenue",
                }
            )

    await _plan_row(
        "high_ticket",
        "High-ticket deals (won)",
        "high_ticket_deals",
        "status='won' AND created_at >= :s",
        "COALESCE(deal_value_cents, 0)",
    )
    await _plan_row(
        "monetization_packs",
        "Monetization packs (credit_transactions)",
        "credit_transactions",
        "amount_cents > 0 AND created_at >= :s",
        "COALESCE(amount_cents, 0)",
    )
    await _plan_row(
        "monetization_packs",
        "Monetization packs (pack_purchases)",
        "pack_purchases",
        "created_at >= :s",
        "COALESCE(amount_cents, 0)",
    )
    await _plan_row(
        "external_affiliate",
        "External affiliate commissions",
        "af_commissions",
        "created_at >= :s",
        "COALESCE(amount_cents, 0)",
    )
    await _plan_row(
        "owned_affiliate",
        "Owned affiliate partner conversions",
        "af_own_partner_conversions",
        "created_at >= :s",
        "COALESCE(conversion_amount_cents, 0)",
    )
    await _plan_row(
        "sponsor_deals",
        "Sponsor deals (won)",
        "sponsor_opportunities",
        "status='won' AND created_at >= :s",
        "COALESCE(deal_amount_cents, 0)",
    )
    await _plan_row(
        "saas_subscriptions",
        "SaaS subscription payments",
        "subscription_events",
        "event_type='payment_succeeded' AND created_at >= :s",
        "COALESCE(amount_cents, 0)",
    )

    # ── Floor math ────────────────────────────────────────────────
    floor_cents = floor_for_month(month_index)
    gap_cents = max(0, floor_cents - recognized_total_cents)
    ratio = (recognized_total_cents / floor_cents) if floor_cents else 0.0
    projected_30d_cents = int(round((payments_7d_cents / 7.0) * 30))
    projected_ratio = (projected_30d_cents / floor_cents) if floor_cents else 0.0

    return {
        "generated_at": now.isoformat(),
        "window_days": 30,
        "org_id": str(org_id),
        "month_index": month_index,
        # Floor
        "floor_cents": floor_cents,
        "floor_usd": floor_cents / 100.0,
        "floor_met": recognized_total_cents >= floor_cents,
        "gap_cents": gap_cents,
        "gap_usd": gap_cents / 100.0,
        "ratio_to_floor": round(ratio, 4),
        "month_1_floor_cents": FLOOR_MONTH_1_CENTS,
        "month_12_floor_cents": FLOOR_MONTH_12_CENTS,
        # Recognized revenue (the ONLY total that counts toward the floor)
        "trailing_30d_cents": recognized_total_cents,
        "trailing_30d_usd": recognized_total_cents / 100.0,
        "recognized_revenue_breakdown": {
            "from_payments_cents": payments_total_cents,
            "from_payments_count": sum(payments_count_by_avenue.values()),
            "from_creator_events_cents": supplemental_total_cents,
            "from_creator_events_count": sum(b["count"] for b in supplemental_by_avenue.values()),
            "excluded_stripe_origin_events_count": excluded_stripe_origin_count,
            "excluded_stripe_origin_events_cents": excluded_stripe_origin_cents,
        },
        # Projection
        "last_7d_cents": payments_7d_cents,
        "projected_30d_cents_at_7d_runrate": projected_30d_cents,
        "projected_ratio_to_floor": round(projected_ratio, 4),
        # Per-avenue attribution
        "avenue_breakdown": avenue_breakdown,
        "strongest_avenue": strongest_avenue,
        # Plan data (not counted)
        "plan_data_ledgers": plan_data,
        # Canonical rule documentation
        "recognized_revenue_rule": (
            "Recognized revenue = payments.amount_cents (status=succeeded) "
            "+ creator_revenue_events.revenue for events NOT originating "
            "from Stripe or Shopify (excludes event_type IN "
            f"{sorted(STRIPE_ORIGIN_EVENT_TYPES)} or event_type LIKE "
            "'stripe_%%' or 'shopify_%%'). All other revenue-shaped tables "
            "are PLAN DATA and do not count toward the floor."
        ),
    }


def _tag_to_avenue_id(avenue_type_tag: str) -> str:
    """Map creator_revenue_events.avenue_type → doctrine avenue_id."""
    mapping = {
        "ugc_services": "ugc_services",
        "consulting": "consulting",
        "service_consulting": "consulting",
        "premium_access": "premium_access",
        "licensing": "licensing",
        "syndication": "syndication",
        "data_product": "data_products",
        "merch": "merchandise",
        "live_event": "live_events",
        "ecommerce": "ecommerce",
        "owned_affiliate": "owned_affiliate",
    }
    return mapping.get(avenue_type_tag, f"unmapped::{avenue_type_tag}")


async def _safe_sum(
    db: AsyncSession,
    table: str,
    where: str,
    params: dict,
    *,
    sum_col: str,
) -> int:
    """Sum ``sum_col`` from ``table`` with ``where`` clause, safely.

    Savepoint-protected: column-mismatches do not poison the outer txn.
    """
    if not await _table_exists(db, table):
        return 0
    try:
        async with db.begin_nested():
            res = await db.execute(
                text(f'SELECT COALESCE(SUM({sum_col}), 0) FROM "{table}" WHERE {where}'),
                params,
            )
            return int(res.scalar() or 0)
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
#  AVENUE PORTFOLIO — all 22 avenues, live-classified per call
# ═══════════════════════════════════════════════════════════════════════════


async def compute_avenue_portfolio(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
) -> dict:
    """Live portfolio of all 22 avenues.

    For each avenue, reports:
      - doctrine status (starting classification)
      - LIVE reclassification (based on current row counts)
      - revenue_tables row counts + trailing-30d revenue
      - activity_tables row counts + trailing-30d activity
      - unlock_plan (for LIVE_BUT_DORMANT)

    Also surfaces:
      - strongest avenue by 30d revenue
      - weakest but UNLOCKABLE avenue (LIVE_BUT_DORMANT with highest
        planned-activity count)
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    avenues_out: list[dict] = []

    for a in REVENUE_AVENUES:
        # Revenue: sum from revenue_tables
        revenue_cents_30d = 0
        revenue_total = 0
        revenue_detail: list[dict] = []
        for t in a["revenue_tables"]:
            total = await _count_table(db, t)
            last30 = await _recent_activity_cutoff(db, t, since)
            revenue_detail.append(
                {
                    "table": t,
                    "total_rows": total,
                    "rows_last_30d": last30,
                }
            )
            if total is not None:
                revenue_total += total
            if last30 is not None:
                revenue_cents_30d_table = 0
                # For payments: sum amount_cents succeeded 30d
                if t == "payments":
                    payments_sum = int(
                        (
                            await db.execute(
                                select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                                    Payment.org_id == org_id,
                                    Payment.status == "succeeded",
                                    Payment.completed_at >= since,
                                )
                            )
                        ).scalar()
                        or 0
                    )
                    revenue_cents_30d_table = payments_sum
                elif t == "creator_revenue_events" and a.get("revenue_avenue_tag"):
                    tag = a["revenue_avenue_tag"]
                    try:
                        res = (
                            await db.execute(
                                text(
                                    "SELECT COALESCE(SUM(revenue * 100)::bigint, 0) "
                                    "FROM creator_revenue_events "
                                    "WHERE avenue_type = :t AND created_at >= :s"
                                ),
                                {"t": tag, "s": since},
                            )
                        ).scalar()
                        revenue_cents_30d_table = int(res or 0)
                    except Exception:
                        revenue_cents_30d_table = 0
                revenue_cents_30d += revenue_cents_30d_table

        # Activity: total + 30d
        activity_total_rows = 0
        activity_rows_30d = 0
        activity_detail: list[dict] = []
        for t in a["activity_tables"]:
            total = await _count_table(db, t)
            last30 = await _recent_activity_cutoff(db, t, since)
            activity_detail.append(
                {
                    "table": t,
                    "total_rows": total,
                    "rows_last_30d": last30,
                }
            )
            if total is not None:
                activity_total_rows += total
            if last30 is not None:
                activity_rows_30d += last30

        # Live reclassification
        live_status = _reclassify_avenue(
            a,
            revenue_total_rows=revenue_total,
            revenue_cents_30d=revenue_cents_30d,
            activity_total_rows=activity_total_rows,
            activity_rows_30d=activity_rows_30d,
        )

        avenues_out.append(
            {
                "n": a["n"],
                "id": a["id"],
                "display_name": a["display_name"],
                "description": a["description"],
                "doctrine_status": a["status"],
                "live_status": live_status,
                "revenue_cents_30d": revenue_cents_30d,
                "revenue_usd_30d": revenue_cents_30d / 100.0,
                "revenue_tables": revenue_detail,
                "activity_total_rows": activity_total_rows,
                "activity_rows_30d": activity_rows_30d,
                "activity_tables": activity_detail,
                "unlock_plan": a.get("unlock_plan"),
                "revenue_avenue_tag": a.get("revenue_avenue_tag"),
            }
        )

    # Strongest + weakest unlockable
    strongest = max(
        (a for a in avenues_out if a["revenue_cents_30d"] > 0),
        key=lambda a: a["revenue_cents_30d"],
        default=None,
    )
    dormant = [a for a in avenues_out if a["live_status"] == STATUS_LIVE_BUT_DORMANT]
    weakest_unlockable = max(
        dormant,
        key=lambda a: a["activity_total_rows"],
        default=None,
    )

    # Status histogram
    status_histogram: dict[str, int] = {}
    for a in avenues_out:
        status_histogram[a["live_status"]] = status_histogram.get(a["live_status"], 0) + 1

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "window_days": 30,
        "total_avenues": len(avenues_out),
        "status_histogram": status_histogram,
        "strongest_avenue": strongest,
        "weakest_unlockable_avenue": weakest_unlockable,
        "avenues": avenues_out,
    }


def _reclassify_avenue(
    a: dict,
    *,
    revenue_total_rows: int,
    revenue_cents_30d: int,
    activity_total_rows: int,
    activity_rows_30d: int,
) -> str:
    """Classify an avenue's LIVE status from real row counts.

    Rules:
      - If doctrine says DISABLED_BY_OPERATOR → preserve.
      - revenue_cents_30d > 0 AND activity_rows_30d > 100 → VERY ACTIVE
      - revenue_cents_30d > 0 → ACTIVE
      - activity_total_rows > 100 (and revenue == 0) → LIVE_BUT_DORMANT
      - revenue_total_rows > 0 (seed data) → LIVE_BUT_DORMANT
      - activity_total_rows > 0 → LIVE_BUT_DORMANT
      - all zero → PRESENT_IN_CODE_ONLY
    """
    if a["status"] == STATUS_DISABLED_BY_OPERATOR:
        return STATUS_DISABLED_BY_OPERATOR
    if revenue_cents_30d > 0 and activity_rows_30d > 100:
        return STATUS_LIVE_AND_VERY_ACTIVE
    if revenue_cents_30d > 0:
        return STATUS_LIVE_AND_ACTIVE
    if activity_total_rows > 100:
        return STATUS_LIVE_BUT_DORMANT
    if revenue_total_rows > 0 or activity_total_rows > 0:
        return STATUS_LIVE_BUT_DORMANT
    return STATUS_PRESENT_IN_CODE_ONLY


# ═══════════════════════════════════════════════════════════════════════════
#  ENGINE STATUS — all 38 engines, live classified
# ═══════════════════════════════════════════════════════════════════════════


async def compute_engine_status(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
) -> dict:
    """Per-engine total row count + live status classification.

    Uses ``pg_stat_user_tables.n_live_tup`` — ONE batched query — for
    approximate row counts across every engine-referenced table. No
    per-table 30-day recency (that required 100+ sequential COUNT
    queries which killed the uvicorn worker on whole-machine inspection).

    Classification uses total_rows thresholds (high=500, active=50,
    dormant>0, zero=present-in-code-only) which is sufficient signal for
    "is this engine doing work" vs "is this engine dead". Per-table 30d
    recency is still available per-avenue via ``compute_avenue_portfolio``
    which operates on a much smaller table set.
    """
    now = datetime.now(timezone.utc)

    # Collect every table referenced by any engine
    all_tables: set[str] = set()
    for e in STRATEGIC_ENGINES:
        for t in e["tables"]:
            all_tables.add(t)

    # ONE query for approximate row counts across all engine tables
    table_counts: dict[str, int] = {}
    if all_tables:
        try:
            async with db.begin_nested():
                res = await db.execute(
                    text(
                        "SELECT relname, n_live_tup "
                        "FROM pg_stat_user_tables "
                        "WHERE schemaname = 'public' AND relname = ANY(:names)"
                    ),
                    {"names": list(all_tables)},
                )
                for row in res:
                    table_counts[row[0]] = int(row[1] or 0)
        except Exception as exc:
            logger_err = str(exc)[:200] if exc else ""
            return {
                "org_id": str(org_id),
                "generated_at": now.isoformat(),
                "total_engines": 0,
                "status_histogram": {},
                "family_histogram": {},
                "engines": [],
                "error": f"pg_stat_user_tables query failed: {logger_err}",
            }

    engines_out: list[dict] = []
    for e in STRATEGIC_ENGINES:
        total_rows = 0
        per_table: list[dict] = []
        for t in e["tables"]:
            total = table_counts.get(t, 0)
            per_table.append({"table": t, "total_rows": total})
            total_rows += total

        # Classification: total-rows thresholds (no 30d recency needed)
        if e["status"] == STATUS_DISABLED_BY_OPERATOR:
            live_status = STATUS_DISABLED_BY_OPERATOR
        elif total_rows >= 500:
            live_status = STATUS_LIVE_AND_VERY_ACTIVE
        elif total_rows >= 50:
            live_status = STATUS_LIVE_AND_ACTIVE
        elif total_rows > 0:
            live_status = STATUS_LIVE_BUT_DORMANT
        else:
            live_status = STATUS_PRESENT_IN_CODE_ONLY

        engines_out.append(
            {
                "id": e["id"],
                "family": e["family"],
                "purpose": e["purpose"],
                "doctrine_status": e["status"],
                "live_status": live_status,
                "total_rows": total_rows,
                "tables": per_table,
            }
        )

    status_hist: dict[str, int] = {}
    family_hist: dict[str, int] = {}
    for eo in engines_out:
        status_hist[eo["live_status"]] = status_hist.get(eo["live_status"], 0) + 1
        family_hist[eo["family"]] = family_hist.get(eo["family"], 0) + 1

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "total_engines": len(engines_out),
        "status_histogram": status_hist,
        "family_histogram": family_hist,
        "engines": engines_out,
        "count_source": "pg_stat_user_tables.n_live_tup (approximate; no 30d recency)",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  B2B pipeline state (preserved from 7A)
# ═══════════════════════════════════════════════════════════════════════════


async def compute_pipeline_state(db: AsyncSession, *, org_id: uuid.UUID) -> dict:
    """B2B-avenue stage entity counts (avenue 1)."""
    stages: list[dict] = []

    # Stage 4 — reply.received (pending drafts)
    s4 = await db.execute(
        select(func.count(EmailReplyDraft.id)).where(
            EmailReplyDraft.org_id == org_id,
            EmailReplyDraft.status == "pending",
            EmailReplyDraft.is_active.is_(True),
        )
    )
    stages.append(_stage_entry(4, "reply.received", int(s4.scalar() or 0)))

    # Stage 5 — proposal.ready (drafts)
    s5 = await db.execute(
        select(func.count(Proposal.id)).where(
            Proposal.org_id == org_id,
            Proposal.status == "draft",
            Proposal.is_active.is_(True),
        )
    )
    stages.append(_stage_entry(5, "proposal.ready", int(s5.scalar() or 0)))

    # Stage 6 — proposal.sent unpaid
    s6 = await db.execute(
        select(func.count(Proposal.id)).where(
            Proposal.org_id == org_id,
            Proposal.status == "sent",
            Proposal.is_active.is_(True),
        )
    )
    stages.append(_stage_entry(6, "proposal.sent", int(s6.scalar() or 0)))

    # Stage 7 — payments succeeded
    s7 = await db.execute(
        select(func.count(Payment.id)).where(
            Payment.org_id == org_id,
            Payment.status == "succeeded",
        )
    )
    clients_count = int((await db.execute(select(func.count(Client.id)).where(Client.org_id == org_id))).scalar() or 0)
    stages.append(_stage_entry(7, "payment.completed", {"payments": int(s7.scalar() or 0), "clients": clients_count}))

    # Stage 8 — intake pending
    s8 = await db.execute(
        select(func.count(IntakeRequest.id)).where(
            IntakeRequest.org_id == org_id,
            IntakeRequest.status.in_(("pending", "sent", "viewed")),
        )
    )
    stages.append(_stage_entry(8, "intake.pending", int(s8.scalar() or 0)))

    # Stage 9 — production running
    s9 = await db.execute(
        select(func.count(ProductionJob.id)).where(
            ProductionJob.org_id == org_id,
            ProductionJob.status == "running",
        )
    )
    stages.append(_stage_entry(9, "production.active", int(s9.scalar() or 0)))

    # Stage 10 — qa pending
    s10 = await db.execute(
        select(func.count(ProductionJob.id)).where(
            ProductionJob.org_id == org_id,
            ProductionJob.status == "qa_pending",
        )
    )
    stages.append(_stage_entry(10, "qa", int(s10.scalar() or 0)))

    # Stage 11 — delivery pending
    s11 = await db.execute(
        select(func.count(ProductionJob.id)).where(
            ProductionJob.org_id == org_id,
            ProductionJob.status == "qa_passed",
        )
    )
    stages.append(_stage_entry(11, "delivery", int(s11.scalar() or 0)))

    def _numeric(v):
        if isinstance(v, dict):
            return sum(int(x) for x in v.values() if isinstance(x, (int, float)))
        try:
            return int(v)
        except Exception:
            return 0

    worst = max(stages, key=lambda s: _numeric(s["count"])) if stages else None
    return {
        "org_id": str(org_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "avenue_id": "b2b_services",
        "stages": stages,
        "bottleneck": worst,
    }


def _stage_entry(n: int, name: str, count: Any) -> dict:
    spec = next((s for s in STAGE_MACHINE if s["n"] == n), None)
    return {
        "stage": n,
        "name": name,
        "count": count,
        "timeout_minutes": spec["timeout_minutes"] if spec else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Bottlenecks — stuck stage_states
# ═══════════════════════════════════════════════════════════════════════════


async def compute_bottlenecks(db: AsyncSession, *, org_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    rows = (
        (
            await db.execute(
                select(StageState)
                .where(
                    StageState.org_id == org_id,
                    StageState.is_active.is_(True),
                    StageState.sla_deadline.is_not(None),
                )
                .order_by(StageState.sla_deadline.asc())
            )
        )
        .scalars()
        .all()
    )
    ranked = []
    for s in rows:
        overdue_minutes = None
        if s.sla_deadline:
            overdue_minutes = int((now - s.sla_deadline).total_seconds() // 60)
        status = "stuck" if s.is_stuck else ("overdue" if (overdue_minutes and overdue_minutes > 0) else "on_track")
        ranked.append(
            {
                "entity_type": s.entity_type,
                "entity_id": str(s.entity_id),
                "stage": s.stage,
                "entered_at": s.entered_at.isoformat() if s.entered_at else None,
                "sla_deadline": s.sla_deadline.isoformat() if s.sla_deadline else None,
                "overdue_minutes": overdue_minutes,
                "status": status,
                "stuck_reason": s.stuck_reason,
            }
        )
    ranked.sort(key=lambda r: (not (r["status"] == "stuck"), -(r["overdue_minutes"] or 0)))
    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "total_tracked": len(ranked),
        "total_stuck": sum(1 for r in ranked if r["status"] == "stuck"),
        "total_overdue": sum(1 for r in ranked if r["status"] in ("stuck", "overdue")),
        "ranked": ranked[:50],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Closest revenue — multi-avenue now
# ═══════════════════════════════════════════════════════════════════════════


async def compute_closest_revenue(db: AsyncSession, *, org_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)

    # A — sent proposals not yet paid (B2B)
    A = []
    A_rows = (
        (
            await db.execute(
                select(Proposal)
                .where(
                    Proposal.org_id == org_id,
                    Proposal.status == "sent",
                    Proposal.is_active.is_(True),
                )
                .order_by(Proposal.total_amount_cents.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    for p in A_rows:
        A.append(
            {
                "type": "proposal_sent_unpaid",
                "avenue_id": "b2b_services",
                "proposal_id": str(p.id),
                "recipient_email": p.recipient_email,
                "amount_cents": p.total_amount_cents,
                "sent_at": p.sent_at.isoformat() if p.sent_at else None,
                "hours_since_sent": (int((now - p.sent_at).total_seconds() // 3600) if p.sent_at else None),
            }
        )

    # B — pending drafts with money-intent
    money_intents = ("pricing_request", "warm_interest", "negotiation")
    B_rows = (
        await db.execute(
            select(EmailReplyDraft, EmailClassification)
            .join(EmailClassification, EmailClassification.id == EmailReplyDraft.classification_id, isouter=True)
            .where(
                EmailReplyDraft.org_id == org_id,
                EmailReplyDraft.status == "pending",
                EmailReplyDraft.is_active.is_(True),
                EmailClassification.intent.in_(money_intents),
            )
            .limit(25)
        )
    ).all()
    B = [
        {
            "type": "draft_pending_money_intent",
            "avenue_id": "b2b_services",
            "draft_id": str(d.id),
            "to_email": d.to_email,
            "intent": c.intent if c else None,
            "confidence": float(c.confidence) if c else None,
        }
        for d, c in B_rows
    ]

    # C — approved drafts awaiting send
    C_rows = (
        (
            await db.execute(
                select(EmailReplyDraft)
                .where(
                    EmailReplyDraft.org_id == org_id,
                    EmailReplyDraft.status == "approved",
                    EmailReplyDraft.is_active.is_(True),
                )
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    C = [
        {
            "type": "draft_approved_pending_send",
            "avenue_id": "b2b_services",
            "draft_id": str(d.id),
            "to_email": d.to_email,
        }
        for d in C_rows
    ]

    # D — intakes sent unsubmitted
    D_rows = (
        (
            await db.execute(
                select(IntakeRequest)
                .where(
                    IntakeRequest.org_id == org_id,
                    IntakeRequest.status.in_(("sent", "viewed")),
                    IntakeRequest.is_active.is_(True),
                )
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    D = [
        {
            "type": "intake_sent_not_submitted",
            "avenue_id": "b2b_services",
            "intake_id": str(i.id),
            "client_id": str(i.client_id),
        }
        for i in D_rows
    ]

    # E — sponsor outreach sequences in-flight (avenue 17 proxy)
    E_count = await _count_table(db, "sponsor_outreach_sequences") or 0
    E = (
        [
            {
                "type": "sponsor_outreach_in_flight",
                "avenue_id": "sponsor_deals",
                "count": E_count,
            }
        ]
        if E_count > 0
        else []
    )

    # F — high-ticket opportunities ready to close
    F_count = await _count_table(db, "high_ticket_opportunities") or 0
    F = (
        [
            {
                "type": "high_ticket_opportunity",
                "avenue_id": "high_ticket",
                "count": F_count,
            }
        ]
        if F_count > 0
        else []
    )

    total_potential = sum(x.get("amount_cents", 0) or 0 for x in A)

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "total_potential_cents": total_potential,
        "total_potential_usd": total_potential / 100.0,
        "buckets": {
            "proposal_sent_unpaid": A,
            "draft_pending_money_intent": B,
            "draft_approved_pending_send": C,
            "intake_sent_not_submitted": D,
            "sponsor_outreach_in_flight": E,
            "high_ticket_opportunity": F,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Blocking floors
# ═══════════════════════════════════════════════════════════════════════════


async def compute_blocking_floors(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    floor = await compute_floor_status(db, org_id=org_id, month_index=month_index)
    closest = await compute_closest_revenue(db, org_id=org_id)

    gap_cents = int(floor["gap_cents"])
    potential_cents = int(closest["total_potential_cents"])
    ratio_with_inflight = (
        ((floor["trailing_30d_cents"] + potential_cents) / floor["floor_cents"]) if floor["floor_cents"] else 0.0
    )

    reasons = []
    if floor["floor_met"]:
        reasons.append("Floor met. Advance to next month's floor target.")
    else:
        if gap_cents > potential_cents:
            reasons.append(
                f"In-flight potential (${potential_cents / 100:.0f}) is less than "
                f"the floor gap (${gap_cents / 100:.0f}). New outreach/leads + "
                f"dormant-avenue activation required."
            )
        if not closest["buckets"]["proposal_sent_unpaid"]:
            reasons.append("No proposals in 'sent' state — revenue engine has no in-flight closes.")
        if not closest["buckets"]["draft_pending_money_intent"]:
            reasons.append("No money-intent replies pending — inbound is quiet.")

    return {
        "org_id": str(org_id),
        "month_index": month_index,
        "floor_usd": floor["floor_usd"],
        "trailing_30d_usd": floor["trailing_30d_usd"],
        "gap_usd": floor["gap_usd"],
        "in_flight_potential_usd": potential_cents / 100.0,
        "ratio_to_floor": floor["ratio_to_floor"],
        "ratio_if_all_in_flight_closes": round(ratio_with_inflight, 4),
        "blocker_reasons": reasons,
        "floor_met": floor["floor_met"],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Ask operator — what GM needs from the operator to succeed
# ═══════════════════════════════════════════════════════════════════════════


async def compute_ask_operator(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    """Concrete list of operator inputs GM needs right now.

    Categories:
      - activation decisions (LIVE_BUT_DORMANT avenues awaiting unlock)
      - code-only avenues awaiting first activation step
      - critical provider credentials missing
      - pending approvals awaiting operator decision
      - open escalations needing operator attention
      - budget/authority decisions
    """
    now = datetime.now(timezone.utc)
    asks: list[dict] = []

    # Pending approvals (operator must decide)
    pending_approvals = (
        (
            await db.execute(
                select(GMApproval)
                .where(
                    GMApproval.org_id == org_id,
                    GMApproval.status == "pending",
                    GMApproval.is_active.is_(True),
                )
                .order_by(GMApproval.created_at.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    for a in pending_approvals:
        asks.append(
            {
                "category": "approval_decision",
                "priority": 1,
                "request": f"Approve/reject: {a.title}",
                "context": a.description or "",
                "risk_level": a.risk_level,
                "entity_type": "gm_approval",
                "entity_id": str(a.id),
            }
        )

    # Open escalations needing attention
    open_escalations = (
        (
            await db.execute(
                select(GMEscalation)
                .where(
                    GMEscalation.org_id == org_id,
                    GMEscalation.status.in_(("open", "acknowledged")),
                    GMEscalation.is_active.is_(True),
                )
                .order_by(GMEscalation.last_seen_at.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    for e in open_escalations:
        asks.append(
            {
                "category": "escalation_resolution",
                "priority": 2,
                "request": f"Resolve escalation: {e.title}",
                "context": e.description or "",
                "severity": e.severity,
                "entity_type": "gm_escalation",
                "entity_id": str(e.id),
            }
        )

    # Dormant-avenue activations: list LIVE_BUT_DORMANT avenues with highest activity_total
    portfolio = await compute_avenue_portfolio(db, org_id=org_id)
    dormant_avenues = sorted(
        (a for a in portfolio["avenues"] if a["live_status"] == STATUS_LIVE_BUT_DORMANT),
        key=lambda a: a["activity_total_rows"],
        reverse=True,
    )[:5]
    for a in dormant_avenues:
        asks.append(
            {
                "category": "dormant_avenue_activation",
                "priority": 3,
                "request": (
                    f"Approve activation of avenue {a['n']} ({a['display_name']}) — "
                    f"{a['activity_total_rows']} planned actions, no realized revenue yet."
                ),
                "context": a.get("description", ""),
                "avenue_id": a["id"],
                "unlock_plan": a.get("unlock_plan") or [],
            }
        )

    # Code-only avenues: need operator decision on whether to build the activation
    code_only = [a for a in portfolio["avenues"] if a["live_status"] == STATUS_PRESENT_IN_CODE_ONLY]
    for a in code_only:
        asks.append(
            {
                "category": "code_only_avenue_activation",
                "priority": 4,
                "request": (
                    f"Decide on avenue {a['n']} ({a['display_name']}): "
                    "should we activate it? First step of unlock plan is needed."
                ),
                "avenue_id": a["id"],
                "unlock_plan": a.get("unlock_plan") or [],
            }
        )

    # Missing critical provider credentials
    critical_providers = ("stripe_webhook", "inbound_email_route", "smtp", "anthropic")
    for key in critical_providers:
        count = (
            await db.execute(
                select(func.count(IntegrationProvider.id)).where(
                    IntegrationProvider.organization_id == org_id,
                    IntegrationProvider.provider_key == key,
                    IntegrationProvider.is_enabled.is_(True),
                )
            )
        ).scalar() or 0
        if count == 0:
            asks.append(
                {
                    "category": "missing_credential",
                    "priority": 2,
                    "request": f"Configure {key} integration_providers row — currently absent or disabled.",
                    "provider_key": key,
                }
            )

    # Floor-budget: if below floor, ask operator for activation authority + budget
    floor = await compute_floor_status(db, org_id=org_id, month_index=month_index)
    if not floor["floor_met"]:
        asks.append(
            {
                "category": "budget_authority",
                "priority": 1,
                "request": (
                    f"Floor M{month_index} not met: ${floor['trailing_30d_usd']:.0f} / "
                    f"${floor['floor_usd']:.0f}. Grant GM authority to activate "
                    f"top dormant avenues and/or increase paid promotion budget."
                ),
                "gap_usd": floor["gap_usd"],
                "ratio": floor["ratio_to_floor"],
            }
        )

    # Sort by priority
    asks.sort(key=lambda x: x["priority"])

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "total_asks": len(asks),
        "by_category": _bucket_count(asks, "category"),
        "asks": asks,
    }


def _bucket_count(items: list[dict], key: str) -> dict:
    out: dict = {}
    for i in items:
        k = i.get(key, "_")
        out[k] = out.get(k, 0) + 1
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Unlock plans — canonical plans for every LIVE_BUT_DORMANT avenue
# ═══════════════════════════════════════════════════════════════════════════


async def compute_unlock_plans(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
) -> dict:
    portfolio = await compute_avenue_portfolio(db, org_id=org_id)
    dormant = [a for a in portfolio["avenues"] if a["live_status"] == STATUS_LIVE_BUT_DORMANT]
    code_only = [a for a in portfolio["avenues"] if a["live_status"] == STATUS_PRESENT_IN_CODE_ONLY]

    plans = []
    for a in dormant + code_only:
        plans.append(
            {
                "avenue_id": a["id"],
                "n": a["n"],
                "display_name": a["display_name"],
                "live_status": a["live_status"],
                "activity_total_rows": a["activity_total_rows"],
                "revenue_cents_30d": a["revenue_cents_30d"],
                "plan": a.get("unlock_plan") or ["No canonical unlock plan in doctrine — request one via operator."],
                "action_class": "approval_required",
            }
        )

    # Rank by dormant before code-only, then by activity_total desc
    plans.sort(
        key=lambda p: (
            p["live_status"] != STATUS_LIVE_BUT_DORMANT,  # dormant first
            -p["activity_total_rows"],
        )
    )

    return {
        "org_id": str(org_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_unlock_candidates": len(plans),
        "plans": plans,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Game plan — FULL-MACHINE priority-ranked action list
# ═══════════════════════════════════════════════════════════════════════════


async def compute_game_plan(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    now = datetime.now(timezone.utc)
    plan: list[dict] = []

    # Rank 1 — revenue at immediate risk (B2B proposals unpaid > 24h)
    risky = (
        (
            await db.execute(
                select(Proposal)
                .where(
                    Proposal.org_id == org_id,
                    Proposal.status == "sent",
                    Proposal.is_active.is_(True),
                    Proposal.sent_at <= (now - timedelta(hours=24)),
                )
                .order_by(Proposal.total_amount_cents.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    for p in risky:
        plan.append(
            {
                "priority_rank": 1,
                "label": "revenue_at_immediate_risk",
                "action_type": "followup_unpaid_proposal",
                "action_class": "approval_required",
                "avenue_id": "b2b_services",
                "entity_type": "proposal",
                "entity_id": str(p.id),
                "detail": f"Proposal to {p.recipient_email} ${p.total_amount_cents / 100:.0f} unpaid "
                f"{int((now - p.sent_at).total_seconds() // 3600)}h.",
                "potential_cents": p.total_amount_cents,
            }
        )

    # Rank 2 — blocked revenue close
    stale = (
        (
            await db.execute(
                select(EmailReplyDraft)
                .where(
                    EmailReplyDraft.org_id == org_id,
                    EmailReplyDraft.status == "approved",
                    EmailReplyDraft.approved_at <= (now - timedelta(minutes=5)),
                    EmailReplyDraft.is_active.is_(True),
                )
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    for d in stale:
        plan.append(
            {
                "priority_rank": 2,
                "label": "blocked_revenue_close",
                "action_type": "dispatch_approved_draft",
                "action_class": "auto_execute",
                "avenue_id": "b2b_services",
                "entity_type": "email_reply_draft",
                "entity_id": str(d.id),
                "detail": f"Draft to {d.to_email} approved — beat cycle should have fired.",
            }
        )

    undelivered = (
        (
            await db.execute(
                select(ProductionJob)
                .where(
                    ProductionJob.org_id == org_id,
                    ProductionJob.status == "qa_passed",
                    ProductionJob.is_active.is_(True),
                )
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    for j in undelivered:
        plan.append(
            {
                "priority_rank": 2,
                "label": "blocked_revenue_close",
                "action_type": "dispatch_delivery",
                "action_class": "auto_execute",
                "avenue_id": "b2b_services",
                "entity_type": "production_job",
                "entity_id": str(j.id),
                "detail": f"Job {j.id} qa_passed, awaiting delivery.",
            }
        )

    # Rank 3 — floor gap
    floor = await compute_floor_status(db, org_id=org_id, month_index=month_index)
    if not floor["floor_met"]:
        plan.append(
            {
                "priority_rank": 3,
                "label": "floor_gap_math",
                "action_type": "close_floor_gap",
                "action_class": "approval_required",
                "avenue_id": "multi",
                "entity_type": "floor",
                "entity_id": f"month_{month_index}",
                "detail": (
                    f"Trailing 30d: ${floor['trailing_30d_usd']:.0f} (across {len(floor['avenue_breakdown'])} "
                    f"avenues) vs ${floor['floor_usd']:.0f} floor. Gap ${floor['gap_usd']:.0f}."
                ),
                "potential_cents": floor["gap_cents"],
            }
        )

    # Rank 4 — dormant + code-only avenue activation (both are unlockable)
    portfolio = await compute_avenue_portfolio(db, org_id=org_id)
    unlockable = [
        a for a in portfolio["avenues"] if a["live_status"] in (STATUS_LIVE_BUT_DORMANT, STATUS_PRESENT_IN_CODE_ONLY)
    ]
    # LIVE_BUT_DORMANT first (more ready), then by activity_total desc
    unlockable.sort(
        key=lambda a: (
            a["live_status"] != STATUS_LIVE_BUT_DORMANT,  # dormant first
            -a["activity_total_rows"],
        )
    )
    for a in unlockable[:10]:  # top 10, not 5 — more avenues, more surface
        plan.append(
            {
                "priority_rank": 4,
                "label": "dormant_avenue_activation",
                "action_type": "activate_dormant_avenue",
                "action_class": "approval_required",
                "avenue_id": a["id"],
                "entity_type": "avenue",
                "entity_id": a["id"],
                "live_status": a["live_status"],
                "detail": (
                    f"Avenue {a['n']} {a['display_name']} [{a['live_status']}]: "
                    f"{a['activity_total_rows']} planned actions, "
                    f"zero realized revenue. "
                    f"{'Canonical unlock plan available.' if a.get('unlock_plan') else 'No doctrine unlock plan yet.'}"
                ),
                "unlock_plan": a.get("unlock_plan") or [],
            }
        )

    # Rank 5 — stuck fulfillment (escalations)
    stuck = (
        (
            await db.execute(
                select(GMEscalation)
                .where(
                    GMEscalation.org_id == org_id,
                    GMEscalation.status.in_(("open", "acknowledged")),
                    GMEscalation.is_active.is_(True),
                )
                .order_by(GMEscalation.last_seen_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    for e in stuck:
        plan.append(
            {
                "priority_rank": 5,
                "label": "stuck_fulfillment",
                "action_type": "resolve_escalation",
                "action_class": "approval_required",
                "avenue_id": "b2b_services",
                "entity_type": "gm_escalation",
                "entity_id": str(e.id),
                "detail": f"{e.reason_code}: {e.title}",
            }
        )

    # Rank 6 — retention (stale clients)
    stale_clients = (
        (
            await db.execute(
                select(Client)
                .where(
                    Client.org_id == org_id,
                    Client.is_active.is_(True),
                    Client.status == "active",
                    Client.last_paid_at <= (now - timedelta(days=30)),
                )
                .order_by(Client.total_paid_cents.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    for c in stale_clients:
        plan.append(
            {
                "priority_rank": 6,
                "label": "retention_expansion",
                "action_type": "propose_next_project_or_retainer",
                "action_class": "approval_required",
                "avenue_id": "recurring_revenue",
                "entity_type": "client",
                "entity_id": str(c.id),
                "detail": f"Client {c.display_name} (LTV ${c.total_paid_cents / 100:.0f}) "
                f"paid "
                f"{int((now - c.last_paid_at).total_seconds() // 86400) if c.last_paid_at else '?'}d ago.",
            }
        )

    # Rank 7 — pending approvals (hygiene)
    pend = (
        (
            await db.execute(
                select(GMApproval)
                .where(
                    GMApproval.org_id == org_id,
                    GMApproval.status == "pending",
                    GMApproval.is_active.is_(True),
                )
                .order_by(GMApproval.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    for a in pend:
        plan.append(
            {
                "priority_rank": 7,
                "label": "operational_hygiene",
                "action_type": "decide_pending_approval",
                "action_class": "approval_required",
                "avenue_id": "b2b_services",
                "entity_type": "gm_approval",
                "entity_id": str(a.id),
                "detail": f"{a.action_type}: {a.title}",
            }
        )

    plan.sort(key=lambda i: (i["priority_rank"], -(i.get("potential_cents") or 0)))

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "month_index": month_index,
        "total_items": len(plan),
        "floor_status": floor,
        "actions": plan,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Batch 11 — retention book (GM read surface)
# ═══════════════════════════════════════════════════════════════════════════


async def compute_retention_book(db, org_id) -> dict:
    """Thin re-export of ``retention_service.compute_retention_book``
    so GM read callers can pull it alongside game_plan / ask_operator /
    avenue_portfolio without a cross-module import."""
    from apps.api.services.retention_service import (
        compute_retention_book as svc,
    )

    return await svc(db, org_id=org_id)
