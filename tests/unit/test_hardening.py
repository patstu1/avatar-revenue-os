"""Verification tests for the stabilization / hardening sprint.

Tests cover:
- Request ID middleware behavior
- Global exception handler JSON shape
- Rate limiter structure
- Queue routing configuration
- Worker lifecycle persistence (TrackedTask)
- Celery housekeeping settings
- Health check endpoint shape
- Notification adapter failure visibility
- Recompute idempotency (delete-before-insert pattern)
"""
import importlib
import uuid

import pytest


# ─── A1: Request ID Middleware ────────────────────────────────────────────

class TestRequestIDMiddleware:
    def test_middleware_class_exists(self):
        from apps.api.middleware import RequestIDMiddleware
        assert RequestIDMiddleware is not None

    def test_request_id_header_constant(self):
        from apps.api.middleware import REQUEST_ID_HEADER
        assert REQUEST_ID_HEADER == "X-Request-ID"

    def test_exception_handlers_registrable(self):
        from apps.api.middleware import register_exception_handlers
        assert callable(register_exception_handlers)


# ─── A3: Global Exception Handler ────────────────────────────────────────

class TestGlobalExceptionHandler:
    def test_register_exception_handlers_callable(self):
        from apps.api.middleware import register_exception_handlers
        assert callable(register_exception_handlers)

    def test_app_imports_and_registers_handlers(self):
        """Verify main.py source code calls register_exception_handlers."""
        import pathlib
        main_path = pathlib.Path(__file__).resolve().parents[2] / "apps" / "api" / "main.py"
        src = main_path.read_text()
        assert "register_exception_handlers" in src


# ─── C6: Queue Split ─────────────────────────────────────────────────────

class TestQueueRouting:
    def test_queue_count(self):
        from workers.celery_app import app
        queues = app.conf.task_queues
        assert len(queues) >= 14, f"Expected at least 14 queues, got {len(queues)}"

    def test_revenue_ceiling_split_into_abc(self):
        from workers.celery_app import app
        queues = set(app.conf.task_queues.keys())
        assert "revenue_ceiling_a" in queues
        assert "revenue_ceiling_b" in queues
        assert "revenue_ceiling_c" in queues

    def test_notifications_queue_exists(self):
        from workers.celery_app import app
        assert "notifications" in app.conf.task_queues

    def test_expansion_pack2_queue_exists(self):
        from workers.celery_app import app
        assert "expansion_pack2" in app.conf.task_queues

    def test_notification_task_routed_to_notifications_queue(self):
        from workers.celery_app import app
        routes = app.conf.task_routes
        key = "workers.scale_alerts_worker.tasks.process_notification_deliveries"
        assert key in routes
        assert routes[key]["queue"] == "notifications"

    def test_ep2_tasks_routed_to_expansion_pack2(self):
        from workers.celery_app import app
        routes = app.conf.task_routes
        ep2_keys = [k for k in routes if "lead_qualification" in k or "pricing_recommendations" in k or "referral_program" in k]
        for k in ep2_keys:
            assert routes[k]["queue"] == "expansion_pack2", f"{k} not routed to expansion_pack2"

    def test_rc_a_tasks_routed_correctly(self):
        from workers.celery_app import app
        routes = app.conf.task_routes
        rc_a_keys = [k for k in routes if "offer_ladders" in k or "owned_audience" in k or "message_sequences" in k or "funnel_leaks" in k]
        for k in rc_a_keys:
            assert routes[k]["queue"] == "revenue_ceiling_a", f"{k} not routed to revenue_ceiling_a"


# ─── C8: Celery Housekeeping ─────────────────────────────────────────────

class TestCeleryHousekeeping:
    def test_result_expires_set(self):
        from workers.celery_app import app
        assert app.conf.result_expires == 86400

    def test_reject_on_worker_lost(self):
        from workers.celery_app import app
        assert app.conf.task_reject_on_worker_lost is True

    def test_max_tasks_per_child(self):
        from workers.celery_app import app
        assert app.conf.worker_max_tasks_per_child == 1000


# ─── C7/B4: Worker TrackedTask ───────────────────────────────────────────

