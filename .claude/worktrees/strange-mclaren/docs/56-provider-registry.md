# Provider Registry — Source of Truth

## Overview

The provider registry is the canonical inventory of every API, AI provider, connector, platform, webhook source, delivery tool, analytics source, and execution service used by the AI Avatar Revenue OS.

Every external service the system communicates with — or plans to communicate with — is tracked here. The registry records:

- **Credential status** — whether the required env vars are configured
- **Integration status** — whether the adapter code is live, partial, or planned
- **Effective status** — the runtime truth combining both signals
- **Dependencies** — which code modules consume each provider

## Provider Inventory (23 providers)

### AI / Reasoning

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Claude (Anthropic) | `claude` | **Primary** reasoning / copilot | Planned (SDK not yet wired; system intelligence is rule-based) | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | Fallback / media only | Partial (Realtime voice adapter exists) | `OPENAI_API_KEY` |

### AI / Media

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Tavus | `tavus` | **Primary** avatar video | Partial (adapter exists) | `TAVUS_API_KEY` |
| ElevenLabs | `elevenlabs` | **Primary** voice synthesis | Partial (adapter exists) | `ELEVENLABS_API_KEY` |
| HeyGen | `heygen` | Optional live avatar | Partial (adapter exists) | `HEYGEN_API_KEY` |
| Fallback (Template) | `fallback_media` | Built-in fallback | **Live** (always available) | — |

### Payment

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Stripe | `stripe` | **Primary** payment processing | **Live** (real HTTP client) | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Shopify | `shopify` | Optional e-commerce | **Live** (real HTTP client) | `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_WEBHOOK_SECRET` |

### Social Distribution

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Buffer | `buffer` | **Primary** social publish | **Live** (real HTTP client) | `BUFFER_API_KEY` |

### Ad Platforms

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Meta Ads | `meta_ads` | Optional campaign reporting | **Live** (real HTTP client) | `META_ADS_ACCESS_TOKEN`, `META_ADS_ACCOUNT_ID` |
| Google Ads | `google_ads` | Optional campaign reporting | **Live** (real HTTP client) | `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_OAUTH_TOKEN` |
| TikTok Ads | `tiktok_ads` | Optional campaign reporting | **Live** (real HTTP client) | `TIKTOK_ADS_ACCESS_TOKEN`, `TIKTOK_ADS_ADVERTISER_ID` |

### CRM

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| CRM (HubSpot/generic) | `crm` | Optional contact sync | Partial (adapter exists, API stubbed) | `CRM_API_KEY`, `CRM_PROVIDER` |

### Email

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| SMTP Email | `smtp` | **Primary** email delivery | **Live** (aiosmtplib) | `SMTP_HOST`, `SMTP_FROM_EMAIL` |
| ESP (Mailchimp/SendGrid) | `esp` | Optional bulk/transactional email | Partial (adapter exists) | `ESP_API_KEY` |

### SMS

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Twilio | `twilio` | **Primary** SMS delivery | **Live** (REST API) | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` |

### Notifications

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Slack Webhook | `slack` | Optional operator alerts | Partial (webhook adapter exists) | `SLACK_WEBHOOK_URL` |
| In-App Notifications | `in_app` | **Primary** internal notifications | **Live** (always available) | — |

### Storage

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| S3-Compatible Storage | `s3` | Optional media asset storage | Partial (adapter exists) | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` |

### Infrastructure

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| PostgreSQL | `postgres` | **Primary** database | **Live** (required) | `DATABASE_URL` |
| Redis | `redis` | **Primary** cache / task broker | **Live** (required) | `REDIS_URL`, `CELERY_BROKER_URL` |

### Observability

| Provider | Key | Role | Integration Status | Env Keys |
|----------|-----|------|--------------------|----------|
| Sentry | `sentry` | Optional error tracking | Partial (initialized on startup if DSN set) | `SENTRY_DSN` |

---

## Primary Model Rule

**Claude (Anthropic) is the designated primary reasoning / copilot model.** OpenAI is used ONLY for the Realtime voice/media adapter. No OpenAI chat completions are imported anywhere in the codebase for reasoning tasks.

---

## What is Live vs Partial vs Planned vs Blocked

| Status | Meaning |
|--------|---------|
| **Live** | Real HTTP adapter exists and the service is called in production when credentials are present |
| **Partial** | Adapter code exists but the integration is not fully wired or only a subset of features is implemented |
| **Planned** | The provider is in the inventory as a future integration; no adapter code yet |
| **Blocked by credentials** | Adapter is live/partial but the required env vars are missing at runtime |
| **Not required** | Provider needs no credentials (e.g., built-in fallback, in-app notifications) |

