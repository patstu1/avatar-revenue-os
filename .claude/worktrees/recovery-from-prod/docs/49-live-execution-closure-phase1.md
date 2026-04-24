# Live Execution Closure — Phase 1

## Purpose

Phase 1 closes the real-world execution gap between internal decision-making and external truth / downstream action. Before this phase, most measurement was synthetic/proxy and messaging execution had no persisted path.

After Phase 1:
- External analytics and conversion data can be ingested with source classification and truth-level reconciliation.
- Experiment outcomes can be imported from live sources, with automatic preference for live truth over proxy estimates.
- Email and SMS execution has a persisted queue with attempt tracking, failure handling, and blocker detection.
- CRM contact sync has a push-based lifecycle with credential blocking.
- All credential/config gaps are surfaced as structured messaging blockers with operator actions.

---

## Architecture

### Tables (11 new)

| Table | Purpose |
|---|---|
| `analytics_imports` | Batch import records for external analytics |
| `analytics_events` | Individual analytics events (views, clicks, engagement) |
| `conversion_imports` | Batch import records for conversion/revenue data |
| `conversion_events` | Individual conversion events (purchase, signup, affiliate payout) |
| `experiment_observation_imports` | Batch import records for live experiment observations |
| `experiment_live_results` | Individual live observation results with truth reconciliation |
| `crm_contacts` | Contacts synced to/from external CRM |
| `crm_syncs` | Batch CRM sync operation records |
| `email_send_requests` | Queued email sends with status tracking |
| `sms_send_requests` | Queued SMS sends with status tracking |
| `messaging_blockers` | Credential/config blockers preventing execution |

### API Endpoints (18)

| Method | Path | Purpose |
|---|---|---|
| GET | `/brands/{id}/analytics-imports` | List analytics imports |
| POST | `/brands/{id}/analytics-imports` | Create analytics import with events |
| GET | `/brands/{id}/analytics-events` | List analytics events |
| POST | `/brands/{id}/analytics-events/recompute` | Reconcile truth levels |
| GET | `/brands/{id}/conversion-imports` | List conversion imports |
| POST | `/brands/{id}/conversion-imports` | Create conversion import |
| GET | `/brands/{id}/conversion-events` | List conversion events |
| POST | `/brands/{id}/conversion-events/recompute` | Reconcile truth levels |
| GET | `/brands/{id}/experiment-observation-imports` | List experiment imports |
| POST | `/brands/{id}/experiment-observation-imports` | Create experiment import |
| GET | `/brands/{id}/experiment-live-results` | List live experiment results |
| POST | `/brands/{id}/experiment-live-results/recompute` | Reconcile truth levels |
| GET | `/brands/{id}/crm-contacts` | List CRM contacts |
| POST | `/brands/{id}/crm-contacts` | Create contact |
| GET | `/brands/{id}/crm-syncs` | List CRM sync records |
| POST | `/brands/{id}/crm-syncs/recompute` | Run CRM sync |
| GET | `/brands/{id}/email-send-requests` | List email requests |
| POST | `/brands/{id}/email-send-requests` | Queue email send |
| GET | `/brands/{id}/sms-send-requests` | List SMS requests |
| POST | `/brands/{id}/sms-send-requests` | Queue SMS send |
| GET | `/brands/{id}/messaging-blockers` | List messaging blockers |
| POST | `/brands/{id}/messaging-blockers/recompute` | Recompute blockers |

### Workers (6 recurring tasks)

| Task | Schedule | Purpose |
|---|---|---|
| `sync_analytics` | Every 1h | Reconcile analytics truth levels |
| `sync_experiment_truth` | Every 2h | Reconcile experiment truth levels |
| `run_crm_sync` | Every 1h | Push pending contacts to CRM |
| `execute_emails` | Every 5m | Execute queued emails |
| `execute_sms` | Every 5m | Execute queued SMS |
| `recompute_messaging_blockers` | Every 1h | Detect credential/config gaps |

### Dashboards (5)

1. **Analytics / Attribution Truth** — imports, events, conversions with truth-level visibility
2. **Experiment Truth** — observation imports, live results with truth reconciliation
3. **CRM / Audience Sync** — contact management, sync history, add contacts
4. **Email & SMS Execution** — queue email/SMS, track status, see failures
5. **Messaging Blockers** — all credential/config blockers with operator actions

