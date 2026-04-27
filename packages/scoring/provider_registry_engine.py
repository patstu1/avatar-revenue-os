"""Provider Registry Engine — source of truth for all providers in the system."""

from __future__ import annotations

import os
from typing import Any

PROVIDER_INVENTORY: list[dict[str, Any]] = [
    # ── AI / Media ─────────────────────────────────────────────────────────
    # ── AI Text (tiered: Claude hero / Gemini Flash standard / DeepSeek bulk) ──
    {
        "provider_key": "claude",
        "display_name": "Claude (Anthropic)",
        "category": "ai_text",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["ANTHROPIC_API_KEY"],
        "integration_status": "live",
        "description": "Primary orchestrator + hero text. Copilot brain, content planning, strategy. $3/$15 per 1M tokens.",
        "capabilities": ["reasoning", "planning", "content_generation", "decision_support", "hero_copy"],
    },
    {
        "provider_key": "gemini_flash",
        "display_name": "Gemini 2.5 Flash",
        "category": "ai_text",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["GOOGLE_AI_API_KEY"],
        "integration_status": "live",
        "description": "Standard-tier text workhorse. Captions, descriptions, scheduling text. $0.30/$2.50 per 1M tokens. 90%+ as good at 10x cheaper.",
        "capabilities": ["text_generation", "captions", "descriptions"],
    },
    {
        "provider_key": "deepseek",
        "display_name": "DeepSeek V3.2",
        "category": "ai_text",
        "provider_type": "primary",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["DEEPSEEK_API_KEY"],
        "integration_status": "live",
        "description": "Bulk text scanner. Hashtags, SEO keywords, trend scanning, analytics summaries. $0.28/$0.42 per 1M tokens.",
        "capabilities": ["text_generation", "data_scanning", "seo", "hashtags"],
    },
    {
        "provider_key": "openai",
        "display_name": "OpenAI",
        "category": "ai_reasoning",
        "provider_type": "fallback",
        "is_primary": False,
        "is_fallback": True,
        "is_optional": False,
        "env_keys": ["OPENAI_API_KEY"],
        "integration_status": "live",
        "description": "Powers GPT Image 1.5 for hero images + Realtime voice adapter. NOT used for text reasoning (Claude is primary).",
        "capabilities": ["image_generation", "realtime_voice"],
    },
    # ── AI Image (tiered: GPT Image hero / Imagen 4 bulk / Flux variety) ──
    {
        "provider_key": "gpt_image",
        "display_name": "GPT Image 1.5 (OpenAI)",
        "category": "ai_image",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["OPENAI_API_KEY"],
        "integration_status": "live",
        "description": "Hero images, product shots, ad creatives. ~$0.04/image. Top quality benchmark.",
        "capabilities": ["image_generation", "hero_images", "ad_creatives"],
    },
    {
        "provider_key": "imagen4",
        "display_name": "Google Imagen 4 Fast",
        "category": "ai_image",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["GOOGLE_AI_API_KEY"],
        "integration_status": "live",
        "description": "Bulk social graphics, thumbnails, variations. ~$0.02/image. Best price-to-quality ratio.",
        "capabilities": ["image_generation", "thumbnails", "bulk_graphics"],
    },
    {
        "provider_key": "flux",
        "display_name": "Flux 2 Pro (fal.ai)",
        "category": "ai_image",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["FAL_API_KEY"],
        "integration_status": "live",
        "description": "Style variety images. ~$0.055/image. Different aesthetic for brand variety.",
        "capabilities": ["image_generation", "artistic_styles"],
    },
    # ── AI Video (tiered: Runway hero / Kling bulk) ──
    {
        "provider_key": "runway",
        "display_name": "Runway Gen-4 Turbo",
        "category": "ai_video",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["RUNWAY_API_KEY"],
        "integration_status": "live",
        "description": "Hero cinematic video. ~$0.10-0.48/5sec clip. Premium quality for promoted content.",
        "capabilities": ["video_generation", "cinematic", "hero_video"],
    },
    {
        "provider_key": "kling",
        "display_name": "Kling AI (fal.ai)",
        "category": "ai_video",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["FAL_API_KEY"],
        "integration_status": "live",
        "description": "Bulk video clips, b-roll, social reels. ~$0.07/sec. Best credit-to-dollar ratio.",
        "capabilities": ["video_generation", "b_roll", "social_clips"],
    },
    # ── AI Avatar (HeyGen primary / D-ID budget / Tavus optional) ──
    {
        "provider_key": "heygen",
        "display_name": "HeyGen",
        "category": "ai_avatar",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["HEYGEN_API_KEY"],
        "integration_status": "live",
        "description": "Primary avatar generation. Creator plan $29/mo unlimited standard. Best lip-sync, most natural output.",
        "capabilities": ["avatar_video", "lip_sync", "talking_head", "interactive_streaming"],
    },
    {
        "provider_key": "did",
        "display_name": "D-ID",
        "category": "ai_avatar",
        "provider_type": "fallback",
        "is_primary": False,
        "is_fallback": True,
        "is_optional": False,
        "env_keys": ["DID_API_KEY"],
        "integration_status": "live",
        "description": "Budget avatar at volume. Pay-per-use, cheaper than HeyGen at scale for bulk affiliate/product review avatars.",
        "capabilities": ["avatar_video", "lip_sync", "budget_avatar"],
    },
    {
        "provider_key": "tavus",
        "display_name": "Tavus",
        "category": "ai_avatar",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["TAVUS_API_KEY"],
        "integration_status": "partial",
        "description": "Optional avatar video generation. Adapter exists, gated on credentials.",
        "capabilities": ["avatar_video", "lip_sync", "async_video"],
    },
    # ── AI Voice (tiered: ElevenLabs hero / Fish Audio standard / Voxtral bulk) ──
    {
        "provider_key": "elevenlabs",
        "display_name": "ElevenLabs",
        "category": "ai_voice",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["ELEVENLABS_API_KEY"],
        "integration_status": "live",
        "description": "Hero voice — narration, voice cloning, brand voice. ~$0.18-0.30/1K chars. Quality king.",
        "capabilities": ["voice_synthesis", "voice_cloning", "streaming_audio", "hero_narration"],
    },
    {
        "provider_key": "fish_audio",
        "display_name": "Fish Audio",
        "category": "ai_voice",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["FISH_AUDIO_API_KEY"],
        "integration_status": "live",
        "description": "Standard voiceovers. $15/1M chars, 80% cheaper than ElevenLabs. #1 on TTS-Arena.",
        "capabilities": ["voice_synthesis", "bulk_voiceover"],
    },
    {
        "provider_key": "voxtral",
        "display_name": "Voxtral TTS (Mistral)",
        "category": "ai_voice",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["MISTRAL_API_KEY"],
        "integration_status": "live",
        "description": "Ultra-budget voice. $0.016/1K chars. Voice clone from 3 seconds of audio.",
        "capabilities": ["voice_synthesis", "voice_cloning", "ultra_budget"],
    },
    # ── AI Music ──
    {
        "provider_key": "suno",
        "display_name": "Suno",
        "category": "ai_music",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["SUNO_API_KEY"],
        "integration_status": "live",
        "description": "Background music, intros, branded jingles. ~$10-30/mo subscription.",
        "capabilities": ["music_generation", "background_tracks"],
    },
    # ── Fallback ──
    {
        "provider_key": "fallback_media",
        "display_name": "Fallback (Template)",
        "category": "ai_media",
        "provider_type": "fallback",
        "is_primary": False,
        "is_fallback": True,
        "is_optional": False,
        "env_keys": [],
        "integration_status": "live",
        "description": "Built-in template-based fallback. Always available, no credentials needed.",
        "capabilities": ["template_video", "static_image"],
    },
    # ── Payment ────────────────────────────────────────────────────────────
    {
        "provider_key": "stripe",
        "display_name": "Stripe",
        "category": "payment",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        # DB-only: Stripe credentials live in integration_providers
        # (api_key + api_secret/webhook_secret encrypted). No env path.
        "env_keys": [],
        "integration_status": "live",
        "description": "Payment processing, webhook verification, batch charge/intent sync. Configure via Settings > Integrations (DB-only).",
        "capabilities": ["payment_processing", "webhook_verification", "batch_sync", "refund_tracking"],
    },
    {
        "provider_key": "shopify",
        "display_name": "Shopify",
        "category": "payment",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["SHOPIFY_SHOP_DOMAIN", "SHOPIFY_ACCESS_TOKEN", "SHOPIFY_WEBHOOK_SECRET"],
        "integration_status": "live",
        "description": "E-commerce order sync, webhook verification, batch order pull.",
        "capabilities": ["order_sync", "webhook_verification", "batch_sync", "refund_tracking"],
    },
    # ── Social / Distribution ──────────────────────────────────────────────
    {
        "provider_key": "buffer",
        "display_name": "Buffer",
        "category": "social_distribution",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["BUFFER_API_KEY"],
        "integration_status": "live",
        "description": "Social media distribution — submit, status sync, profile management.",
        "capabilities": ["social_publish", "status_sync", "profile_management", "scheduling"],
    },
    # ── Ad Platforms ───────────────────────────────────────────────────────
    {
        "provider_key": "meta_ads",
        "display_name": "Meta Ads",
        "category": "ad_platform",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["META_ADS_ACCESS_TOKEN", "META_ADS_ACCOUNT_ID"],
        "integration_status": "live",
        "description": "Meta/Facebook campaign reporting import.",
        "capabilities": ["campaign_reporting", "spend_tracking", "conversion_tracking"],
    },
    {
        "provider_key": "google_ads",
        "display_name": "Google Ads",
        "category": "ad_platform",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_OAUTH_TOKEN"],
        "integration_status": "live",
        "description": "Google/YouTube campaign reporting import.",
        "capabilities": ["campaign_reporting", "spend_tracking", "conversion_tracking"],
    },
    {
        "provider_key": "tiktok_ads",
        "display_name": "TikTok Ads",
        "category": "ad_platform",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["TIKTOK_ADS_ACCESS_TOKEN", "TIKTOK_ADS_ADVERTISER_ID"],
        "integration_status": "live",
        "description": "TikTok campaign reporting import.",
        "capabilities": ["campaign_reporting", "spend_tracking", "conversion_tracking"],
    },
    # ── CRM ────────────────────────────────────────────────────────────────
    {
        "provider_key": "crm",
        "display_name": "CRM (HubSpot/generic)",
        "category": "crm",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["CRM_API_KEY", "CRM_PROVIDER"],
        "integration_status": "partial",
        "description": "CRM contact sync. Adapter exists, real API calls stubbed.",
        "capabilities": ["contact_sync", "lifecycle_tracking"],
    },
    # ── Email ──────────────────────────────────────────────────────────────
    {
        "provider_key": "smtp",
        "display_name": "SMTP Email",
        "category": "email",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["SMTP_HOST", "SMTP_FROM_EMAIL"],
        "integration_status": "live",
        "description": "Direct SMTP email delivery via aiosmtplib.",
        "capabilities": ["email_send", "html_email", "tls"],
    },
    {
        "provider_key": "esp",
        "display_name": "ESP (Mailchimp/SendGrid)",
        "category": "email",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["ESP_API_KEY"],
        "integration_status": "partial",
        "description": "Email service provider for bulk/transactional email.",
        "capabilities": ["email_send", "bulk_email", "templates"],
    },
    # ── SMS ────────────────────────────────────────────────────────────────
    {
        "provider_key": "twilio",
        "display_name": "Twilio",
        "category": "sms",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"],
        "integration_status": "live",
        "description": "SMS delivery via Twilio REST API.",
        "capabilities": ["sms_send", "delivery_status"],
    },
    # ── Notifications ──────────────────────────────────────────────────────
    {
        "provider_key": "slack",
        "display_name": "Slack Webhook",
        "category": "notifications",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["SLACK_WEBHOOK_URL"],
        "integration_status": "partial",
        "description": "Slack webhook for operator alerts.",
        "capabilities": ["webhook_notification"],
    },
    {
        "provider_key": "in_app",
        "display_name": "In-App Notifications",
        "category": "notifications",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": [],
        "integration_status": "live",
        "description": "Internal notification system. Always available.",
        "capabilities": ["in_app_notification"],
    },
    # ── Storage ────────────────────────────────────────────────────────────
    {
        "provider_key": "s3",
        "display_name": "S3-Compatible Storage",
        "category": "storage",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"],
        "integration_status": "partial",
        "description": "S3-compatible object storage for media assets.",
        "capabilities": ["file_storage", "media_hosting"],
    },
    # ── Infrastructure ─────────────────────────────────────────────────────
    {
        "provider_key": "postgres",
        "display_name": "PostgreSQL",
        "category": "infrastructure",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["DATABASE_URL"],
        "integration_status": "live",
        "description": "Primary database. Required.",
        "capabilities": ["data_persistence", "transactions"],
    },
    {
        "provider_key": "redis",
        "display_name": "Redis",
        "category": "infrastructure",
        "provider_type": "primary",
        "is_primary": True,
        "is_fallback": False,
        "is_optional": False,
        "env_keys": ["REDIS_URL", "CELERY_BROKER_URL"],
        "integration_status": "live",
        "description": "Cache, rate limiting, Celery broker. Required.",
        "capabilities": ["caching", "rate_limiting", "task_queue"],
    },
    # ── Observability ──────────────────────────────────────────────────────
    {
        "provider_key": "sentry",
        "display_name": "Sentry",
        "category": "observability",
        "provider_type": "optional",
        "is_primary": False,
        "is_fallback": False,
        "is_optional": True,
        "env_keys": ["SENTRY_DSN"],
        "integration_status": "partial",
        "description": "Error tracking and performance monitoring.",
        "capabilities": ["error_tracking", "performance_monitoring"],
    },
]