---

## Dependency Map

Every provider maps to one or more code modules that consume it:

| Provider | Module | Type | Description |
|----------|--------|------|-------------|
| `claude` | `system.reasoning` | primary | Primary reasoning model for planning, decisions, copilot intelligence |
| `openai` | `packages.provider_clients.media_providers.OpenAIRealtimeAdapter` | optional | Realtime voice/media only |
| `tavus` | `packages.provider_clients.media_providers.TavusAdapter` | primary | Avatar video generation pipeline |
| `elevenlabs` | `packages.provider_clients.media_providers.ElevenLabsAdapter` | primary | Voice synthesis pipeline |
| `heygen` | `packages.provider_clients.media_providers.HeyGenLiveAvatarAdapter` | optional | Live avatar streaming |
| `stripe` | `packages.clients.external_clients.StripePaymentClient` | primary | Payment connector sync + webhook verification |
| `stripe` | `apps.api.routers.webhooks.stripe_webhook` | primary | Stripe webhook endpoint |
| `shopify` | `packages.clients.external_clients.ShopifyOrderClient` | optional | Shopify batch order sync |
| `shopify` | `apps.api.routers.webhooks.shopify_webhook` | optional | Shopify webhook endpoint |
| `buffer` | `packages.clients.external_clients.BufferClient` | primary | Buffer social distribution |
| `buffer` | `apps.api.services.buffer_distribution_service` | primary | Buffer publish/sync/blockers |
| `meta_ads` | `packages.clients.external_clients.MetaAdsClient` | optional | Meta ad reporting import |
| `google_ads` | `packages.clients.external_clients.GoogleAdsClient` | optional | Google ad reporting import |
| `tiktok_ads` | `packages.clients.external_clients.TikTokAdsClient` | optional | TikTok ad reporting import |
| `crm` | `apps.api.services.live_execution_service.run_crm_sync` | optional | CRM contact sync |
| `smtp` | `packages.clients.external_clients.SmtpEmailClient` | primary | Email send execution |
| `esp` | `apps.api.services.live_execution_service.execute_pending_emails` | optional | ESP-based email delivery |
| `twilio` | `packages.clients.external_clients.TwilioSmsClient` | primary | SMS send execution |
| `slack` | `packages.notifications.adapters.SlackWebhookAdapter` | optional | Operator alert delivery via Slack |
| `s3` | `workers.generation_worker` | optional | Media asset storage |
| `postgres` | `packages.db.session` | required | All data persistence |
| `redis` | `workers.celery_app` | required | Task queue and caching |
| `sentry` | `apps.api.main` | optional | Error tracking (initialized on startup if DSN set) |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/brands/{id}/providers` | List all registered providers for a brand |
| `GET` | `/api/v1/brands/{id}/providers/readiness` | Readiness report with credential checks |
| `GET` | `/api/v1/brands/{id}/providers/dependencies` | Full dependency map |
| `GET` | `/api/v1/brands/{id}/providers/blockers` | Providers blocked by missing credentials |
| `POST` | `/api/v1/brands/{id}/providers/audit` | Run a full provider audit (refresh credential status) |

---

## Dashboard Pages

| Page | Path | Description |
|------|------|-------------|
| Provider Inventory | `/dashboard/provider-registry` | Full provider table with credential/integration/effective status |
| Provider Readiness | `/dashboard/provider-readiness` | Ready/not-ready view with missing env keys |
| Dependency Map | `/dashboard/provider-dependencies` | Code modules grouped by provider |
| Provider Blockers | `/dashboard/provider-blockers` | Cards showing blockers with severity and action needed |

---

## How to Maintain

1. **Refresh the registry**: Run `POST /brands/{id}/providers/audit` to re-check all credential statuses
2. **Check blockers**: `GET /brands/{id}/providers/blockers` lists every provider missing credentials
3. **Set env vars**: Each blocker includes a `missing_env_keys` field — set those in your `.env` or deployment config
4. **Provider registry auto-detects** credential presence at audit time — no manual toggling required
5. **Add new providers**: Edit `packages/scoring/provider_registry_engine.py` — add to `PROVIDER_INVENTORY` and `PROVIDER_DEPENDENCIES`

---

## Credential Check Logic

```
for each provider:
  if env_keys is empty → not_required, is_ready=True
  if all env_keys present → configured, is_ready=True
  if some env_keys present → partial, is_ready=False
  if no env_keys present → not_configured, is_ready=False
```

The `effective_status` combines credential status with integration status:
- `configured` + `live`/`partial` → **live**
- `not_configured` + `live` → **blocked_by_credentials**
- Otherwise → inherits `integration_status`