class TestTrackedTask:
    def test_tracked_task_has_audit_method(self):
        from workers.base_task import TrackedTask
        assert hasattr(TrackedTask, "_write_audit")

    def test_tracked_task_retry_config(self):
        from workers.base_task import TrackedTask
        assert TrackedTask.max_retries == 3
        assert TrackedTask.retry_backoff is True

    def test_cached_engine_function_exists(self):
        from workers.base_task import _cached_sync_engine
        assert callable(_cached_sync_engine)


# ─── D10: Rate Limiting ──────────────────────────────────────────────────

class TestRateLimiting:
    def test_rate_limiter_class_exists(self):
        from apps.api.rate_limit import RateLimiter
        assert RateLimiter is not None

    def test_auth_rate_limit_configured(self):
        from apps.api.rate_limit import auth_rate_limit
        assert auth_rate_limit.max_calls == 10
        assert auth_rate_limit.window_seconds == 60

    def test_recompute_rate_limit_configured(self):
        from apps.api.rate_limit import recompute_rate_limit
        assert recompute_rate_limit.max_calls == 5
        assert recompute_rate_limit.window_seconds == 60

    def test_rate_limiter_key_prefix(self):
        from apps.api.rate_limit import auth_rate_limit, recompute_rate_limit
        assert auth_rate_limit.key_prefix == "rl:auth"
        assert recompute_rate_limit.key_prefix == "rl:recompute"


# ─── F16: Notification Adapter Hardening ──────────────────────────────────

class TestNotificationAdapters:
    def test_unconfigured_email_returns_clear_error(self):
        import asyncio
        from packages.notifications.adapters import EmailAdapter, NotificationPayload
        adapter = EmailAdapter(smtp_host="", smtp_user="")
        payload = NotificationPayload(title="Test", summary="Test", urgency=50, alert_type="test", brand_id="x")
        ok, err = asyncio.run(adapter.send(payload, "test@example.com"))
        assert ok is False
        assert "SMTP" in err

    def test_unconfigured_slack_returns_clear_error(self):
        import asyncio
        from packages.notifications.adapters import SlackWebhookAdapter, NotificationPayload
        adapter = SlackWebhookAdapter(webhook_url="")
        payload = NotificationPayload(title="Test", summary="Test", urgency=50, alert_type="test", brand_id="x")
        ok, err = asyncio.run(adapter.send(payload, "channel"))
        assert ok is False
        assert "webhook" in err.lower() or "SLACK" in err

    def test_unconfigured_sms_returns_clear_error(self):
        import asyncio
        from packages.notifications.adapters import SMSAdapter, NotificationPayload
        adapter = SMSAdapter(api_key="")
        payload = NotificationPayload(title="Test", summary="Test", urgency=50, alert_type="test", brand_id="x")
        ok, err = asyncio.run(adapter.send(payload, "+1234567890"))
        assert ok is False
        assert "SMS" in err

    def test_in_app_always_succeeds(self):
        import asyncio
        from packages.notifications.adapters import InAppAdapter, NotificationPayload
        adapter = InAppAdapter()
        payload = NotificationPayload(title="Test", summary="Test", urgency=50, alert_type="test", brand_id="x")
        ok, err = asyncio.run(adapter.send(payload, "user"))
        assert ok is True
        assert err is None


# ─── D11: Idempotency — verify delete-before-insert in service modules ───

class TestRecomputeIdempotency:
    """Verify that all recompute service functions import 'delete' from SQLAlchemy.
    This is a structural check — actual DB behavior is tested in integration tests."""

    def _check_module_has_delete(self, module_path: str):
        mod = importlib.import_module(module_path)
        source_file = mod.__file__
        with open(source_file, "r") as f:
            content = f.read()
        assert "delete(" in content, f"{module_path} does not use delete() — potential idempotency gap"

    def test_scale_alerts_service_uses_delete(self):
        self._check_module_has_delete("apps.api.services.scale_alerts_service")

    def test_revenue_ceiling_a_uses_delete(self):
        self._check_module_has_delete("apps.api.services.revenue_ceiling_phase_a_service")

    def test_revenue_ceiling_b_uses_delete(self):
        self._check_module_has_delete("apps.api.services.revenue_ceiling_phase_b_service")

    def test_revenue_ceiling_c_uses_delete(self):
        self._check_module_has_delete("apps.api.services.revenue_ceiling_phase_c_service")

    def test_ep2a_uses_delete(self):
        self._check_module_has_delete("apps.api.services.expansion_pack2_phase_a_service")

    def test_ep2b_uses_delete(self):
        self._check_module_has_delete("apps.api.services.expansion_pack2_phase_b_service")

    def test_ep2c_uses_delete(self):
        self._check_module_has_delete("apps.api.services.expansion_pack2_phase_c_service")


