# Phase 4: Analytics, Attribution, Intelligence & Discipline

## Module Purpose

Phase 4 closes the feedback loop: published content generates performance data, which feeds attribution, revenue rollups, winner detection, suppression logic, bottleneck classification, and memory learning.

## Attribution Model

### Event Types

| Event | Description | Tracked Value |
|-------|-------------|---------------|
| click | Link click from content | $0 (count only) |
| opt_in | Email/lead capture | $0 |
| lead | Qualified lead | Variable |
| booked_call | Sales call booked | Variable |
| purchase | Direct purchase/subscription | Transaction value |
| coupon_redemption | Promo code used | Discount value |
| affiliate_conversion | Affiliate sale attributed | Commission value |
| assisted_conversion | Multi-touch attribution | Partial value |

### Attribution Windows

Default: 720 hours (30 days). Configurable per event.

### Attribution Models

- `last_click` — Full credit to last clicked content (default)
- Future: first_click, linear, time_decay

### Tracking

- UTM parameters: built per content item + offer + account
- Tracking IDs: unique per link, persisted with events
- Click → Conversion linking via tracking_id

## Funnel Event Model

```
Impressions → Views → Clicks → [Event Type] → Revenue
```

Each stage tracked independently. Funnel dashboard shows drop-off at each stage.

## Revenue Rollups

Computed on-demand from:
- `performance_metrics.revenue` — Platform ad revenue (AdSense, etc.)
- `attribution_events.event_value` — Attribution revenue (affiliate, product, etc.)
- `content_items.total_cost` — Production costs

Derived metrics: RPM, EPC, ROI, net profit, conversion rate.

## Memory Update Logic

The memory engine stores learnings from analytics:
- **Winners**: Content that exceeds RPM/profit/engagement thresholds → stored with win_score
- **Losers**: Content that underperforms → stored for avoidance
- **Audience insights**: Patterns from engagement data
- **Platform learnings**: Best times, formats, content types per platform

Memory entries track:
- `times_reinforced` — How many times this learning was confirmed
- `times_contradicted` — How many times contradicted
- `confidence` — Net confidence based on reinforcement/contradiction

## Winner Clone Logic

Criteria for winner status:
- RPM ≥ $10 **OR**
- Profit ≥ $50 **OR**
- Engagement rate ≥ 5% **AND** CTR ≥ 3%

When a winner is detected:
1. Mark in memory
2. If other platforms available → create WinnerCloneJob (strategy: adapt)
3. Clone targets = available platforms minus source platform

Loser criteria:
- ≥1000 impressions AND RPM < $2 AND engagement < 1%

## Suppression Logic

Triggers:
- Negative profit after 500+ impressions → suppress (reason: low_profit)
- RPM < $1 after 1000+ impressions → suppress (reason: low_profit)

Every suppression creates:
- `SuppressionAction` with reason, detail, entity
- `SuppressionDecision` canonical record with input_snapshot, explanation

## Bottleneck Classifier Rules

14 categories, evaluated per account:

| Bottleneck | Trigger | Severity |
|-----------|---------|----------|
| weak_opportunity_selection | Low opportunity score + few impressions | High |
| weak_hook_retention | Avg watch < 30% with views | High |
| weak_ctr | CTR < 2% with impressions | High |
| weak_offer_fit | Offer fit score < 0.4 | Medium |
| weak_landing_page | Clicks > 10, zero conversions | High |
| weak_conversion | Conversion rate < 1% with clicks | High |
| weak_aov | AOV < $15 with conversions | Medium |
| weak_ltv | LTV estimate < $20 | Medium |
| weak_scale_capacity | > 90% posting capacity used | Medium |
| audience_fatigue | Fatigue score > 0.5 | High |
| content_similarity | Similarity score > 0.7 | Medium |
| platform_mismatch | Platform match < 0.4 | Medium |
| trust_deficit | Trust score < 0.4 with impressions | Medium |
| monetization_mismatch | Good fit + conversion but low revenue | Medium |

Each classification includes severity, explanation, and recommended actions.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /analytics/performance/ingest | Ingest performance metrics |
| POST | /analytics/events/track-click | Track click event |
| POST | /analytics/events/track-conversion | Track conversion event |
| GET | /analytics/dashboard/revenue | Revenue rollup dashboard |
| GET | /analytics/dashboard/content-performance | Per-content metrics |
| GET | /analytics/dashboard/funnel | Funnel stage breakdown |
| GET | /analytics/dashboard/leaks | Revenue leaks (bottlenecks + suppressions) |
| GET | /analytics/dashboard/bottlenecks | Per-account bottleneck classification |
| POST | /analytics/winners/detect | Detect winners and create clone jobs |
| POST | /analytics/suppressions/evaluate | Evaluate and create suppressions |

## What Is Live vs Credential-Dependent

**Live now:**
- All analytics ingestion endpoints
- All attribution tracking (click/conversion)
- All revenue rollups and dashboards
- Bottleneck classification
- Winner/loser detection
- Clone job creation
- Suppression evaluation
- Memory learning

**Needs platform credentials:**
- Auto-ingestion from YouTube/TikTok/Instagram APIs
- Real-time webhook conversion tracking from affiliate networks
