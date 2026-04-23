"""Recurring Revenue Ceiling Phase A recomputes."""
import asyncio
import logging

from sqlalchemy import select

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import async_session_factory
from packages.db.models.core import Brand
from apps.api.services import revenue_ceiling_phase_a_service as rca
from apps.api.services import revenue_ceiling_phase_b_service as rcb
from apps.api.services import revenue_ceiling_phase_c_service as rcc
from apps.api.services import expansion_pack2_phase_a_service as ep2a
from apps.api.services import expansion_pack2_phase_b_service as ep2b
from apps.api.services import expansion_pack2_phase_c_service as ep2c

logger = logging.getLogger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_offer_ladders")
def recompute_all_offer_ladders(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rca.recompute_offer_ladders(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("offer_ladders_created", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_offer_ladders %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_owned_audience")
def recompute_all_owned_audience(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await rca.recompute_owned_audience(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_owned_audience %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.refresh_all_message_sequences")
def refresh_all_message_sequences(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await rca.generate_message_sequences(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("generate_message_sequences %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_funnel_leaks")
def recompute_all_funnel_leaks(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await rca.recompute_funnel_leaks(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_funnel_leaks %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_high_ticket")
def recompute_all_high_ticket(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rcb.recompute_high_ticket_opportunities(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("high_ticket_rows", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_high_ticket %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_product_opportunities")
def recompute_all_product_opportunities(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rcb.recompute_product_opportunities(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("product_opportunities", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_product_opportunities %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_revenue_density")
def recompute_all_revenue_density(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rcb.recompute_revenue_density(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("revenue_density_rows", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_revenue_density %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_recurring_revenue")
def recompute_all_recurring_revenue(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await rcc.recompute_recurring_revenue(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_recurring_revenue %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_inventory")
def recompute_all_sponsor_inventory(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rcc.recompute_sponsor_inventory(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("sponsor_inventory_rows", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_sponsor_inventory %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_trust_conversion")
def recompute_all_trust_conversion(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await rcc.recompute_trust_conversion(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_trust_conversion %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_lead_qualification")
def recompute_all_lead_qualification(self) -> dict:
    async def _run():
        total = {"brands": 0, "leads_scored": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2a.recompute_lead_qualification(db, bid)
                    await db.commit()
                    total["leads_scored"] += int(res.get("leads_scored", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_lead_qualification %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_owned_offer_recommendations")
def recompute_all_owned_offer_recommendations(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2a.recompute_owned_offer_recommendations(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("rows", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_owned_offer_recommendations %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_monetization_mix")
def recompute_all_monetization_mix(self) -> dict:
    async def _run():
        total = {"brands": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    await rcc.recompute_monetization_mix(db, bid)
                    await db.commit()
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_monetization_mix %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.refresh_all_paid_promotion_candidates")
def refresh_all_paid_promotion_candidates(self) -> dict:
    async def _run():
        total = {"brands": 0, "eligible": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rcc.recompute_paid_promotion_candidates(db, bid)
                    await db.commit()
                    total["eligible"] += int(res.get("eligible", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_paid_promotion_candidates %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.refresh_all_upsell_recommendations")
def refresh_all_upsell_recommendations(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await rcb.recompute_upsell_recommendations(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("upsell_rows", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_upsell %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_pricing_recommendations")
def recompute_all_pricing_recommendations(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2b.recompute_pricing_recommendations(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("pricing_recommendations_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_pricing_recommendations %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_bundle_recommendations")
def recompute_all_bundle_recommendations(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2b.recompute_bundle_recommendations(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("bundle_recommendations_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_bundle_recommendations %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_retention_recommendations")
def recompute_all_retention_recommendations(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2b.recompute_retention_recommendations(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("retention_recommendations_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_retention_recommendations %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_reactivation_campaigns")
def recompute_all_reactivation_campaigns(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2b.recompute_reactivation_campaigns(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("reactivation_campaigns_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_reactivation_campaigns %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_referral_program_recommendations")
def recompute_all_referral_program_recommendations(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2c.recompute_referral_program_recommendations(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("referral_recommendations_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_referral_program_recommendations %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_competitive_gap_reports")
def recompute_all_competitive_gap_reports(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2c.recompute_competitive_gap_reports(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("competitive_gap_reports_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_competitive_gap_reports %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_targets")
def recompute_all_sponsor_targets(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2c.recompute_sponsor_targets(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("sponsor_targets_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_sponsor_targets %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_sponsor_outreach_sequences")
def recompute_all_sponsor_outreach_sequences(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2c.recompute_sponsor_outreach_sequences(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("sponsor_outreach_sequences_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_sponsor_outreach_sequences %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())


@app.task(base=TrackedTask, bind=True, name="workers.revenue_ceiling_worker.tasks.recompute_all_profit_guardrail_reports")
def recompute_all_profit_guardrail_reports(self) -> dict:
    async def _run():
        total = {"brands": 0, "rows": 0, "errors": []}
        async with async_session_factory() as db:
            ids = [r[0] for r in (await db.execute(select(Brand.id))).all()]
        for bid in ids:
            try:
                async with async_session_factory() as db:
                    res = await ep2c.recompute_profit_guardrail_reports(db, bid)
                    await db.commit()
                    total["rows"] += int(res.get("profit_guardrail_reports_count", 0))
                    total["brands"] += 1
            except Exception as e:
                logger.exception("recompute_profit_guardrail_reports %s", bid)
                total["errors"].append({"brand_id": str(bid), "error": str(e)})
        return total

    return _run_async(_run())
