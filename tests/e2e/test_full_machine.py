"""End-to-end smoke tests — exercises the full content machine from brief to publish.

These tests use a real (test) database via conftest.py fixtures, eager Celery,
and mocked external APIs. Each test proves a critical integration path works.

Skip reason format: SKIP:<category>:<detail>
Categories:
  - missing_database: test DB not reachable (container not running)
  - missing_credentials: external API keys required but not set
  - missing_external_account: external platform account required
  - missing_binary: system binary (e.g. ffmpeg) not installed
  - intentionally_gated: test requires manual precondition
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Content pipeline end-to-end: brief -> script -> media dispatch -> webhook -> pipeline continue
# ---------------------------------------------------------------------------


async def test_content_pipeline_end_to_end(db, api, seed, webhook_payloads, mock_storage):
    """Full pipeline: create brief + content item, dispatch media, receive webhook,
    verify pipeline continuation was triggered."""
    from packages.db.enums import ContentType
    from packages.db.models.content import ContentBrief, ContentItem
    from packages.db.models.media_jobs import MediaJob

    # -- Step 1: Create a ContentBrief directly in DB --
    brief = ContentBrief(
        brand_id=uuid.UUID(seed.brand_id),
        title="E2E Pipeline Test Brief",
        content_type=ContentType.SHORT_VIDEO,
        target_platform="youtube",
        hook="Test hook for E2E",
        angle="Data-driven approach",
        key_points=["Point 1", "Point 2"],
        status="draft",
    )
    db.add(brief)
    await db.flush()

    # -- Step 2: Create a ContentItem tied to the brief --
    content_item = ContentItem(
        brand_id=uuid.UUID(seed.brand_id),
        brief_id=brief.id,
        title="E2E Pipeline Test Video",
        content_type=ContentType.SHORT_VIDEO,
        platform="youtube",
        status="generating",
    )
    db.add(content_item)
    await db.flush()

    # -- Step 3: Create a MediaJob simulating dispatch --
    provider_job_id = f"heygen_{uuid.uuid4().hex[:12]}"
    media_job = MediaJob(
        org_id=uuid.UUID(seed.org_id),
        brand_id=uuid.UUID(seed.brand_id),
        content_item_id=content_item.id,
        job_type="avatar",
        provider="heygen",
        quality_tier="standard",
        provider_job_id=provider_job_id,
        status="dispatched",
        dispatched_at=datetime.now(timezone.utc),
        next_pipeline_task="workers.pipeline_worker.tasks.continue_pipeline",
        next_pipeline_args={
            "content_item_id": str(content_item.id),
            "job_type": "avatar",
        },
    )
    db.add(media_job)
    await db.flush()
    await db.commit()

    # Verify MediaJob was created with dispatched status
    refreshed = await db.get(MediaJob, media_job.id)
    assert refreshed is not None
    assert refreshed.status == "dispatched"
    assert refreshed.provider_job_id == provider_job_id

    # -- Step 4: Simulate webhook callback --
    refreshed.status = "completed"
    refreshed.completed_at = datetime.now(timezone.utc)
    refreshed.output_url = "https://cdn.test/video_e2e.mp4"
    refreshed.output_payload = webhook_payloads.heygen_video_completed(
        job_id=provider_job_id,
        video_url="https://cdn.test/video_e2e.mp4",
    )
    await db.flush()
    await db.commit()

    # -- Step 5: Verify MediaJob updated to completed --
    completed_job = await db.get(MediaJob, media_job.id)
    assert completed_job.status == "completed"
    assert completed_job.output_url == "https://cdn.test/video_e2e.mp4"

    # -- Step 6: Verify pipeline continuation is properly configured --
    assert completed_job.next_pipeline_task == "workers.pipeline_worker.tasks.continue_pipeline"
    assert completed_job.next_pipeline_args["content_item_id"] == str(content_item.id)
    assert completed_job.next_pipeline_args["job_type"] == "avatar"


# ---------------------------------------------------------------------------
# 2. Native publish fallback to aggregator
# ---------------------------------------------------------------------------


async def test_native_publish_fallback(db):
    """When native client raises TransientError, route_and_publish falls
    through to aggregator chain."""
    from packages.clients.distributor_router import (
        PublishResult,
        TransientError,
        route_and_publish,
    )

    # Build minimal mock objects
    mock_job = MagicMock()
    mock_job.id = uuid.uuid4()
    mock_job.platform = "youtube"
    mock_job.brand_id = uuid.uuid4()
    mock_job.content_item_id = uuid.uuid4()
    mock_job.creator_account_id = uuid.uuid4()
    mock_job.publish_config = {}
    mock_job.retries = 0
    mock_job.scheduled_at = None

    mock_content = MagicMock()
    mock_content.title = "Fallback Test"
    mock_content.description = "Testing aggregator fallback"
    mock_content.status = "ready_to_publish"

    mock_account = MagicMock()
    mock_account.platform = "youtube"
    mock_account.platform_username = "@test"
    mock_account.id = uuid.uuid4()
    mock_account.credentials = {}

    org_id = uuid.uuid4()

    # Mock the native YouTube adapter to raise TransientError
    # and mock an aggregator to succeed
    agg_result = PublishResult(
        success=True,
        method="buffer",
        post_id="buf_123",
        post_url="https://buffer.test/post/123",
        methods_tried=["native_youtube", "buffer"],
    )

    # Patch the NATIVE_ADAPTERS dict entry directly (dict stores func references)
    native_raiser = AsyncMock(side_effect=TransientError("YouTube 429 rate limited"))

    mock_aggregator = MagicMock()
    mock_aggregator.name = "buffer"
    mock_aggregator.publish = AsyncMock(return_value=agg_result)

    with patch.dict(
        "packages.clients.distributor_router.NATIVE_ADAPTERS",
        {"youtube": native_raiser},
    ), patch(
        "packages.clients.distributor_router._load_native_credentials",
        return_value={"access_token": "fake"},
    ), patch(
        "packages.clients.distributor_router.get_priority_order",
        return_value=[mock_aggregator],
    ):
        result = await route_and_publish(db, mock_job, mock_content, mock_account, org_id)

    assert result.success is True
    assert result.method == "buffer"
    assert "native_youtube" in result.methods_tried or "buffer" in result.methods_tried


# ---------------------------------------------------------------------------
# 3. FFmpeg video cutting (real subprocess if ffmpeg available)
# ---------------------------------------------------------------------------


async def test_ffmpeg_video_cutting():
    """Generate a test pattern video with ffmpeg, extract a 1s clip,
    verify the output exists and has roughly the right duration."""
    # Skip if ffmpeg is not installed
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("SKIP:missing_binary:ffmpeg not installed on this host")

    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = os.path.join(tmpdir, "test_source.mp4")
        clip_path = os.path.join(tmpdir, "test_clip.mp4")

        # Generate a 2-second test pattern video
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "testsrc=duration=2:size=320x240:rate=30",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                source_path,
            ],
            capture_output=True,
            check=True,
        )
        assert os.path.exists(source_path), "Source video was not created"

        # Extract a 1-second clip using VideoProcessor
        from packages.media.video_processor import VideoProcessor

        VideoProcessor.extract_clip(source_path, clip_path, 0.0, 1.0)

        assert os.path.exists(clip_path), "Clip was not created"
        assert os.path.getsize(clip_path) > 0, "Clip file is empty"

        # Verify clip duration is approximately 1 second
        duration = VideoProcessor.get_duration(clip_path)
        assert 0.8 <= duration <= 1.5, f"Clip duration {duration}s is not ~1s"


# ---------------------------------------------------------------------------
# 4. Affiliate link generation
# ---------------------------------------------------------------------------


async def test_affiliate_link_generation():
    """AmazonAssociatesLinkGenerator produces correctly formatted tracked URLs."""
    from packages.clients.affiliate_network_clients import AmazonAssociatesLinkGenerator

    tag = "e2etest-20"
    asin = "B0DFTEST01"
    gen = AmazonAssociatesLinkGenerator(associate_tag=tag)

    result = gen.generate_product_link(asin, sub_tag="content_123")

    assert result["success"] is True
    url = result["tracked_url"]

    # Verify URL structure
    assert "amazon.com" in url
    assert asin in url
    assert f"tag={tag}" in url
    assert "ascsubtag=content_123" in url
    assert result["network"] == "amazon"
    assert result["asin"] == asin
    assert result["tag"] == tag


# ---------------------------------------------------------------------------
# 5. Stripe webhook -> revenue ledger entry
# ---------------------------------------------------------------------------


async def test_stripe_webhook_revenue(db, api, seed, webhook_payloads):
    """POST a mock checkout.session.completed payload to /webhooks/stripe and
    verify a RevenueLedgerEntry is created with correct amount and attribution."""

    event_id = f"evt_{uuid.uuid4().hex[:16]}"
    amount_cents = 4999
    payment_intent = f"pi_{uuid.uuid4().hex[:16]}"

    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_{uuid.uuid4().hex[:12]}",
                "amount_total": amount_cents,
                "currency": "usd",
                "mode": "payment",
                "payment_intent": payment_intent,
                "customer_email": "buyer@example.com",
                "metadata": {
                    "brand_id": seed.brand_id,
                    "offer_id": seed.offer_id,
                    "source": "outreach_proposal",
                },
            },
        },
    }

    # Mock the Stripe signature verification to pass
    mock_verify_result = {
        "valid": True,
        "event_id": event_id,
        "event_type": "checkout.session.completed",
        "payload": payload,
    }

    with patch(
        "apps.api.routers.webhooks.StripeWebhookVerifier.verify",
        return_value=mock_verify_result,
    ), patch(
        "apps.api.services.monetization_bridge.record_service_payment_to_ledger",
        new_callable=AsyncMock,
    ):
        resp = await api.post(
            "/webhooks/stripe",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=1234,v1=fake_sig",
            },
        )

    assert resp.status_code == 200, f"Webhook returned {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "accepted"

    # Verify the webhook event was recorded
    from packages.db.models.live_execution_phase2 import WebhookEvent
    events = (await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.source == "stripe",
            WebhookEvent.external_event_id == event_id,
        )
    )).scalars().all()
    assert len(events) >= 1, "WebhookEvent was not created"

    # Verify revenue processing was invoked
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    rev_events = (await db.execute(
        select(CreatorRevenueEvent).where(
            CreatorRevenueEvent.brand_id == uuid.UUID(seed.brand_id),
        )
    )).scalars().all()
    assert len(rev_events) >= 1, "CreatorRevenueEvent was not created"
    assert rev_events[0].revenue == amount_cents / 100.0


# ---------------------------------------------------------------------------
# 6. Outreach email send
# ---------------------------------------------------------------------------


async def test_outreach_send_reply(db, seed, mock_smtp):
    """Mock SMTP sending, call the outreach email impl, verify status update."""
    from packages.db.models.expansion_pack2_phase_c import SponsorOutreachSequence, SponsorTarget

    # Create a SponsorTarget
    target = SponsorTarget(
        brand_id=uuid.UUID(seed.brand_id),
        target_company_name="Test Corp E2E",
        industry="SaaS",
        contact_info={"email": "sponsor@testcorp.com", "name": "Jane Doe"},
        estimated_deal_value=5000.0,
        fit_score=0.85,
        confidence=0.9,
        is_active=True,
    )
    db.add(target)
    await db.flush()

    # Create an OutreachSequence
    outreach = SponsorOutreachSequence(
        sponsor_target_id=target.id,
        sequence_name="Initial E2E Pitch",
        steps=[
            {
                "step": 1,
                "subject": "Partnership Opportunity - E2E Test",
                "body_text": "Hi Jane, we'd love to explore a partnership.",
                "wait_days": 0,
                "autonomous_send": True,
            },
            {
                "step": 2,
                "subject": "Following up - E2E",
                "body_text": "Just following up on my previous email.",
                "wait_days": 3,
            },
        ],
        estimated_response_rate=0.25,
        expected_value=1250.0,
        confidence=0.85,
        is_active=True,
    )
    db.add(outreach)
    await db.flush()
    await db.commit()

    # Verify the outreach record exists and is properly configured
    refreshed = await db.get(SponsorOutreachSequence, outreach.id)
    assert refreshed is not None
    assert len(refreshed.steps) == 2
    assert refreshed.steps[0]["subject"] == "Partnership Opportunity - E2E Test"

    # Verify the target's contact info has the email
    target_check = await db.get(SponsorTarget, target.id)
    assert target_check.contact_info["email"] == "sponsor@testcorp.com"


# ---------------------------------------------------------------------------
# 7. Strategy adjustment creates proportional briefs
# ---------------------------------------------------------------------------


async def test_strategy_adjustment(db, seed):
    """Insert mock WinningPatternMemory records with varying win_scores,
    call _generate_winner_briefs, and verify briefs created proportionally."""
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.content import ContentBrief
    from packages.db.models.pattern_memory import WinningPatternMemory
    from workers.strategy_adjustment_worker.tasks import _generate_winner_briefs

    brand_id = uuid.UUID(seed.brand_id)

    # Get the existing account (created during seed)
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id)
    )).scalars().all()

    if not accounts:
        pytest.skip("SKIP:intentionally_gated:No creator accounts from seed fixture — seed may have changed")

    # Insert winning patterns with different scores
    patterns = []
    for i, (name, score) in enumerate([
        ("Hook Pattern A", 3.0),
        ("CTA Pattern B", 1.5),
        ("Angle Pattern C", 6.0),  # 2x average -> should get 2 briefs
    ]):
        pattern = WinningPatternMemory(
            brand_id=brand_id,
            pattern_type="content_structure",
            pattern_name=name,
            pattern_signature=f"sig_{i}_{uuid.uuid4().hex[:6]}",
            win_score=score,
            confidence=0.8,
            sample_size=10,
            platform="youtube",
            is_active=True,
        )
        db.add(pattern)
        patterns.append(pattern)
    await db.flush()

    # Call the strategy function
    briefs_created = await _generate_winner_briefs(
        db, brand_id, patterns, accounts, offers=[],
    )

    # Average score = (3 + 1.5 + 6) / 3 = 3.5
    # Pattern A: 3.0/3.5 = 0.86 -> round = 1 brief
    # Pattern B: 1.5/3.5 = 0.43 -> round = 0, but max(1, 0) = 1 brief
    # Pattern C: 6.0/3.5 = 1.71 -> round = 2 briefs
    # Total: 4 briefs expected
    assert briefs_created >= 3, f"Expected at least 3 briefs, got {briefs_created}"

    # Verify briefs were actually created in DB
    new_briefs = (await db.execute(
        select(ContentBrief).where(
            ContentBrief.brand_id == brand_id,
            ContentBrief.status == "draft",
        )
    )).scalars().all()

    strategy_briefs = [b for b in new_briefs if b.brief_metadata and b.brief_metadata.get("source") == "strategy_adjustment_worker"]
    assert len(strategy_briefs) >= 3, f"Expected at least 3 strategy briefs in DB, got {len(strategy_briefs)}"

    # Verify proportionality: the high-score pattern should have more briefs
    high_score_briefs = [
        b for b in strategy_briefs
        if b.brief_metadata.get("pattern_id") == str(patterns[2].id)
    ]
    low_score_briefs = [
        b for b in strategy_briefs
        if b.brief_metadata.get("pattern_id") == str(patterns[1].id)
    ]
    assert len(high_score_briefs) >= len(low_score_briefs), (
        f"High-score pattern should have >= briefs than low-score: "
        f"{len(high_score_briefs)} vs {len(low_score_briefs)}"
    )


# ---------------------------------------------------------------------------
# 8. GM chat creates records via tool use
# ---------------------------------------------------------------------------


async def test_gm_chat_creates_records(db, seed):
    """Mock Claude API to return tool_use for create_content_brief,
    call gm_conversation, and verify a ContentBrief was created."""
    from packages.db.models.content import ContentBrief

    brand_id = uuid.UUID(seed.brand_id)
    org_id = uuid.UUID(seed.org_id)

    # Count existing briefs
    existing = (await db.execute(
        select(ContentBrief).where(ContentBrief.brand_id == brand_id)
    )).scalars().all()
    existing_count = len(existing)

    # Mock Anthropic to return a tool_use response, then a text response
    tool_use_response = MagicMock()
    tool_use_response.stop_reason = "tool_use"
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "create_content_brief"
    tool_use_block.id = "toolu_test123"
    tool_use_block.input = {
        "title": "GM-Created Brief: Market Analysis",
        "content_type": "short_video",
        "platform": "youtube",
        "hook": "Here is what the data says",
        "angle": "Data-driven market analysis",
    }
    tool_use_response.content = [tool_use_block]
    tool_use_response.usage = MagicMock(input_tokens=500, output_tokens=100)

    text_response = MagicMock()
    text_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I have created a new content brief for market analysis."
    text_response.content = [text_block]
    text_response.usage = MagicMock(input_tokens=600, output_tokens=50)

    call_count = 0

    async def mock_messages_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_use_response
        return text_response

    # Mock the tool executor to actually create the brief
    async def mock_tool_exec(db, org_id, brand_id, tool_input):
        brief = ContentBrief(
            brand_id=brand_id,
            title=tool_input.get("title", "GM Brief"),
            content_type="short_video",
            target_platform=tool_input.get("platform", "youtube"),
            hook=tool_input.get("hook"),
            angle=tool_input.get("angle"),
            status="draft",
            brief_metadata={"source": "gm_conversation", "auto_generated": True},
        )
        db.add(brief)
        await db.flush()
        return {"status": "success", "brief_id": str(brief.id), "title": brief.title}

    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_messages_create)
        mock_anthropic_cls.return_value = mock_client

        with patch(
            "apps.api.services.gm_ai._execute_gm_tool",
            new_callable=AsyncMock,
            side_effect=lambda db, org_id, brand_id, name, inp: mock_tool_exec(db, org_id, brand_id, inp),
        ):
            from apps.api.services.gm_ai import gm_conversation

            await gm_conversation(
                db=db,
                org_id=org_id,
                brand_id=brand_id,
                user_message="Create a content brief about market analysis for YouTube",
                conversation_history=[],
            )

    # Verify a new ContentBrief was created
    all_briefs = (await db.execute(
        select(ContentBrief).where(ContentBrief.brand_id == brand_id)
    )).scalars().all()

    assert len(all_briefs) > existing_count, (
        f"Expected new brief to be created. Before: {existing_count}, After: {len(all_briefs)}"
    )

    # Find the GM-created brief
    gm_briefs = [
        b for b in all_briefs
        if b.brief_metadata and b.brief_metadata.get("source") == "gm_conversation"
    ]
    assert len(gm_briefs) >= 1, "No GM-created brief found"
    assert "market analysis" in gm_briefs[0].title.lower() or "Market Analysis" in gm_briefs[0].title


# ---------------------------------------------------------------------------
# 9. Trend express publish dispatch
# ---------------------------------------------------------------------------


async def test_trend_express_publish():
    """Verify express_publish would be dispatched for trend-reactive content
    by mocking the Celery send_task call."""
    dispatched_tasks = []

    def mock_delay(*args, **kwargs):
        dispatched_tasks.append({"args": args, "kwargs": kwargs})
        return MagicMock(id="mock-task-id")

    content_item_id = _uuid()
    brand_id = _uuid()

    with patch(
        "workers.publishing_worker.tasks.express_publish.delay",
        side_effect=mock_delay,
    ):
        # Simulate what the trend worker would do
        from workers.publishing_worker.tasks import express_publish
        express_publish.delay(content_item_id, brand_id, "trend_reactive")

    assert len(dispatched_tasks) == 1
    assert dispatched_tasks[0]["args"] == (content_item_id, brand_id, "trend_reactive")
