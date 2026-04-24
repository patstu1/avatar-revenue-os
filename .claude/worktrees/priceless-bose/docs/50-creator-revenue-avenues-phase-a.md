# 50 — Creator Revenue Avenues Pack — Phase A

## Overview

Phase A introduces the Creator Revenue Avenues system — a dedicated module for identifying, scoring, planning, and tracking revenue opportunities across three distinct creator monetization paths:

1. **UGC / Creative Services** — selling content production services to brands and businesses
2. **Services / Consulting** — selling strategic advisory, implementation, and consulting
3. **Premium Access / Concierge** — monetizing audience access via memberships, VIP tiers, and exclusive guidance

## Architecture

### Database Tables (6)

| Table | Purpose |
|---|---|
| `creator_revenue_opportunities` | Unified opportunity ledger across all avenues |
| `ugc_service_actions` | UGC/creative service execution plans with pricing and steps |
| `service_consulting_actions` | Consulting/advisory execution plans with tiers |
| `premium_access_actions` | Premium access/concierge execution plans with revenue models |
| `creator_revenue_blockers` | Blockers preventing revenue avenue execution |
| `creator_revenue_events` | Realized revenue events tied to avenues |

### Engine Logic

Located in `packages/scoring/creator_revenue_engine.py`:

- **`score_ugc_opportunity()`** — Scores 7 UGC service types based on audience size, content count, niche, avatar availability, and account count. Produces expected value, margin, price band, and execution steps per type.
- **`score_consulting_opportunities()`** — Scores 8 consulting service types with tier classification (entry/standard/premium) and buyer targeting. Niche-specific value multipliers for tech/saas/finance.
- **`score_premium_access_opportunities()`** — Scores 5 premium access types with community-boosted confidence, recurring vs one-time revenue models, and entry criteria.
- **`detect_creator_revenue_blockers()`** — Detects 6 blocker types: insufficient portfolio, no avatar, no offers, small audience, no payment processor, no landing page. Each blocker includes operator action.
- **`build_revenue_opportunities()`** — Consolidates all avenues into a unified, priority-sorted opportunity list.

### UGC Service Types

| Service Type | Description |
|---|---|
| `ugc_content_production` | Original UGC content for brands |
| `ad_creative_production` | Ad creative with hook variants |
| `short_form_content_packages` | Monthly short-form video packages |
| `spokesperson_avatar_services` | AI spokesperson/avatar packages |
| `editing_repurposing_packages` | Long-form → clip repurposing |
| `campaign_creative_packages` | Full campaign creative bundles |
| `platform_native_creative_bundles` | Platform-specific format bundles |

### Consulting Service Types

| Service Type | Tier | Target Buyer |
|---|---|---|
| `strategic_advisory` | premium | founders/CEOs |
| `implementation_services` | standard | marketing teams |
| `content_strategy_consulting` | standard | creators/brands |
| `automation_consulting` | standard | operations teams |
| `done_for_you_setups` | standard | solopreneurs |
| `audits_roadmaps` | entry | startups |
| `premium_workshops` | premium | teams/cohorts |
| `retained_support` | premium | enterprise clients |

### Premium Access Types

| Access Type | Revenue Model | Entry Criteria |
|---|---|---|
| `premium_membership` | recurring | Minimum 3 months engagement |
| `vip_concierge` | one_time | Previous purchase > $500 |
| `priority_advisory` | recurring | Company revenue > $1M |
| `exclusive_guidance` | recurring | Application required |
| `inner_circle` | recurring | Invitation only |

## API Endpoints (10)

| Method | Path | Purpose |
|---|---|---|
| GET | `/brands/{id}/creator-revenue-opportunities` | List scored opportunities |
| POST | `/brands/{id}/creator-revenue-opportunities/recompute` | Rescore all opportunities |
| GET | `/brands/{id}/ugc-services` | List UGC service plans |
| POST | `/brands/{id}/ugc-services/recompute` | Rescore UGC services |
| GET | `/brands/{id}/service-consulting` | List consulting plans |
| POST | `/brands/{id}/service-consulting/recompute` | Rescore consulting |
| GET | `/brands/{id}/premium-access` | List premium access plans |
| POST | `/brands/{id}/premium-access/recompute` | Rescore premium access |
| GET | `/brands/{id}/creator-revenue-blockers` | List blockers |
| GET | `/brands/{id}/creator-revenue-events` | List revenue events |

All POST recompute endpoints are rate-limited.

## Dashboards (6)

1. **Creator Revenue Hub** — Unified opportunity table sorted by priority
2. **UGC / Creative Services** — Service plan cards with pricing and execution steps
3. **Services / Consulting** — Consulting plans with tiers and deal values
4. **Premium Access / Concierge** — Premium offer cards with revenue models
5. **Creator Revenue Blockers** — Blocker list with severity and operator actions
6. **Creator Revenue Events** — Revenue event log with profit tracking

## Workers (4 recurring tasks)

| Task | Schedule | Purpose |
|---|---|---|
| `recompute_creator_revenue` | Every 4 hours | Rescore all opportunities |
| `recompute_ugc_services` | Every 6 hours | Rescore UGC plans |
| `recompute_premium_access` | Every 6 hours | Rescore premium access |
| `recompute_creator_revenue_blockers` | Every 2 hours | Refresh blocker detection |

## Blocker Model

The system detects 6 blocker types:

| Blocker | Severity | Avenue |
|---|---|---|
| `insufficient_portfolio` | high | UGC |
| `no_avatar_configured` | medium | UGC |
| `no_offers_defined` | high | Consulting |
| `audience_too_small` | medium | Premium Access |
| `no_payment_processor` | critical | All |
| `no_landing_page` | medium | All |

Each blocker includes:
- Exact operator action needed
- Severity classification
- Affected avenue type

## Revenue Event Model

Revenue events track realized revenue from creator avenues:
- `avenue_type` — which avenue generated the revenue
- `event_type` — deal_closed, payment_received, subscription_started, etc.
- `revenue`, `cost`, `profit` — financial tracking
- `client_name` — who paid
- Optional link to the `CreatorRevenueOpportunity` that predicted it

## Execution vs Recommendation Boundaries

| Module | Mode |
|---|---|
| Opportunity Scoring | **Recommends only** — surfaces and prioritizes opportunities |
| UGC Service Plans | **Recommends + queues** — generates execution plans, operator executes |
| Consulting Plans | **Recommends + queues** — generates plans, operator negotiates and delivers |
| Premium Access Plans | **Recommends + queues** — generates plans, operator sets up and launches |
| Blocker Detection | **Detects + escalates** — surfaces blockers with operator actions |
| Revenue Events | **Records** — passive event log, not auto-generated |

## Credential / External Dependencies

| Dependency | Status |
|---|---|
| Payment processor (Stripe/PayPal) | Detected as blocker when missing |
| Landing page / service page | Detected as blocker when missing |
| AI Avatar | Detected as blocker for spokesperson services |
| Offer catalog | Detected as blocker for consulting credibility |
| Audience size | Detected as blocker for premium access |

## Test Coverage

- **Unit tests**: Engine logic for all 4 scoring functions + blocker detection + consolidation
- **Integration tests**: DB-backed tests for all recompute paths, event persistence, idempotency, and cross-entity relationships
