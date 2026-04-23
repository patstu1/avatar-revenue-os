# Creator Revenue Avenues — Phase C: Merch, Live Events, Owned Affiliate Program

## Overview

Phase C extends the Creator Revenue Avenues Pack with three new monetization layers:

1. **Merch / Physical Products** — Creator-branded drops, evergreen products, bundles, limited editions, product experiments
2. **Live Events** — Webinars, workshops, creator sessions, paid events, premium Q&A, niche event products
3. **Owned Affiliate Program** — Recruit affiliates for your own offers, tier management, incentive optimization, attribution

These extend the Phase A (UGC, consulting, premium access) and Phase B (licensing, syndication, data products) foundation to cover the complete creator monetization spectrum.

## Tables

| Table | Purpose |
|---|---|
| `merch_actions` | Persisted merch/physical product execution plans per brand |
| `live_event_actions` | Persisted live event execution plans per brand |
| `owned_affiliate_program_actions` | Persisted affiliate program execution plans per brand |
| `creator_revenue_blockers` | Shared blocker table (extended with Phase C detection) |
| `creator_revenue_events` | Shared revenue event table (merch/event/affiliate events) |

## Engine Logic

### Merch (`score_merch_opportunities`)

Evaluates 5 merch types:

| Type | Segment | Price Band |
|---|---|---|
| `creator_branded_drop` | loyal_followers | mid |
| `evergreen_store_product` | general_audience | low |
| `product_line_experiment` | early_adopters | mid |
| `physical_bundle` | high_value_fans | high |
| `limited_edition_release` | collectors_and_superfans | high |

Scoring factors: audience size, avatar presence, niche fit (lifestyle/fitness/fashion boost), content depth.

### Live Events (`score_live_event_opportunities`)

Evaluates 6 event types:

| Type | Audience | Ticket Model |
|---|---|---|
| `webinar` | interested_audience | free_with_upsell |
| `workshop` | skill_seekers | paid |
| `live_creator_session` | fans_and_followers | paid |
| `paid_live_event` | premium_audience | paid |
| `premium_qa_office_hours` | committed_learners | paid |
| `niche_event_product` | niche_professionals | paid |

Scoring factors: content depth, audience size, niche value (tech/business/finance boost).

### Owned Affiliate Program (`score_owned_affiliate_opportunities`)

Evaluates 5 program types:

| Type | Partner | Incentive | Tier |
|---|---|---|---|
| `affiliate_recruitment` | micro_influencers | percentage | standard |
| `affiliate_program_launch` | content_creators | percentage | standard |
| `incentive_model_optimization` | existing_affiliates | tiered_percentage | gold |
| `partner_tier_expansion` | top_performers | tiered_percentage | platinum |
| `affiliate_attribution_setup` | all_affiliates | percentage | standard |

Scoring factors: offer count (critical — 0 offers = blocked), audience size, niche value.

### Phase C Blocker Detection (`detect_phase_c_blockers`)

Detects:
- Audience too small for merch (< 2,000)
- Insufficient content for live events (< 10)
- No offers for affiliate program (0 offers)
- Missing payment processor

## Truth Labels

Phase C introduces explicit `truth_label` on every action:

| Label | Meaning |
|---|---|
| `recommended` | System recommends this action; operator should evaluate and execute |
| `queued` | Action is queued for operator review; may auto-advance in future |
| `blocked` | Cannot execute due to missing prerequisite (credential, offer, audience) |
| `live` | Action is actively executing (future state when execution layer connects) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/merch` | List active merch plans |
| POST | `/brands/{id}/merch/recompute` | Recompute merch (rate-limited) |
| GET | `/brands/{id}/live-events` | List active live event plans |
| POST | `/brands/{id}/live-events/recompute` | Recompute live events (rate-limited) |
| GET | `/brands/{id}/owned-affiliate-program` | List active affiliate program plans |
| POST | `/brands/{id}/owned-affiliate-program/recompute` | Recompute affiliate (rate-limited) |
| GET | `/brands/{id}/creator-revenue-blockers` | List all blockers (Phase A + B + C) |
| GET | `/brands/{id}/creator-revenue-events` | List all revenue events |

## Dashboards

1. **Merch / Physical Products Dashboard** — Card view with truth labels, segments, values
2. **Live Events Dashboard** — Table view with event types, ticket models, truth labels
3. **Owned Affiliate Program Dashboard** — Card view with partner types, tiers, incentives

Existing Blockers and Events dashboards display Phase C data automatically.

## Workers

| Task | Schedule | Purpose |
|---|---|---|
| `recompute_merch` | Every 6h (m=50) | Recompute merch plans for all brands |
| `recompute_live_events` | Every 6h (m=55) | Recompute live event plans for all brands |
| `recompute_affiliate_program` | Every 6h (1,7,13,19h) | Recompute affiliate plans for all brands |

## Execution Boundaries

All Phase C modules are **recommendation + execution-plan layers**:
- They persist structured action plans with execution steps and truth labels
- They do not auto-execute purchases, event platforms, or affiliate payouts
- Operator must take persisted plans and execute through external tools
- Truth labels honestly convey what is recommendation vs blocked vs queued

### Truth Boundary

| Data | Source | Status |
|---|---|---|
| Content count | Internal DB | Live |
| Avatar presence | Internal DB | Live |
| Offer count | Internal DB | Live |
| Audience size | Proxy (account_count × 2500) | Proxy |
| Payment processor | Always False (not yet wired) | Blocker |
| Merch fulfillment | Not yet integrated | Operator-executed |
| Event platform | Not yet integrated | Operator-executed |
| Affiliate tracking | Not yet integrated | Operator-executed |

## Connection to Creator Revenue Hub

The unified `creator_revenue_opportunities` view aggregates all avenues (Phase A + B + C) via the opportunity recompute pipeline. The Revenue Hub dashboard shows all avenues together, while individual dashboards provide deep per-avenue visibility.

## Credential Dependencies

- **Payment processor** — Required for all revenue collection. System detects absence.
- **Merch fulfillment provider** — Print-on-demand or warehouse (Printful, Printify, etc.)
- **Event platform** — Zoom, Riverside, Crowdcast, etc. for live events
- **Affiliate tracking** — FirstPromoter, Rewardful, or custom tracking for attribution
