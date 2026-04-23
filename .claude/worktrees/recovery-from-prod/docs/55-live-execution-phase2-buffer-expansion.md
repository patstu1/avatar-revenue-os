# Live Execution Phase 2 + Buffer Execution Expansion

## Overview

Phase 2 moves the system from batch-only import to webhook-ready real-time ingestion, automated sequence triggering, payment and checkout connector support, platform analytics auto-pull, ad-platform reporting connectors, and full Buffer lifecycle management. Events are classified and reconciled against truth states so operators can see what is live, what is connector-ready, and what remains blocked until credentials and account linkage are configured.

## 1. Live Execution Phase 2 Architecture

- **Webhook / event ingestion model**
  - `webhook_events` stores each inbound event. **`idempotency_key`** is unique and used for deduplication so retries and duplicate deliveries do not double-process.
  - **`external_event_ingestions`** rolls up batch-oriented summaries per brand/source (counts received, processed, skipped, failed, status).
- **Supported sources (design / classification)**  
  Stripe, Shopify (payment); HubSpot (CRM); Mailchimp, SendGrid, ConvertKit (email); Twilio (SMS); Buffer (social); Meta, Google, TikTok (ads). Additional sources can be ingested and classified as known or unknown.
- **Source classification**  
  Every event receives **`source`**, **`source_category`** (for example `payment`, `crm`, `email`, `sms`, `social`, `ads`, `platform_analytics`), and truth-oriented labeling derived from the classification engine.
- **Processing pipeline**  
  **Webhook received → classified → processed → triggers evaluated → actions created** (sequence trigger rows and downstream operator-facing signals).

## 2. Sequence Trigger System

- **Trigger rules (examples)**  
  - **Purchase** → conversion sequence (`start_conversion_sequence`).  
  - **High-value purchase** (for example conversion value above configured threshold) → upsell path (`create_upsell_offer`).  
  - **subscription_cancelled** → reactivation sequence plus retention flags.  
  - **CRM-oriented events** (deal stage changes, contact updates, leads, or CRM-category engagement) → **update_crm_stage** and related lifecycle handling.
- **Table: `sequence_trigger_actions`**  
  Columns include **`trigger_source`**, **`trigger_event_type`**, **`action_type`**, **`status`**, and **`retry_count`** for retry support.
- **Worker**  
  Celery Beat schedules **`process_sequence_triggers`** every **10 minutes** (`*/10`).

## 3. Payment / Checkout Connectors

- **Supported**  
  Stripe and Shopify (connector-ready implementations; incremental sync semantics in service layer).
- **Table: `payment_connector_syncs`**  
  Tracks sync operations, **`credential_status`**, **`orders_imported`**, **`revenue_imported`**, refunds, cursors, and error/detail JSON.
- **Blocked by credentials**  
  Sync remains blocked until **`STRIPE_API_KEY`** and **`SHOPIFY_API_KEY`** (per provider) are present in the environment as expected by the API service.
- **When configured**  
  Incremental sync pulls orders and normalizes them into conversion-oriented event processing where applicable.

## 4. Platform Analytics Auto-Pull

- **Supported (connector-ready)**  
  Buffer analytics, YouTube Analytics, Instagram Insights, TikTok Analytics (and related `platform_analytics` sources in the classification map).
- **Table: `platform_analytics_syncs`**  
  Includes **`reconciliation_status`**, **`attribution_refreshed`**, metrics and match counts, **`credential_status`**, and operator-facing blocker fields.
- **Worker**  
  **`run_analytics_auto_pull`** runs on a **2-hour** cadence (Celery: minute `15`, `hour="*/2"`).
- **Blocked by credentials**  
  Until the relevant platform API keys (and configuration) are set, sync rows reflect missing or partial credentials rather than successful pulls.

## 5. Ad-Platform Reporting Connectors

- **Supported (connector-ready)**  
  Meta Ads, Google / YouTube Ads, TikTok Ads (`meta_ads`, `google_ads`, `tiktok_ads`).
- **Table: `ad_reporting_imports`**  
  Stores **`spend_imported`**, **`impressions_imported`**, **`clicks_imported`**, **`conversions_imported`**, **`revenue_attributed`**, and related campaign counts.
- **Source classification**  
  Rows use **`source_classification`** defaulting to **`ads`**.
- **Reconciliation**  
  **`reconciliation_status`** supports **clean**, **mismatch**, and **unreconciled** style outcomes (aligned with import and attribution logic).
- **Worker**  
  **`run_ad_reporting_import`** every **4 hours** (Celery: minute `20`, `hour="*/4"`).
- **Blocked by credentials**  
  Requires platform API keys **and** ad **account IDs** where the service enforces `account_id_present`.

## 6. Buffer Execution Lifecycle

### Truth States

Happy path progression:

**queued_internally → selected_for_buffer → submitted_to_buffer → accepted_by_buffer → scheduled_in_buffer → published_by_buffer**

Error and control states include **`failed_in_buffer`**, **`degraded`**, **`unknown`**, and **`blocked`**.