PROVIDER_DEPENDENCIES: list[dict[str, Any]] = [
    {
        "provider_key": "claude",
        "module_path": "system.reasoning",
        "dependency_type": "primary",
        "description": "Primary reasoning model for planning, decisions, copilot intelligence",
    },
    {
        "provider_key": "openai",
        "module_path": "packages.provider_clients.media_providers.OpenAIRealtimeAdapter",
        "dependency_type": "optional",
        "description": "Realtime voice/media only",
    },
    {
        "provider_key": "tavus",
        "module_path": "packages.provider_clients.media_providers.TavusAdapter",
        "dependency_type": "primary",
        "description": "Avatar video generation pipeline",
    },
    {
        "provider_key": "elevenlabs",
        "module_path": "packages.provider_clients.media_providers.ElevenLabsAdapter",
        "dependency_type": "primary",
        "description": "Voice synthesis pipeline",
    },
    {
        "provider_key": "heygen",
        "module_path": "packages.provider_clients.media_providers.HeyGenLiveAvatarAdapter",
        "dependency_type": "optional",
        "description": "Live avatar streaming",
    },
    {
        "provider_key": "stripe",
        "module_path": "packages.clients.external_clients.StripePaymentClient",
        "dependency_type": "primary",
        "description": "Payment connector sync + webhook verification",
    },
    {
        "provider_key": "stripe",
        "module_path": "apps.api.routers.webhooks.stripe_webhook",
        "dependency_type": "primary",
        "description": "Stripe webhook endpoint",
    },
    {
        "provider_key": "shopify",
        "module_path": "packages.clients.external_clients.ShopifyOrderClient",
        "dependency_type": "optional",
        "description": "Shopify batch order sync",
    },
    {
        "provider_key": "shopify",
        "module_path": "apps.api.routers.webhooks.shopify_webhook",
        "dependency_type": "optional",
        "description": "Shopify webhook endpoint",
    },
    {
        "provider_key": "buffer",
        "module_path": "packages.clients.external_clients.BufferClient",
        "dependency_type": "primary",
        "description": "Buffer social distribution",
    },
    {
        "provider_key": "buffer",
        "module_path": "apps.api.services.buffer_distribution_service",
        "dependency_type": "primary",
        "description": "Buffer publish/sync/blockers",
    },
    {
        "provider_key": "meta_ads",
        "module_path": "packages.clients.external_clients.MetaAdsClient",
        "dependency_type": "optional",
        "description": "Meta ad reporting import",
    },
    {
        "provider_key": "google_ads",
        "module_path": "packages.clients.external_clients.GoogleAdsClient",
        "dependency_type": "optional",
        "description": "Google ad reporting import",
    },
    {
        "provider_key": "tiktok_ads",
        "module_path": "packages.clients.external_clients.TikTokAdsClient",
        "dependency_type": "optional",
        "description": "TikTok ad reporting import",
    },
    {
        "provider_key": "crm",
        "module_path": "apps.api.services.live_execution_service.run_crm_sync",
        "dependency_type": "optional",
        "description": "CRM contact sync",
    },
    {
        "provider_key": "smtp",
        "module_path": "packages.clients.external_clients.SmtpEmailClient",
        "dependency_type": "primary",
        "description": "Email send execution",
    },
    {
        "provider_key": "esp",
        "module_path": "apps.api.services.live_execution_service.execute_pending_emails",
        "dependency_type": "optional",
        "description": "ESP-based email delivery",
    },
    {
        "provider_key": "twilio",
        "module_path": "packages.clients.external_clients.TwilioSmsClient",
        "dependency_type": "primary",
        "description": "SMS send execution",
    },
    {
        "provider_key": "slack",
        "module_path": "packages.notifications.adapters.SlackWebhookAdapter",
        "dependency_type": "optional",
        "description": "Operator alert delivery via Slack",
    },
    {
        "provider_key": "s3",
        "module_path": "workers.generation_worker",
        "dependency_type": "optional",
        "description": "Media asset storage",
    },
    {
        "provider_key": "postgres",
        "module_path": "packages.db.session",
        "dependency_type": "required",
        "description": "All data persistence",
    },
    {
        "provider_key": "redis",
        "module_path": "workers.celery_app",
        "dependency_type": "required",
        "description": "Task queue and caching",
    },
    {
        "provider_key": "sentry",
        "module_path": "apps.api.main",
        "dependency_type": "optional",
        "description": "Error tracking (initialized on startup if DSN set)",
    },
    {
        "provider_key": "gemini_flash",
        "module_path": "packages.clients.ai_clients.GeminiFlashClient",
        "dependency_type": "primary",
        "description": "Standard-tier text generation",
    },
    {
        "provider_key": "deepseek",
        "module_path": "packages.clients.ai_clients.DeepSeekClient",
        "dependency_type": "primary",
        "description": "Bulk text scanning / hashtags / SEO",
    },
    {
        "provider_key": "gpt_image",
        "module_path": "packages.clients.ai_clients.GPTImageClient",
        "dependency_type": "primary",
        "description": "Hero image generation",
    },
    {
        "provider_key": "imagen4",
        "module_path": "packages.clients.ai_clients.Imagen4Client",
        "dependency_type": "primary",
        "description": "Bulk image generation",
    },
    {
        "provider_key": "flux",
        "module_path": "packages.clients.ai_clients.FluxClient",
        "dependency_type": "optional",
        "description": "Style variety images",
    },
    {
        "provider_key": "runway",
        "module_path": "packages.clients.ai_clients.RunwayClient",
        "dependency_type": "primary",
        "description": "Hero video generation",
    },
    {
        "provider_key": "kling",
        "module_path": "packages.clients.ai_clients.KlingClient",
        "dependency_type": "primary",
        "description": "Bulk video generation",
    },
    {
        "provider_key": "did",
        "module_path": "packages.clients.ai_clients.DIDClient",
        "dependency_type": "fallback",
        "description": "Budget avatar generation",
    },
    {
        "provider_key": "fish_audio",
        "module_path": "packages.clients.ai_clients.FishAudioClient",
        "dependency_type": "primary",
        "description": "Standard voice generation",
    },
    {
        "provider_key": "voxtral",
        "module_path": "packages.clients.ai_clients.VoxtralClient",
        "dependency_type": "optional",
        "description": "Ultra-budget voice generation",
    },
    {
        "provider_key": "suno",
        "module_path": "packages.clients.ai_clients.SunoClient",
        "dependency_type": "primary",
        "description": "Music generation",
    },
]


