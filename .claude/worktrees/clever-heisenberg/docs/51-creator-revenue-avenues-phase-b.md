# Creator Revenue Avenues — Phase B: Licensing, Syndication, Data Products

## Overview

Phase B extends the Creator Revenue Avenues Pack with three new monetization layers:

1. **Licensing** — License creative assets, content formats, workflows, IP packages, and white-label rights
2. **Syndication** — Syndicate content across channels, partners, newsletters, and republishing networks
3. **Data Products** — Sell niche databases, intelligence feeds, swipe files, research packs, signal datasets, and premium reports

These extend the Phase A foundation (UGC services, consulting, premium access) to cover the full spectrum of creator-driven revenue.

## Tables

| Table | Purpose |
|---|---|
| `licensing_actions` | Persisted licensing execution plans per brand |
| `syndication_actions` | Persisted syndication execution plans per brand |
| `data_product_actions` | Persisted data product execution plans per brand |
| `creator_revenue_blockers` | Shared blocker table (extended with Phase B detection) |
| `creator_revenue_events` | Shared revenue event table (licensing/syndication/data events) |

## Engine Logic

### Licensing (`score_licensing_opportunities`)

Evaluates 6 licensing types:

| Type | Tier | Target | Usage |
|---|---|---|---|
| `creative_asset_licensing` | standard | agencies_and_brands | limited_use |
| `content_format_licensing` | standard | content_teams | limited_use |
| `workflow_system_licensing` | premium | operations_teams | full_use |
| `ip_package_licensing` | premium | enterprise_buyers | full_use |
| `white_label_rights` | premium | resellers_and_agencies | full_use |
| `limited_use_licensing` | entry | small_businesses | limited_use |

Scoring factors: content depth, avatar presence, niche value, offer count.

### Syndication (`score_syndication_opportunities`)

Evaluates 5 syndication formats:

| Format | Partner Type | Revenue Model |
|---|---|---|
| `cross_channel_syndication` | platform_operators | recurring |
| `content_package_syndication` | media_companies | one_time |
| `media_newsletter_syndication` | newsletter_operators | recurring |
| `republishing_rights` | publishers_and_blogs | one_time |
| `partner_distribution_bundles` | distribution_partners | recurring |

Scoring factors: content count, account count, niche value.

### Data Products (`score_data_product_opportunities`)

Evaluates 6 product types:

| Type | Target | Revenue Model |
|---|---|---|
| `niche_database` | researchers_and_analysts | recurring |
| `premium_intelligence_feed` | decision_makers | recurring |
| `swipe_file` | marketers_and_creators | one_time |
| `research_pack` | strategists | one_time |
| `signal_trend_dataset` | investors_and_operators | recurring |
| `premium_reporting_product` | executives_and_teams | recurring |

Scoring factors: content depth, niche value, audience size. High-data products require 30+ content items for reasonable confidence.

### Blocker Detection (`detect_phase_b_blockers`)

Detects:
- Insufficient licensable content (< 15 items)
- Insufficient syndication content (< 10 items)
- Insufficient data depth (< 20 items)
- Missing payment processor

These combine with Phase A blockers during recomputation.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/licensing` | List active licensing plans |
| POST | `/brands/{id}/licensing/recompute` | Recompute licensing (rate-limited) |
| GET | `/brands/{id}/syndication` | List active syndication plans |
| POST | `/brands/{id}/syndication/recompute` | Recompute syndication (rate-limited) |
| GET | `/brands/{id}/data-products` | List active data product plans |
| POST | `/brands/{id}/data-products/recompute` | Recompute data products (rate-limited) |
| GET | `/brands/{id}/creator-revenue-blockers` | List all blockers (Phase A + B) |
| GET | `/brands/{id}/creator-revenue-events` | List all revenue events |

## Dashboards

1. **Licensing Dashboard** — Table view of all licensing plans with deal values, tiers, scopes
2. **Syndication Dashboard** — Card view of syndication opportunities with revenue models
3. **Data Products Dashboard** — Card view of data product plans with pricing and segments

The existing Blockers and Events dashboards from Phase A display Phase B data automatically.

## Workers

| Task | Schedule | Purpose |
|---|---|---|
| `recompute_licensing` | Every 6h (m=35) | Recompute licensing plans for all brands |
| `recompute_syndication` | Every 6h (m=40) | Recompute syndication plans for all brands |
| `recompute_data_products` | Every 6h (m=45) | Recompute data product plans for all brands |

The existing Phase A blocker recompute task now also runs Phase B blocker detection.

## Execution Boundaries

All Phase B modules are **recommendation + execution-plan layers**:
- They persist structured action plans with execution steps
- They do not auto-execute deals or send outreach
- Operator must take persisted plans and execute through external tools
- Blockers surface missing prerequisites as structured operator actions

### Truth Boundary

| Data | Source | Status |
|---|---|---|
| Content count | Internal DB | Live |
| Avatar presence | Internal DB | Live |
| Audience size | Proxy (account_count × 2500) | Proxy |
| Payment processor | Always False (not yet wired) | Blocker |
| Licensing deal value | Rules-based estimate | Deterministic |
| Syndication value | Rules-based estimate | Deterministic |
| Data product value | Rules-based estimate | Deterministic |

## Credential Dependencies

- **Payment processor** — Required for all revenue collection. System detects absence and creates blockers.
- **CRM/outreach tools** — Not yet wired. Licensing/syndication outreach is operator-executed.
- **Analytics integration** — Real revenue tracking requires Live Execution Closure analytics ingestion.