**Table: `buffer_execution_truth`**  
Per publish job (and optional **`content_item_id`**) truth tracking: **`truth_state`**, **`previous_truth_state`**, duplicate/stale flags, conflict and **`operator_action`** text, and **`details_json`**.

**Table: `buffer_execution_events`**  
Append-only-style transition log: **`event_type`**, **`from_state`**, **`to_state`**, **`details_json`**.

### Duplicate-Submit Protection

**`check_duplicate_submit`** uses a composite key **`content_item_id` + `platform`** (encoded as `"{content_item_id}:{platform}"` against a set of keys for already-submitted work). When true, the job is treated as a duplicate submit and flagged (**`is_duplicate`**) so the same content is not pushed again for that platform.

### Stale Job Detection

Jobs **older than 48 hours** in a **non-terminal** state (success terminal: **`published_by_buffer`**) are marked **stale**. The dedicated worker runs **hourly** (Celery: minute `45` each hour) and sets stale flags with operator guidance such as reviewing stuck executions.

### Retry / Backoff Rules

- **Exponential backoff**  
  Base **`RETRY_BACKOFF_BASE_SECONDS` = 60**, multiplier **2**, so delay ≈ **60 × 2^(attempt − 1)** seconds for attempt **`n`** (implementation uses `max(1, attempt_number)`).
- **Escalation**  
  After **3** failed attempts (**`ESCALATION_THRESHOLD`**), backoff computation sets escalation / **`next_action`** to escalate.
- **Max retries**  
  **5** attempts (**`MAX_BUFFER_RETRIES`**) before truth is forced toward **`blocked`** with operator action **`max_retries_exceeded_review`**.
- **Table: `buffer_retry_records`**  
  One row per attempt: **`attempt_number`**, **`retry_reason`**, **`backoff_seconds`**, **`next_retry_at`**, **`outcome`**, **`escalated`**, **`error_message`**.

### Manual Retry and Cancel

- **Retry path**  
  From **`failed_in_buffer`**, valid transitions include back to **`submitted_to_buffer`** via recompute / operator-driven flows (see **`BUFFER_TRUTH_TRANSITIONS`** in the engine).
- **Cancel / pause**  
  Set **`truth_state`** to **`blocked`** to stop automated progression.
- **Resubmission**  
  From **`blocked`**, transition **`queued_internally`** allows internal re-queuing for a fresh cycle.

## 7. Buffer Capability / Readiness Checks

- **Per-profile validation**  
  Readiness combines **`credential_valid`**, presence of **`buffer_profile_id`** mapping, **`is_active`**, and **`platform_supported`** (see **`evaluate_buffer_profile_readiness`**).
- **Supported platforms**  
  Engine includes Twitter/X, Facebook, Instagram, LinkedIn, Pinterest, TikTok, YouTube, Threads, and additional networks (for example Mastodon, Bluesky) in the supported set.
- **Unsupported modes**  
  Non-supported platforms populate **`unsupported_modes`** (JSON list) on **`buffer_capability_checks`**.
- **Table: `buffer_capability_checks`**  
  **`profile_ready`**, flags for missing mapping / inactive profile, **`capabilities_json`**, **`blocker_summary`**, **`operator_action`**.
- **Worker**  
  **`recompute_buffer_capabilities`** every **2 hours** (Celery: minute `50`, `hour="*/2"`).

## 8. What is Live vs Connector-Ready vs Blocked by Credentials

| Capability | Status |
|------------|--------|
| Webhook ingestion (generic) | **Live** — authenticated brand-scoped POST accepts flexible source/event_type |
| Stripe webhook verification | **Live** — POST /api/v1/webhooks/stripe with real HMAC-SHA256 verification |
| Shopify webhook verification | **Live** — POST /api/v1/webhooks/shopify with real HMAC-SHA256 verification |
| Stripe batch sync (charges) | **Live when configured** — real StripePaymentClient; blocked until STRIPE_API_KEY |
| Shopify batch order sync | **Live when configured** — real ShopifyOrderClient; blocked until SHOPIFY_SHOP_DOMAIN + SHOPIFY_ACCESS_TOKEN |
| Buffer submit / sync | **Live when configured** — real BufferClient; blocked until BUFFER_API_KEY |
| Meta / Google / TikTok ads | **Live when configured** — real API clients; blocked until platform API keys + account IDs |
| YouTube / Instagram / TikTok analytics | **Connector-ready** — blocked until platform API keys |
| CRM (HubSpot) | **Connector-ready** — blocked until CRM_API_KEY |
| Email (SMTP) | **Live when configured** — real SmtpEmailClient via aiosmtplib; blocked until SMTP_HOST + SMTP_FROM_EMAIL |
| SMS (Twilio) | **Live when configured** — real TwilioSmsClient via httpx; blocked until TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM_NUMBER |

### Buffer Webhook Receiver — Design Decision

Buffer v1 API does **not** provide server-to-server webhook callbacks for post status changes. Buffer notifies users via in-app UI and email, not via programmatic webhooks. Therefore:

- **Polling is the source of truth** for Buffer job status via `BufferClient.get_update()`, run by the `lec2-buffer-truth-every-15m` worker.
- No dedicated `POST /webhooks/buffer` endpoint is implemented because Buffer has no mechanism to call it.
- If Buffer adds webhook support in a future API version, the `webhook_events` table and ingestion pipeline are already webhook-ready.