def check_provider_credentials(provider: dict[str, Any]) -> dict[str, Any]:
    """Check env vars for a provider and return credential status."""
    env_keys = provider.get("env_keys", [])
    if not env_keys:
        return {"credential_status": "not_required", "is_ready": True, "missing_keys": []}
    missing = [k for k in env_keys if not os.environ.get(k)]
    present = [k for k in env_keys if os.environ.get(k)]
    if not missing:
        return {"credential_status": "configured", "is_ready": True, "missing_keys": []}
    if present:
        return {"credential_status": "partial", "is_ready": False, "missing_keys": missing}
    return {"credential_status": "not_configured", "is_ready": False, "missing_keys": missing}


def audit_all_providers() -> list[dict[str, Any]]:
    """Audit all providers and return enriched registry with live credential status."""
    results = []
    for p in PROVIDER_INVENTORY:
        cred = check_provider_credentials(p)
        entry = {**p, **cred}
        if cred["credential_status"] == "configured" and p["integration_status"] in ("live", "partial"):
            entry["effective_status"] = "live"
        elif cred["credential_status"] == "not_configured" and p["integration_status"] == "live":
            entry["effective_status"] = "blocked_by_credentials"
        else:
            entry["effective_status"] = p["integration_status"]
        results.append(entry)
    return results


def get_provider_blockers(brand_id_str: str) -> list[dict[str, Any]]:
    """Generate blockers for providers with missing credentials."""
    blockers = []
    for p in PROVIDER_INVENTORY:
        cred = check_provider_credentials(p)
        if not cred["is_ready"] and p.get("env_keys"):
            if p["provider_type"] == "primary":
                severity = "high"
            elif p["provider_type"] == "optional":
                severity = "low"
            else:
                severity = "medium"
            blockers.append(
                {
                    "provider_key": p["provider_key"],
                    "blocker_type": "missing_credentials",
                    "severity": severity,
                    "description": f"{p['display_name']} credentials not configured. Missing: {', '.join(cred['missing_keys'])}",
                    "operator_action_needed": f"Set environment variable(s): {', '.join(cred['missing_keys'])}",
                }
            )
    return blockers


def get_dependency_map() -> list[dict[str, Any]]:
    """Return the full dependency map."""
    return PROVIDER_DEPENDENCIES
