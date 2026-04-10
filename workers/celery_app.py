"""Celery application configuration with split queues and beat schedule."""
import asyncio
import os

from celery import Celery
from celery.schedules import crontab

# ---------------------------------------------------------------------------
# Patch asyncio.run for Celery workers: dispose async DB pool after each run.
#
# Problem: Workers call asyncio.run(some_async_task()). When the event loop
# is destroyed, any asyncpg connections borrowed from the SQLAlchemy pool
# are abandoned mid-transaction (the ROLLBACK never reaches postgres).
# These pile up as "idle in transaction" on the postgres side.
#
# Fix: After each asyncio.run(), dispose the async engine's pool so all
# connections are properly closed with ROLLBACK before the loop dies.
# ---------------------------------------------------------------------------
_original_asyncio_run = asyncio.run


def _patched_asyncio_run(coro, **kwargs):
    """asyncio.run replacement that reuses a persistent event loop.

    Standard asyncio.run() creates and destroys a loop each time.
    With asyncpg, destroying the loop orphans TCP connections mid-transaction
    ('idle in transaction' on postgres). This patch reuses a single loop
    per worker process so connections stay valid and get properly returned
    to the pool with ROLLBACK via _AutoRollbackSession.close().
    """
    from packages.db.session import _get_worker_loop
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)


# Apply the patch immediately at import time — this module is loaded by
# every worker process before any task modules.
asyncio.run = _patched_asyncio_run

# Also register a Celery worker_process_init signal to re-apply in case
# of prefork worker pool (each child re-imports).
from celery.signals import worker_process_init

@worker_process_init.connect
def _patch_asyncio_on_fork(**kwargs):
    import asyncio as _asyncio
    _asyncio.run = _patched_asyncio_run

broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