## 9. API Routes

Base path for Phase 2: **`/api/v1/brands`**. All routes below are prefixed with that base (replace `{brand_id}` with the brand UUID).

| # | Method | Path |
|---|--------|------|
| 1 | `POST` | `/{brand_id}/webhook-events` |
| 2 | `GET` | `/{brand_id}/webhook-events` |
| 3 | `GET` | `/{brand_id}/event-ingestions` |
| 4 | `POST` | `/{brand_id}/event-ingestions/recompute` |
| 5 | `GET` | `/{brand_id}/sequence-triggers` |
| 6 | `POST` | `/{brand_id}/sequence-triggers/process` |
| 7 | `GET` | `/{brand_id}/payment-syncs` |
| 8 | `POST` | `/{brand_id}/payment-syncs/run` |
| 9 | `GET` | `/{brand_id}/analytics-syncs` |
| 10 | `POST` | `/{brand_id}/analytics-syncs/run` |
| 11 | `GET` | `/{brand_id}/ad-imports` |
| 12 | `POST` | `/{brand_id}/ad-imports/run` |
| 13 | `GET` | `/{brand_id}/buffer-execution-truth` |
| 14 | `POST` | `/{brand_id}/buffer-execution-truth/recompute` |
| 15 | `GET` | `/{brand_id}/buffer-retries` |
| 16 | `POST` | `/{brand_id}/buffer-retries/recompute` |
| 17 | `GET` | `/{brand_id}/buffer-capabilities` |
| 18 | `POST` | `/{brand_id}/buffer-capabilities/recompute` |

**Query parameters (selected routes)**  

- **`POST .../payment-syncs/run`**: `provider` (default `stripe`).  
- **`POST .../analytics-syncs/run`**: `source` (default `buffer`).  
- **`POST .../ad-imports/run`**: `platform` (default `meta_ads`).

**Auth**  

- Read and webhook ingest: authenticated user with access to the brand.  
- Recompute / process / run endpoints: **operator** role (see `OperatorUser` dependency), with recompute rate limiting where applied.

Related **Buffer Distribution** APIs (profiles, publish jobs, status sync, blockers, root profile update and submit) are mounted under **`/api/v1/brands`** and **`/api/v1`** in `buffer_distribution` routers — see router tags in `apps/api/main.py`.

## 10. Workers

Celery Beat entries in `workers/celery_app.py` (task name → schedule):

| # | Beat key (id) | Task | Frequency |
|---|----------------|------|-----------|
| 1 | `lec2-webhook-processing-every-5m` | `workers.live_execution_phase2_worker.tasks.process_webhook_events` | Every **5** minutes (`minute="*/5"`) |
| 2 | `lec2-sequence-triggers-every-10m` | `workers.live_execution_phase2_worker.tasks.process_sequence_triggers` | Every **10** minutes (`minute="*/10"`) |
| 3 | `lec2-payment-sync-every-30m` | `workers.live_execution_phase2_worker.tasks.run_payment_connector_sync` | Every **30** minutes (`minute="*/30"`) |
| 4 | `lec2-analytics-pull-every-2h` | `workers.live_execution_phase2_worker.tasks.run_analytics_auto_pull` | Every **2** hours (minute **15**, `hour="*/2"`) |
| 5 | `lec2-ad-reporting-every-4h` | `workers.live_execution_phase2_worker.tasks.run_ad_reporting_import` | Every **4** hours (minute **20**, `hour="*/4"`) |
| 6 | `lec2-buffer-truth-every-15m` | `workers.live_execution_phase2_worker.tasks.recompute_buffer_execution_truth` | Every **15** minutes (`minute="*/15"`) |
| 7 | `lec2-stale-buffer-jobs-every-1h` | `workers.live_execution_phase2_worker.tasks.detect_stale_buffer_jobs` | **Hourly** at minute **45** |
| 8 | `lec2-buffer-capabilities-every-2h` | `workers.live_execution_phase2_worker.tasks.recompute_buffer_capabilities` | Every **2** hours (minute **50**, `hour="*/2"`) |

The worker package **`workers.live_execution_phase2_worker`** must be included in Celery **`autodiscover_tasks`** (already configured alongside other workers).

## 11. Migration

- **Revision**  
  **`lec_phase2_001`** — merge migration from **`b3c4d5e6f7g8`** and **`cra_phase_d_001`** (`down_revision` tuple in `packages/db/alembic/versions/lec_phase2_buffer_expansion.py`).
- **Creates 10 tables**
  1. `webhook_events`  
  2. `external_event_ingestions`  
  3. `sequence_trigger_actions`  
  4. `payment_connector_syncs`  
  5. `platform_analytics_syncs`  
  6. `ad_reporting_imports`  
  7. `buffer_execution_truth`  
  8. `buffer_execution_events`  
  9. `buffer_retry_records`  
  10. `buffer_capability_checks`  

Apply with your normal Alembic workflow from `packages/db` (for example `alembic upgrade head` against the configured database URL).