---

## Truth Levels

Every analytics event, conversion event, and experiment result carries a `truth_level` field:

| Level | Meaning |
|---|---|
| `live_verified` | Confirmed by multiple live sources |
| `live_import` | Imported from an external live source |
| `operator_override` | Manually set by operator |
| `synthetic_proxy` | Computed internally, not from live data |
| `unknown` | Source unknown or unclassified |

The `reconcile_truth` engine always prefers higher-priority truth levels. When live data arrives for something previously proxy-only, the truth level is upgraded automatically.

---

## Source Categories

Analytics and conversion imports are automatically classified:

| Category | Example Sources |
|---|---|
| `social` | Buffer, TikTok, Instagram, YouTube, X, Reddit, LinkedIn, Facebook |
| `checkout` | Stripe, Shopify, Gumroad, PayPal |
| `affiliate` | ClickBank, Impact, ShareASale |
| `email` | Mailchimp, ConvertKit, ActiveCampaign, SendGrid |
| `sms` | Twilio, MessageBird |
| `ads` | Google Ads, Meta Ads, TikTok Ads |
| `crm` | HubSpot, Salesforce, Pipedrive |
| `manual` | Unknown or unclassified sources |

---

## Experiment Truth Reconciliation

When live observations arrive for experiments:
- **Sample >= 30**: Live value used directly, confidence scaled by sample size
- **Sample 10–29**: Blended (30% proxy + 70% live), confidence capped at 0.7
- **Sample < 10**: Proxy value retained, truth_level stays `synthetic_proxy`

This prevents premature overreaction to tiny samples while eagerly adopting meaningful live data.

---

## Execution vs Queued Boundaries

| Module | Behavior |
|---|---|
| Analytics import | **Executes immediately** — events persisted on POST |
| Conversion import | **Executes immediately** — events persisted on POST |
| Experiment import | **Executes immediately** — results persisted on POST |
| CRM sync | **Queued** — contacts created as `pending`, sync worker pushes when `CRM_API_KEY` is set |
| Email send | **Queued** — requests created as `queued`, worker executes when `SMTP_HOST` or `ESP_API_KEY` is set |
| SMS send | **Queued** — requests created as `queued`, worker executes when `SMS_API_KEY` is set |

---

## Credential Boundaries

| Credential | Purpose | Env Variable |
|---|---|---|
| SMTP config | Direct email sending | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` |
| ESP API key | Templated/sequence emails via ESP | `ESP_API_KEY` |
| SMS API key | SMS sending via Twilio or similar | `SMS_API_KEY` |
| CRM API key | Contact sync with external CRM | `CRM_API_KEY` |
| CRM provider | Which CRM provider to use | `CRM_PROVIDER` |

Without credentials, the system:
1. Queues the send request with `status=failed` and error message
2. Creates a structured `MessagingBlocker` with exact operator action
3. Does not fail silently

---

## What Is Now Live Truth vs Still Proxy

| Area | Status |
|---|---|
| Analytics ingestion layer | **Live-ready** — accepts external data, classifies, reconciles |
| Conversion ingestion layer | **Live-ready** — accepts revenue data, computes profit |
| Experiment truth ingestion | **Live-ready** — imports live observations, reconciles with proxy |
| CRM contact sync | **Execution-ready** — blocked only by `CRM_API_KEY` |
| Email execution | **Execution-ready** — blocked only by `SMTP_HOST` / `ESP_API_KEY` |
| SMS execution | **Execution-ready** — blocked only by `SMS_API_KEY` |
| Internal scoring/decisions | Still `synthetic_proxy` until live data is ingested |
| Platform-native analytics | Still requires platform API credentials (Buffer analytics available via import) |
| Real-time webhooks | Not yet implemented — batch import only for Phase 1 |

---

## Integration with Other Modules

- **Brain Architecture**: Brain memory, decisions, and readiness checks can now reference imported live data truth levels
- **Buffer Distribution**: Buffer publish status flows into analytics events via import
- **Autonomous Execution**: Experiment truth ingestion feeds into experiment decision loop closure
- **Revenue Ceiling / MXP**: Conversion events feed real revenue data into revenue pressure and contribution engines
- **Recovery / Self-Healing**: Email/SMS failures trigger messaging blockers, visible to the brain escalation system