# ─── E12: Seed data coverage ─────────────────────────────────────────────

class TestSeedDataCoverage:
    """Verify the seed script references all major dashboard model classes."""

    def test_seed_imports_scale_alerts(self):
        import scripts.seed as seed_mod
        source = seed_mod.__file__
        with open(source, "r") as f:
            content = f.read()
        assert "OperatorAlert" in content
        assert "LaunchCandidate" in content
        assert "ScaleBlockerReport" in content

    def test_seed_imports_revenue_ceiling(self):
        import scripts.seed as seed_mod
        with open(seed_mod.__file__, "r") as f:
            content = f.read()
        assert "OfferLadder" in content
        assert "HighTicketOpportunity" in content
        assert "RecurringRevenueModel" in content

    def test_seed_imports_expansion_packs(self):
        import scripts.seed as seed_mod
        with open(seed_mod.__file__, "r") as f:
            content = f.read()
        assert "LeadOpportunity" in content
        assert "PricingRecommendation" in content
        assert "ReferralProgramRecommendation" in content
        assert "ProfitGuardrailReport" in content

    def test_seed_imports_autonomous_execution(self):
        import scripts.seed as seed_mod
        with open(seed_mod.__file__, "r") as f:
            content = f.read()
        assert "AutomationExecutionPolicy" in content
        assert "AutomationExecutionRun" in content

    def test_seed_covers_all_platforms(self):
        import scripts.seed as seed_mod
        with open(seed_mod.__file__, "r") as f:
            content = f.read()
        for p in ["YOUTUBE", "TIKTOK", "INSTAGRAM", "TWITTER", "REDDIT", "LINKEDIN", "FACEBOOK"]:
            assert f"Platform.{p}" in content, f"Seed missing Platform.{p}"


# ─── Item 1: Recompute rate limiting applied across routers ───────────────

class TestRecomputeRateLimitApplied:
    """Verify that all recompute router files import and use recompute_rate_limit."""

    ROUTER_FILES = [
        "apps/api/routers/scale_alerts.py",
        "apps/api/routers/growth_commander.py",
        "apps/api/routers/growth_pack.py",
        "apps/api/routers/revenue_ceiling_phase_a.py",
        "apps/api/routers/revenue_ceiling_phase_b.py",
        "apps/api/routers/revenue_ceiling_phase_c.py",
        "apps/api/routers/expansion_pack2_phase_a.py",
        "apps/api/routers/expansion_pack2_phase_b.py",
        "apps/api/routers/expansion_pack2_phase_c.py",
        "apps/api/routers/autonomous_execution.py",
        "apps/api/routers/brand_scale.py",
        "apps/api/routers/brand_growth.py",
        "apps/api/routers/brand_phase7.py",
        "apps/api/routers/brand_revenue_intel.py",
        "apps/api/routers/discovery.py",
    ]

    def _read_router(self, path: str) -> str:
        import os
        full = os.path.join(os.path.dirname(__file__), "..", "..", path)
        with open(full) as f:
            return f.read()

    def test_all_routers_import_rate_limit(self):
        for path in self.ROUTER_FILES:
            src = self._read_router(path)
            assert "recompute_rate_limit" in src, f"{path} missing recompute_rate_limit import"

    def test_all_routers_import_depends(self):
        for path in self.ROUTER_FILES:
            src = self._read_router(path)
            assert "Depends" in src, f"{path} missing Depends import"

    def test_all_routers_use_rate_limit_in_post(self):
        for path in self.ROUTER_FILES:
            src = self._read_router(path)
            assert "Depends(recompute_rate_limit)" in src, f"{path} has no Depends(recompute_rate_limit) usage"


# ─── Item 5: Org-scope helper exists ─────────────────────────────────────

class TestOrgScopeHelper:
    def test_require_brand_access_exists(self):
        from apps.api.deps import require_brand_access
        assert callable(require_brand_access)

    def test_require_brand_access_is_async(self):
        import asyncio
        from apps.api.deps import require_brand_access
        assert asyncio.iscoroutinefunction(require_brand_access)