app = Celery(
    "avatar_revenue_os",
    broker=broker_url,
    backend=result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=86400,
    task_default_queue="default",
    task_queues={
        "default": {},
        "generation": {},
        "publishing": {},
        "analytics": {},
        "qa": {},
        "learning": {},
        "portfolio": {},
        "scale_alerts": {},
        "notifications": {},
        "growth_pack": {},
        "revenue_ceiling_a": {},
        "revenue_ceiling_b": {},
        "revenue_ceiling_c": {},
        "expansion_pack2": {},
        "mxp": {},
        "autonomous_phase_d": {},
        "brain": {},
        "buffer": {},
        "cinema_studio": {},
        "monetization": {},
        "pipeline": {},
        "repurposing": {},
        "strategy_adjustment": {},
        "outreach": {},
        "express_publishing": {
            "queue_arguments": {"x-max-priority": 10},
        },
    },
    task_routes={
        "workers.publishing_worker.express_publish": {"queue": "express_publishing"},
        "workers.generation_worker.*": {"queue": "generation"},
        "workers.publishing_worker.*": {"queue": "publishing"},
        "workers.analytics_worker.*": {"queue": "analytics"},
        "workers.qa_worker.*": {"queue": "qa"},
        "workers.learning_worker.*": {"queue": "learning"},
        "workers.portfolio_worker.*": {"queue": "portfolio"},
        "workers.scale_alerts_worker.tasks.process_notification_deliveries": {"queue": "notifications"},
        "workers.scale_alerts_worker.*": {"queue": "scale_alerts"},
        "workers.growth_pack_worker.*": {"queue": "growth_pack"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_offer_ladders": {"queue": "revenue_ceiling_a"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_owned_audience": {"queue": "revenue_ceiling_a"},
        "workers.revenue_ceiling_worker.tasks.refresh_all_message_sequences": {"queue": "revenue_ceiling_a"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_funnel_leaks": {"queue": "revenue_ceiling_a"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_high_ticket": {"queue": "revenue_ceiling_b"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_product_opportunities": {"queue": "revenue_ceiling_b"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_revenue_density": {"queue": "revenue_ceiling_b"},
        "workers.revenue_ceiling_worker.tasks.refresh_all_upsell_recommendations": {"queue": "revenue_ceiling_b"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_recurring_revenue": {"queue": "revenue_ceiling_c"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_inventory": {"queue": "revenue_ceiling_c"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_trust_conversion": {"queue": "revenue_ceiling_c"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_monetization_mix": {"queue": "revenue_ceiling_c"},
        "workers.revenue_ceiling_worker.tasks.refresh_all_paid_promotion_candidates": {"queue": "revenue_ceiling_c"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_lead_qualification": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_owned_offer_recommendations": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_pricing_recommendations": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_bundle_recommendations": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_retention_recommendations": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_reactivation_campaigns": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_referral_program_recommendations": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_competitive_gap_reports": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_targets": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_outreach_sequences": {"queue": "expansion_pack2"},
        "workers.revenue_ceiling_worker.tasks.recompute_all_profit_guardrail_reports": {"queue": "expansion_pack2"},
        "workers.mxp_worker.*": {"queue": "mxp"},
        "workers.action_executor_worker.*": {"queue": "default"},
        "workers.autonomous_phase_a_worker.*": {"queue": "default"},
        "workers.autonomous_phase_b_worker.*": {"queue": "default"},
        "workers.autonomous_phase_c_worker.*": {"queue": "default"},
        "workers.autonomous_phase_d_worker.*": {"queue": "autonomous_phase_d"},
        "workers.brain_worker.*": {"queue": "brain"},
        "workers.buffer_worker.*": {"queue": "buffer"},
        "workers.cinema_studio_worker.*": {"queue": "cinema_studio"},
        "workers.monetization_worker.*": {"queue": "monetization"},
        "workers.pipeline_worker.*": {"queue": "pipeline"},
        "workers.repurposing_worker.*": {"queue": "repurposing"},
        "workers.strategy_adjustment_worker.*": {"queue": "strategy_adjustment"},
        "workers.outreach_worker.*": {"queue": "outreach"},
    },
    beat_schedule={
        # RECOMPUTE DEPENDENCY ORDER:
        # 1. Analytics (ingest_performance → populates PerformanceMetric, the keystone table)
        # 2. Portfolio (reads PerformanceMetric)
        # 3. Scale (reads PerformanceMetric, accounts, offers)
        # 4. Scale Alerts (reads scale recs)
        # 5. Growth Pack (reads scale recs, candidates, blockers, readiness)
        # 6. Revenue Ceiling / Expansion Packs (reads offers, content, metrics)
        # 7. MXP (reads audience segments from growth, offers, metrics)
        # 8. Action Executor (reads pending actions from ALL modules above, executes)
        # 9. Notifications (delivers alerts generated by all of the above)
        #
        # --- Analytics ---
        "trend-scan-every-hour": {
            "task": "workers.analytics_worker.tasks.scan_trends",
            "schedule": crontab(minute=0),
        },
        "performance-ingest-every-30-min": {
            "task": "workers.analytics_worker.tasks.ingest_performance",
            "schedule": crontab(minute="*/30"),
        },
        "saturation-check-every-6h": {
            "task": "workers.analytics_worker.tasks.check_saturation",
            "schedule": crontab(hour="*/6", minute=15),
        },
        # --- Portfolio ---
        "portfolio-rebalance-daily": {
            "task": "workers.portfolio_worker.tasks.rebalance_portfolios",
            "schedule": crontab(hour=6, minute=0),
        },
        # --- Learning ---
        "learning-consolidate-daily": {
            "task": "workers.learning_worker.tasks.consolidate_memory",
            "schedule": crontab(hour=3, minute=0),
        },
        # --- Scale Alerts ---
        "scale-alerts-every-4h": {
            "task": "workers.scale_alerts_worker.tasks.recompute_all_alerts",
            "schedule": crontab(hour="*/4", minute=30),
        },
        "scale-launch-candidates-every-4h": {
            "task": "workers.scale_alerts_worker.tasks.recompute_all_launch_candidates",
            "schedule": crontab(hour="*/4", minute=40),
        },
        "scale-blockers-every-4h": {
            "task": "workers.scale_alerts_worker.tasks.recompute_all_blockers",
            "schedule": crontab(hour="*/4", minute=50),
        },
        "launch-readiness-every-4h": {
            "task": "workers.scale_alerts_worker.tasks.recompute_all_readiness",
            "schedule": crontab(hour="*/4", minute=55),
        },
        # --- Notifications (own queue) ---
        "notification-delivery-every-15m": {
            "task": "workers.scale_alerts_worker.tasks.process_notification_deliveries",
            "schedule": crontab(minute="*/15"),
        },
        # --- Growth Pack ---
        "growth-pack-recompute-every-6h": {
            "task": "workers.growth_pack_worker.tasks.recompute_all_growth_pack",
            "schedule": crontab(hour="*/6", minute=20),
        },
        # --- Revenue Ceiling A ---
        "rc-a-offer-ladders-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_offer_ladders",
            "schedule": crontab(hour="*/6", minute=5),
        },
        "rc-a-owned-audience-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_owned_audience",
            "schedule": crontab(hour="*/6", minute=10),
        },
        "rc-a-sequences-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.refresh_all_message_sequences",
            "schedule": crontab(hour="*/12", minute=25),
        },
        "rc-a-funnel-leaks-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_funnel_leaks",
            "schedule": crontab(hour="*/6", minute=35),
        },
        # --- Revenue Ceiling B ---
        "rc-b-high-ticket-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_high_ticket",
            "schedule": crontab(hour="*/6", minute=45),
        },
        "rc-b-product-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_product_opportunities",
            "schedule": crontab(hour="*/6", minute=50),
        },
        "rc-b-density-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_revenue_density",
            "schedule": crontab(hour="*/6", minute=55),
        },
        "rc-b-upsell-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.refresh_all_upsell_recommendations",
            "schedule": crontab(hour="*/12", minute=40),
        },
        # --- Revenue Ceiling C ---
        "rc-c-recurring-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_recurring_revenue",
            "schedule": crontab(hour="*/8", minute=5),
        },
        "rc-c-sponsor-inventory-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_inventory",
            "schedule": crontab(hour="*/8", minute=15),
        },
        "rc-c-trust-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_trust_conversion",
            "schedule": crontab(hour="*/12", minute=20),
        },
        "rc-c-mix-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_monetization_mix",
            "schedule": crontab(hour="*/12", minute=30),
        },
        "rc-c-paid-promo-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.refresh_all_paid_promotion_candidates",
            "schedule": crontab(hour="*/6", minute=58),
        },
        # --- Expansion Pack 2 ---
        "ep2a-lead-qualification-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_lead_qualification",
            "schedule": crontab(hour="*/6", minute=2),
        },
        "ep2a-owned-offer-recs-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_owned_offer_recommendations",
            "schedule": crontab(hour="*/8", minute=8),
        },
        "ep2b-pricing-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_pricing_recommendations",
            "schedule": crontab(hour="*/8", minute=12),
        },
        "ep2b-bundles-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_bundle_recommendations",
            "schedule": crontab(hour="*/12", minute=18),
        },
        "ep2b-retention-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_retention_recommendations",
            "schedule": crontab(hour="*/6", minute=22),
        },
        "ep2b-reactivation-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_reactivation_campaigns",
            "schedule": crontab(hour="*/12", minute=35),
        },
        "ep2c-referral-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_referral_program_recommendations",
            "schedule": crontab(hour="*/8", minute=10),
        },
        "ep2c-competitive-gaps-every-12h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_competitive_gap_reports",
            "schedule": crontab(hour="*/12", minute=25),
        },
        "ep2c-sponsor-targets-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_targets",
            "schedule": crontab(hour="*/8", minute=28),
        },
        "ep2c-sponsor-outreach-every-8h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_outreach_sequences",
            "schedule": crontab(hour="*/8", minute=32),
        },
        "ep2c-profit-guardrails-every-6h": {
            "task": "workers.revenue_ceiling_worker.tasks.recompute_all_profit_guardrail_reports",
            "schedule": crontab(hour="*/6", minute=45),
        },
        # --- Maximum-Strength Pack ---
        "mxp-experiment-decisions-every-6h": {
            "task": "workers.mxp_worker.tasks.recompute_all_experiment_decisions",
            "schedule": crontab(hour="*/6", minute=3),
        },
        "mxp-contribution-every-8h": {
            "task": "workers.mxp_worker.tasks.recompute_all_contribution_reports",
            "schedule": crontab(hour="*/8", minute=9),
        },
        "mxp-capacity-every-6h": {
            "task": "workers.mxp_worker.tasks.recompute_all_capacity",
            "schedule": crontab(hour="*/6", minute=14),
        },
        "mxp-offer-lifecycle-every-8h": {
            "task": "workers.mxp_worker.tasks.recompute_all_offer_lifecycle",
            "schedule": crontab(hour="*/8", minute=19),
        },
        "mxp-creative-memory-every-12h": {
            "task": "workers.mxp_worker.tasks.recompute_all_creative_memory",
            "schedule": crontab(hour="*/12", minute=24),
        },
        "mxp-recovery-every-4h": {
            "task": "workers.mxp_worker.tasks.recompute_all_recovery_incidents",
            "schedule": crontab(hour="*/4", minute=33),
        },
        "mxp-deal-desk-every-8h": {
            "task": "workers.mxp_worker.tasks.recompute_all_deal_desk",
            "schedule": crontab(hour="*/8", minute=38),
        },
        "mxp-audience-states-every-8h": {
            "task": "workers.mxp_worker.tasks.recompute_all_audience_states",
            "schedule": crontab(hour="*/8", minute=43),
        },
        "mxp-reputation-every-12h": {
            "task": "workers.mxp_worker.tasks.recompute_all_reputation",
            "schedule": crontab(hour="*/12", minute=48),
        },
        "mxp-market-timing-every-12h": {
            "task": "workers.mxp_worker.tasks.recompute_all_market_timing",
            "schedule": crontab(hour="*/12", minute=53),
        },
        "mxp-kill-ledger-every-12h": {
            "task": "workers.mxp_worker.tasks.recompute_all_kill_ledger",
            "schedule": crontab(hour="*/12", minute=58),
        },
        # --- Action Executor (runs after intelligence modules) ---
        "action-executor-kill-ledger-every-4h": {
            "task": "workers.action_executor_worker.tasks.execute_kill_ledger_actions",
            "schedule": crontab(hour="*/4", minute=5),
        },
        "action-executor-lifecycle-every-4h": {
            "task": "workers.action_executor_worker.tasks.execute_offer_lifecycle_transitions",
            "schedule": crontab(hour="*/4", minute=8),
        },
        "action-executor-recovery-every-4h": {
            "task": "workers.action_executor_worker.tasks.execute_recovery_actions",
            "schedule": crontab(hour="*/4", minute=12),
        },
        "action-executor-throttle-every-2h": {
            "task": "workers.action_executor_worker.tasks.enforce_capacity_throttle",
            "schedule": crontab(hour="*/2", minute=15),
        },
        "action-executor-reputation-recovery-every-4h": {
            "task": "workers.action_executor_worker.tasks.link_reputation_to_recovery",
            "schedule": crontab(hour="*/4", minute=18),
        },
        "action-executor-experiment-actions-every-6h": {
            "task": "workers.action_executor_worker.tasks.advance_experiment_outcome_actions",
            "schedule": crontab(hour="*/6", minute=22),
        },
        "action-executor-brain-decisions-every-4h": {
            "task": "workers.action_executor_worker.tasks.execute_brain_decisions",
            "schedule": crontab(hour="*/4", minute=28),
        },
        # --- Autonomous Phase A (signal scan → queue → warmup → output → maturity) ---
        "phase-a-signal-scan-every-2h": {
            "task": "workers.autonomous_phase_a_worker.tasks.run_all_signal_scans",
            "schedule": crontab(hour="*/2", minute=25),
        },
        "phase-a-auto-queue-rebuild-every-2h": {
            "task": "workers.autonomous_phase_a_worker.tasks.rebuild_all_auto_queues",
            "schedule": crontab(hour="*/2", minute=30),
        },
        "phase-a-warmup-recompute-every-4h": {
            "task": "workers.autonomous_phase_a_worker.tasks.recompute_all_warmup",
            "schedule": crontab(hour="*/4", minute=35),
        },
        "phase-a-output-recompute-every-4h": {
            "task": "workers.autonomous_phase_a_worker.tasks.recompute_all_output",
            "schedule": crontab(hour="*/4", minute=40),
        },
        "phase-a-maturity-recompute-every-4h": {
            "task": "workers.autonomous_phase_a_worker.tasks.recompute_all_maturity",
            "schedule": crontab(hour="*/4", minute=45),
        },
        # --- Autonomous Phase B (policies → runner → distribution → monetization → suppression) ---
        "phase-b-content-runner-every-1h": {
            "task": "workers.autonomous_phase_b_worker.tasks.run_content_runner",
            "schedule": crontab(hour="*", minute=50),
        },
        "phase-b-distribution-recompute-every-2h": {
            "task": "workers.autonomous_phase_b_worker.tasks.recompute_distribution_plans",
            "schedule": crontab(hour="*/2", minute=52),
        },
        "phase-b-monetization-recompute-every-2h": {
            "task": "workers.autonomous_phase_b_worker.tasks.recompute_monetization_routes",
            "schedule": crontab(hour="*/2", minute=55),
        },
        "phase-b-suppression-check-every-4h": {
            "task": "workers.autonomous_phase_b_worker.tasks.run_suppression_checks",
            "schedule": crontab(hour="*/4", minute=58),
        },
        # --- Autonomous Phase C ---
        "phase-c-funnel-every-4h": {
            "task": "workers.autonomous_phase_c_worker.tasks.run_funnel_execution",
            "schedule": crontab(hour="*/4", minute=5),
        },
        "phase-c-paid-operator-every-4h": {
            "task": "workers.autonomous_phase_c_worker.tasks.run_paid_operator",
            "schedule": crontab(hour="*/4", minute=10),
        },
        "phase-c-sponsor-every-6h": {
            "task": "workers.autonomous_phase_c_worker.tasks.run_sponsor_autonomy",
            "schedule": crontab(hour="*/6", minute=15),
        },
        "phase-c-retention-every-6h": {
            "task": "workers.autonomous_phase_c_worker.tasks.run_retention_autonomy",
            "schedule": crontab(hour="*/6", minute=25),
        },
        "phase-c-recovery-every-2h": {
            "task": "workers.autonomous_phase_c_worker.tasks.run_recovery_autonomy",
            "schedule": crontab(hour="*/2", minute=35),
        },
        "phase-c-execute-approved-every-1h": {
            "task": "workers.autonomous_phase_c_worker.tasks.execute_approved_actions",
            "schedule": crontab(hour="*", minute=40),
        },
        "phase-c-notify-operators-every-2h": {
            "task": "workers.autonomous_phase_c_worker.tasks.notify_operators",
            "schedule": crontab(hour="*/2", minute=45),
        },
        # --- Autonomous Phase D (agents, pressure, blockers, escalations) ---
        "phase-d-agent-orchestration-every-2h": {
            "task": "workers.autonomous_phase_d_worker.tasks.run_agent_orchestration",
            "schedule": crontab(hour="*/2", minute=0),
        },
        "phase-d-revenue-pressure-every-4h": {
            "task": "workers.autonomous_phase_d_worker.tasks.run_revenue_pressure",
            "schedule": crontab(hour="*/4", minute=12),
        },
        "phase-d-blocker-detection-every-2h": {
            "task": "workers.autonomous_phase_d_worker.tasks.run_blocker_detection",
            "schedule": crontab(hour="*/2", minute=20),
        },
        "phase-d-escalation-generation-every-4h": {
            "task": "workers.autonomous_phase_d_worker.tasks.run_escalation_generation",
            "schedule": crontab(hour="*/4", minute=28),
        },
        # --- Brain Architecture Phase A ---
        "brain-memory-consolidation-every-6h": {
            "task": "workers.brain_worker.tasks.consolidate_brain_memory",
            "schedule": crontab(hour="*/6", minute=32),
        },
        "brain-account-states-every-4h": {
            "task": "workers.brain_worker.tasks.recompute_account_states",
            "schedule": crontab(hour="*/4", minute=36),
        },
        "brain-opportunity-states-every-4h": {
            "task": "workers.brain_worker.tasks.recompute_opportunity_states",
            "schedule": crontab(hour="*/4", minute=42),
        },
        "brain-execution-states-every-4h": {
            "task": "workers.brain_worker.tasks.recompute_execution_states",
            "schedule": crontab(hour="*/4", minute=48),
        },
        "brain-audience-states-every-6h": {
            "task": "workers.brain_worker.tasks.recompute_audience_states",
            "schedule": crontab(hour="*/6", minute=52),
        },
        # --- Brain Architecture Phase B ---
        "brain-decisions-every-4h": {
            "task": "workers.brain_worker.tasks.recompute_brain_decisions",
            "schedule": crontab(hour="*/4", minute=56),
        },
        # --- Brain Architecture Phase C ---
        "brain-agent-mesh-every-4h": {
            "task": "workers.brain_worker.tasks.recompute_agent_mesh",
            "schedule": crontab(hour="*/4", minute=2),
        },
        # --- Brain Architecture Phase D ---
        "brain-meta-monitoring-every-2h": {
            "task": "workers.brain_worker.tasks.recompute_meta_monitoring",
            "schedule": crontab(hour="*/2", minute=8),
        },
        # --- Buffer Distribution Layer ---
        "auto-publish-approved-every-10m": {
            "task": "workers.publishing_worker.tasks.auto_publish_approved_content",
            "schedule": crontab(minute="*/10"),
        },
        "buffer-submit-pending-every-15m": {
            "task": "workers.buffer_worker.tasks.submit_pending_jobs",
            "schedule": crontab(minute="*/15"),
        },
        "buffer-status-sync-every-30m": {
            "task": "workers.buffer_worker.tasks.sync_buffer_statuses",
            "schedule": crontab(minute="*/30"),
        },
        # --- Live Execution Closure ---
        "analytics-sync-every-1h": {
            "task": "workers.live_execution_worker.tasks.sync_analytics",
            "schedule": crontab(minute=5, hour="*"),
        },
        "experiment-truth-sync-every-2h": {
            "task": "workers.live_execution_worker.tasks.sync_experiment_truth",
            "schedule": crontab(minute=15, hour="*/2"),
        },
        "crm-sync-every-1h": {
            "task": "workers.live_execution_worker.tasks.run_crm_sync",
            "schedule": crontab(minute=20, hour="*"),
        },
        "email-execution-every-5m": {
            "task": "workers.live_execution_worker.tasks.execute_emails",
            "schedule": crontab(minute="*/5"),
        },
        "sms-execution-every-5m": {
            "task": "workers.live_execution_worker.tasks.execute_sms",
            "schedule": crontab(minute="*/5"),
        },
        "messaging-blockers-every-1h": {
            "task": "workers.live_execution_worker.tasks.recompute_messaging_blockers",
            "schedule": crontab(minute=30, hour="*"),
        },
        "creator-revenue-opps-every-4h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_creator_revenue",
            "schedule": crontab(minute=10, hour="*/4"),
        },
        "ugc-services-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_ugc_services",
            "schedule": crontab(minute=20, hour="*/6"),
        },
        "service-consulting-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_service_consulting",
            "schedule": crontab(minute=25, hour="*/6"),
        },
        "premium-access-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_premium_access",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "licensing-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_licensing",
            "schedule": crontab(minute=35, hour="*/6"),
        },
        "syndication-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_syndication",
            "schedule": crontab(minute=40, hour="*/6"),
        },
        "data-products-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_data_products",
            "schedule": crontab(minute=45, hour="*/6"),
        },
        "merch-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_merch",
            "schedule": crontab(minute=50, hour="*/6"),
        },
        "live-events-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_live_events",
            "schedule": crontab(minute=55, hour="*/6"),
        },
        "affiliate-program-every-6h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_affiliate_program",
            "schedule": crontab(minute=0, hour="1,7,13,19"),
        },
        "creator-revenue-hub-every-3h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_creator_revenue_hub",
            "schedule": crontab(minute=10, hour="*/3"),
        },
        "creator-revenue-blockers-every-2h": {
            "task": "workers.creator_revenue_worker.tasks.recompute_creator_revenue_blockers",
            "schedule": crontab(minute=5, hour="*/2"),
        },
        "lec2-webhook-processing-every-5m": {
            "task": "workers.live_execution_phase2_worker.tasks.process_webhook_events",
            "schedule": crontab(minute="*/5"),
        },
        "lec2-sequence-triggers-every-10m": {
            "task": "workers.live_execution_phase2_worker.tasks.process_sequence_triggers",
            "schedule": crontab(minute="*/10"),
        },
        "lec2-payment-sync-every-30m": {
            "task": "workers.live_execution_phase2_worker.tasks.run_payment_connector_sync",
            "schedule": crontab(minute="*/30"),
        },
        "lec2-analytics-pull-every-2h": {
            "task": "workers.live_execution_phase2_worker.tasks.run_analytics_auto_pull",
            "schedule": crontab(minute=15, hour="*/2"),
        },
        "lec2-ad-reporting-every-4h": {
            "task": "workers.live_execution_phase2_worker.tasks.run_ad_reporting_import",
            "schedule": crontab(minute=20, hour="*/4"),
        },
        "lec2-buffer-truth-every-15m": {
            "task": "workers.live_execution_phase2_worker.tasks.recompute_buffer_execution_truth",
            "schedule": crontab(minute="*/15"),
        },
        "lec2-stale-buffer-jobs-every-1h": {
            "task": "workers.live_execution_phase2_worker.tasks.detect_stale_buffer_jobs",
            "schedule": crontab(minute=45),
        },
        "lec2-buffer-capabilities-every-2h": {
            "task": "workers.live_execution_phase2_worker.tasks.recompute_buffer_capabilities",
            "schedule": crontab(minute=50, hour="*/2"),
        },
        # --- Content Form Selection ---
        "content-forms-every-6h": {
            "task": "workers.content_form_worker.tasks.recompute_content_forms",
            "schedule": crontab(minute=5, hour="*/6"),
        },
        "content-form-mix-every-6h": {
            "task": "workers.content_form_worker.tasks.recompute_content_form_mix",
            "schedule": crontab(minute=10, hour="*/6"),
        },
        "content-form-blockers-every-4h": {
            "task": "workers.content_form_worker.tasks.recompute_content_form_blockers",
            "schedule": crontab(minute=15, hour="*/4"),
        },
        # --- Monster Ops: Expansion Advisor, Gatekeeper, Scale Engine ---
        "expansion-advisor-every-4h": {
            "task": "workers.monster_ops_worker.tasks.recompute_expansion_advisor",
            "schedule": crontab(minute=25, hour="*/4"),
        },
        "gatekeeper-every-6h": {
            "task": "workers.monster_ops_worker.tasks.recompute_gatekeeper",
            "schedule": crontab(minute=35, hour="*/6"),
        },
        "scale-engine-every-4h": {
            "task": "workers.monster_ops_worker.tasks.recompute_scale_engine",
            "schedule": crontab(minute=5, hour="*/4"),
        },
        "offer-learning-every-6h": {
            "task": "workers.monster_ops_worker.tasks.run_offer_learning",
            "schedule": crontab(minute=45, hour="*/6"),
        },
        "measured-data-cascade-every-4h": {
            "task": "workers.publishing_worker.tasks.run_measured_data_cascade",
            "schedule": crontab(minute=15, hour="*/4"),
        },
        "weak-lane-detection-every-6h": {
            "task": "workers.monster_ops_worker.tasks.detect_weak_lanes",
            "schedule": crontab(minute=55, hour="*/6"),
        },
        "saturation-expansion-trigger-every-4h": {
            "task": "workers.monster_ops_worker.tasks.trigger_saturation_expansion",
            "schedule": crontab(minute=0, hour="2,6,10,14,18,22"),
        },
        "daily-operator-digest": {
            "task": "workers.monster_ops_worker.tasks.daily_operator_digest",
            "schedule": crontab(minute=0, hour=7),
        },
        # --- Content Routing ---
        "content-routing-cost-rollup-daily": {
            "task": "workers.content_routing_worker.tasks.daily_cost_rollup",
            "schedule": crontab(minute=30, hour=23),
        },
        "pattern-memory-every-6h": {
            "task": "workers.pattern_memory_worker.tasks.recompute_pattern_memory",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "promote-winner-evaluate-every-4h": {
            "task": "workers.promote_winner_worker.tasks.evaluate_and_promote",
            "schedule": crontab(minute=45, hour="*/4"),
        },
        "capital-allocation-every-6h": {
            "task": "workers.capital_allocator_worker.tasks.recompute_capital_allocation",
            "schedule": crontab(minute=10, hour="*/6"),
        },
        "account-state-intel-every-4h": {
            "task": "workers.account_state_intel_worker.tasks.recompute_account_state_intel",
            "schedule": crontab(minute=20, hour="*/4"),
        },
        "quality-governor-every-2h": {
            "task": "workers.quality_governor_worker.tasks.recompute_quality_governor",
            "schedule": crontab(minute=35, hour="*/2"),
        },
        "objection-mining-every-6h": {
            "task": "workers.objection_mining_worker.tasks.recompute_objection_mining",
            "schedule": crontab(minute=40, hour="*/6"),
        },
        "opportunity-cost-every-4h": {
            "task": "workers.opportunity_cost_worker.tasks.recompute_opportunity_cost",
            "schedule": crontab(minute=50, hour="*/4"),
        },
        "failure-family-every-6h": {
            "task": "workers.failure_family_worker.tasks.recompute_failure_families",
            "schedule": crontab(minute=55, hour="*/6"),
        },
        "landing-pages-every-8h": {
            "task": "workers.landing_page_worker.tasks.recompute_landing_pages",
            "schedule": crontab(minute=5, hour="*/8"),
        },
        "campaigns-every-8h": {
            "task": "workers.campaign_worker.tasks.recompute_campaigns",
            "schedule": crontab(minute=15, hour="*/8"),
        },
        "affiliate-intel-every-4h": {
            "task": "workers.affiliate_intel_worker.tasks.recompute_affiliate_intel",
            "schedule": crontab(minute=25, hour="*/4"),
        },
        "brand-governance-every-4h": {
            "task": "workers.brand_governance_worker.tasks.recompute_brand_governance",
            "schedule": crontab(minute=35, hour="*/4"),
        },
        "enterprise-compliance-daily": {
            "task": "workers.enterprise_security_worker.tasks.recompute_compliance",
            "schedule": crontab(minute=0, hour=5),
        },
        "hyperscale-capacity-every-15m": {
            "task": "workers.hyperscale_worker.tasks.recompute_scale_capacity",
            "schedule": crontab(minute="*/15"),
        },
        "integrations-listening-every-2h": {
            "task": "workers.integrations_listening_worker.tasks.recompute_listening",
            "schedule": crontab(minute=40, hour="*/2"),
        },
        "executive-intel-daily": {
            "task": "workers.executive_intel_worker.tasks.recompute_executive_intel",
            "schedule": crontab(minute=0, hour=6),
        },
        "offer-lab-every-8h": {
            "task": "workers.offer_lab_worker.tasks.recompute_offer_lab",
            "schedule": crontab(minute=20, hour="*/8"),
        },
        "revenue-leaks-every-4h": {
            "task": "workers.revenue_leak_worker.tasks.recompute_revenue_leaks",
            "schedule": crontab(minute=30, hour="*/4"),
        },
        "digital-twin-daily": {
            "task": "workers.digital_twin_worker.tasks.run_simulations",
            "schedule": crontab(minute=0, hour=4),
        },
        "recovery-scan-every-10m": {
            "task": "workers.recovery_engine_worker.tasks.scan_recovery",
            "schedule": crontab(minute="*/10"),
        },
        "causal-attribution-every-6h": {
            "task": "workers.causal_attribution_worker.tasks.recompute_causal_attribution",
            "schedule": crontab(minute=45, hour="*/6"),
        },
        "trend-light-scan-tick": {
            "task": "workers.trend_viral_worker.tasks.trend_light_scan",
            "schedule": 10.0,  # Base tick — per-brand interval is configurable via brand_guidelines.trend_scan_interval_seconds (no default; operator/GM sets it)
        },
        "trend-deep-analysis-every-5m": {
            "task": "workers.trend_viral_worker.tasks.trend_deep_analysis",
            "schedule": crontab(minute="*/5"),
        },
        "autonomous-content-generation-every-30m": {
            "task": "workers.autonomous_generation_worker.tasks.process_pending_briefs",
            "schedule": crontab(minute="*/30"),
        },
        "autonomous-content-ideation-every-4h": {
            "task": "workers.content_ideation_worker.tasks.ideate_content",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "niche-research-daily": {
            "task": "workers.niche_research_worker.tasks.recompute_niche_scores",
            "schedule": crontab(minute=0, hour=6),
        },
        "account-warmup-check-every-1h": {
            "task": "workers.warmup_worker.tasks.enforce_warmup_cadence",
            "schedule": crontab(minute=0),
        },
        "fleet-manager-every-4h": {
            "task": "workers.fleet_manager_worker.tasks.recompute_fleet_status",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "competitor-scan-every-12h": {
            "task": "workers.competitor_worker.tasks.scan_competitors",
            "schedule": crontab(minute=0, hour="*/12"),
        },
        "daily-intelligence-report": {
            "task": "workers.intelligence_report_worker.tasks.generate_daily_report",
            "schedule": crontab(minute=0, hour=7),
        },
        "offer-rotation-every-6h": {
            "task": "workers.offer_rotation_worker.tasks.rotate_offers",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "repurpose-content-every-2h": {
            "task": "workers.repurposing_worker.tasks.repurpose_content",
            "schedule": crontab(minute=30, hour="*/2"),
        },
        "engagement-automation-every-2h": {
            "task": "workers.engagement_worker.tasks.run_engagement",
            "schedule": crontab(minute=15, hour="*/2"),
        },
        "email-campaigns-every-8h": {
            "task": "workers.email_campaign_worker.tasks.process_email_campaigns",
            "schedule": crontab(minute=0, hour="*/8"),
        },
        # --- Outreach Pipeline (send emails, poll replies) ---
        "outreach-poll-inbox-every-5m": {
            "task": "workers.outreach_worker.tasks.poll_all_inboxes",
            "schedule": crontab(minute="*/5"),
        },
        "offer-discovery-daily": {
            "task": "workers.offer_discovery_worker.tasks.discover_offers",
            "schedule": crontab(minute=0, hour=5),
        },
        "data-pruning-weekly": {
            "task": "workers.data_pruning_worker.tasks.prune_stale_data",
            "schedule": crontab(minute=0, hour=3, day_of_week=0),
        },
        # ─── Cinema Studio ─────────────────────────────────────────────
        "cinema-studio-sync-generations-every-30s": {
            "task": "workers.cinema_studio_worker.tasks.sync_studio_generations",
            "schedule": 30.0,
        },
        "cinema-studio-auto-approve-every-2m": {
            "task": "workers.cinema_studio_worker.tasks.auto_approve_studio_content",
            "schedule": 120.0,
        },
        # --- Revenue Intelligence ---
        "revenue-forecast-every-6h": {
            "task": "workers.analytics_worker.tasks.recompute_revenue_forecast",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "revenue-anomaly-check-every-1h": {
            "task": "workers.analytics_worker.tasks.check_revenue_anomalies",
            "schedule": crontab(minute=10),
        },
        "youtube-analytics-sync-every-2h": {
            "task": "workers.analytics_worker.tasks.sync_youtube_analytics",
            "schedule": crontab(minute=25, hour="*/2"),
        },
        # --- Monetization Machine ---
        "credit-replenishment-monthly": {
            "task": "workers.monetization_worker.tasks.replenish_credits",
            "schedule": crontab(minute=0, hour=0, day_of_month=1),
        },
        "credit-exhaustion-check-every-2h": {
            "task": "workers.monetization_worker.tasks.check_credit_exhaustion",
            "schedule": crontab(minute=30, hour="*/2"),
        },
        "ascension-analysis-every-4h": {
            "task": "workers.monetization_worker.tasks.compute_ascension_profiles",
            "schedule": crontab(minute=15, hour="*/4"),
        },
        "monetization-health-every-6h": {
            "task": "workers.monetization_worker.tasks.compute_monetization_health",
            "schedule": crontab(minute=20, hour="*/6"),
        },
        "multiplication-opportunity-scan-every-1h": {
            "task": "workers.monetization_worker.tasks.scan_multiplication_opportunities",
            "schedule": crontab(minute=40),
        },
        # --- SaaS Metrics ---
        "saas-metrics-snapshot-daily": {
            "task": "workers.monetization_worker.tasks.snapshot_saas_metrics",
            "schedule": crontab(minute=0, hour=1),
        },
        "churn-prediction-every-6h": {
            "task": "workers.monetization_worker.tasks.run_churn_prediction",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "expansion-opportunity-scan-every-4h": {
            "task": "workers.monetization_worker.tasks.scan_expansion_opportunities",
            "schedule": crontab(minute=45, hour="*/4"),
        },
        # --- Revenue Avenue Optimization ---
        "revenue-avenue-rankings-every-12h": {
            "task": "workers.monetization_worker.tasks.recompute_avenue_rankings",
            "schedule": crontab(minute=0, hour="*/12"),
        },
        "pipeline-scoring-every-2h": {
            "task": "workers.monetization_worker.tasks.score_pipeline_deals",
            "schedule": crontab(minute=20, hour="*/2"),
        },
        # --- Revenue Maximizer Cycle ---
        "revenue-maximizer-cycle-every-4h": {
            "task": "workers.monetization_worker.tasks.run_revenue_cycle",
            "schedule": crontab(minute=47, hour="*/4"),
        },
        # --- Quality Feedback + Growth Handling Loops ---
        # Quality feedback: performance → pattern memory → better generation
        "quality-feedback-loop-every-6h": {
            "task": "workers.monetization_worker.tasks.run_quality_feedback_loop",
            "schedule": crontab(minute=37, hour="*/6"),
        },
        # --- Platform Analytics Ingestion ---
        # Fetches real performance data from YouTube/TikTok/Instagram.
        # Gracefully skips if API credentials not configured.
        "platform-analytics-ingestion-every-6h": {
            "task": "workers.analytics_ingestion_worker.tasks.ingest_platform_analytics",
            "schedule": crontab(minute=13, hour="*/6"),
        },
        # --- Strategy Adjustment (runs after analytics ingestion) ---
        # Reads ALL winning/losing patterns, generates proportional briefs,
        # deprioritizes losers, rotates offers, detects spikes, cross-pollinates.
        "strategy-adjustment-after-analytics-every-6h": {
            "task": "workers.strategy_adjustment_worker.tasks.adjust_all_strategies",
            "schedule": crontab(minute=20, hour="*/6"),
        },
        # --- Trend Signal Ingestion ---
        # Fetches trending topics from Google Trends and YouTube.
        # Gracefully skips if SERPAPI_KEY/YOUTUBE_API_KEY not configured.
        "trend-signal-ingestion-every-12h": {
            "task": "workers.analytics_ingestion_worker.tasks.ingest_trend_signals",
            "schedule": crontab(minute=23, hour="*/12"),
        },
        # --- Async Media Job Stale Check ---
        "media-job-stale-check-every-10m": {
            "task": "workers.generation_worker.check_stale_jobs",
            "schedule": crontab(minute="*/10"),
        },
        # --- Health Monitor ---
        "system-health-check-every-5m": {
            "task": "workers.health_monitor_worker.tasks.check_system_health",
            "schedule": crontab(minute="*/5"),
        },
    },
)

app.autodiscover_tasks([
    "workers.generation_worker",
    "workers.publishing_worker",
    "workers.analytics_worker",
    "workers.qa_worker",
    "workers.learning_worker",
    "workers.portfolio_worker",
    "workers.scale_alerts_worker",
    "workers.growth_pack_worker",
    "workers.revenue_ceiling_worker",
    "workers.mxp_worker",
    "workers.action_executor_worker",
    "workers.autonomous_phase_a_worker",
    "workers.autonomous_phase_b_worker",
    "workers.autonomous_phase_c_worker",
    "workers.autonomous_phase_d_worker",
    "workers.brain_worker",
    "workers.buffer_worker",
    "workers.live_execution_worker",
    "workers.creator_revenue_worker",
    "workers.live_execution_phase2_worker",
    "workers.content_form_worker",
    "workers.monster_ops_worker",
    "workers.content_routing_worker",
    "workers.pattern_memory_worker",
    "workers.promote_winner_worker",
    "workers.capital_allocator_worker",
    "workers.account_state_intel_worker",
    "workers.quality_governor_worker",
    "workers.objection_mining_worker",
    "workers.opportunity_cost_worker",
    "workers.failure_family_worker",
    "workers.landing_page_worker",
    "workers.campaign_worker",
    "workers.affiliate_intel_worker",
    "workers.brand_governance_worker",
    "workers.enterprise_security_worker",
    "workers.hyperscale_worker",
    "workers.integrations_listening_worker",
    "workers.executive_intel_worker",
    "workers.offer_lab_worker",
    "workers.revenue_leak_worker",
    "workers.digital_twin_worker",
    "workers.recovery_engine_worker",
    "workers.causal_attribution_worker",
    "workers.trend_viral_worker",
    "workers.autonomous_generation_worker",
    "workers.content_ideation_worker",
    "workers.niche_research_worker",
    "workers.warmup_worker",
    "workers.fleet_manager_worker",
    "workers.competitor_worker",
    "workers.intelligence_report_worker",
    "workers.offer_rotation_worker",
    "workers.repurposing_worker",
    "workers.engagement_worker",
    "workers.email_campaign_worker",
    "workers.offer_discovery_worker",
    "workers.data_pruning_worker",
    "workers.cinema_studio_worker",
    "workers.monetization_worker",
    "workers.analytics_ingestion_worker",
    "workers.strategy_adjustment_worker",
    "workers.pipeline_worker",
    "workers.outreach_worker",
    "workers.health_monitor_worker",
])
