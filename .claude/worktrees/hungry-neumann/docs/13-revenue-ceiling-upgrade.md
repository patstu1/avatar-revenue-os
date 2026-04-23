# Revenue ceiling upgrade — maximize revenue per unit of attention

## Purpose

Turn the system from a content production engine into a full acquisition and monetization machine. Every feature is tied to measurable business outcomes with persisted evidence.

## Architecture

Same pattern as all prior phases: **POST recompute writes, GETs are read-only.**

- `POST /brands/{id}/revenue-intel/recompute` — runs all 5 engines, cleans prior rows, persists fresh outputs + MonetizationDecisions
- All GET endpoints return persisted data only
- `GET /dashboard/revenue-intel?brand_id=` — bundled dashboard read

## 5 engines

### 1. Offer Stack Optimizer

Decides which offers to layer on a single content asset (primary + secondary + downsell).

| Input | Output |
|-------|--------|
| Content performance + all active offers + audience segment | Ranked offer combinations with expected revenue lift |

**Evidence stored:** offers considered, why each included/excluded, expected AOV uplift, segment fit multiplier.

**Decision wiring:** Creates `MonetizationDecision` for each content item — fixes the Phase 8 gap where MonetizationDecision was the only decision type with no write path.

**Measurable outcome:** Expected revenue per 1,000 impressions for each stack. AOV uplift percentage.

### 2. Post-Click Funnel Scorer

Scores every content→offer→landing path for conversion efficiency.

| Input | Output |
|-------|--------|
| Attribution events grouped by path, funnel stage counts | Per-path conversion rate, drop-off stage, expected recoverable revenue |

**Evidence stored:** stage-by-stage counts, comparison to brand average, specific bottleneck identification.

**Measurable outcome:** Expected recoverable revenue from fixing each underperforming path.

### 3. Owned Audience Value Engine

Estimates value of email/subscriber/community audiences.

| Channel | Value calculation |
|---------|------------------|
| Email | opt-in count × (best payout × 5% × repeat rate) |
| Subscribers | subscriber count × (avg revenue per subscriber × 12) |
| Membership | membership count × max(avg rev × 1.5, best payout × 10%) |

**Evidence stored:** cohort sizes, repeat rates, revenue-per-subscriber estimates.

**Recommended actions:** lead magnet addition, repeat-purchase sequences, membership tier launch.

### 4. Productization Recommender

Recommends courses/memberships/products from proven content.

| Product type | Trigger | Includes |
|-------------|---------|----------|
| Course | 2+ winners, method not in catalog | Price point, addressable size, break-even units |
| Membership | 500+ subscribers, method not in catalog | Monthly price, annual revenue estimate |
| Lead magnet | $1,000+ revenue, method not in catalog | List-building for upsell path |
| Consulting | $5,000+ revenue, 3+ winners | Per-session pricing, addressable count |

**Evidence stored:** winner count, subscriber count, comment purchase signals, revenue proof.

**Each recommendation includes:** expected upside, expected cost, confidence, break-even timeline.

### 5. Monetization Density Scorer

Scores each content item on how many revenue layers it activates (0-100).

| Layer | Examples |
|-------|----------|
| `ad_revenue` | AdSense, platform ad revenue |
| `affiliate` | Affiliate link attached |
| `sponsor` | Sponsored integration |
| `lead_capture` | Opt-in form, lead magnet |
| `direct_product` | Course, product sale |
| `cross_sell` | Related offer cross-sell |
| `upsell` | Higher-tier upsell path |
| `email_opt_in` | Email capture CTA |

**Score:** 70% layer coverage + 30% RPM efficiency (vs $15 target).

**Evidence stored:** RPM, revenue, impressions, revenue efficiency ratio.

## Data model changes

### `content_items` table additions
- `offer_stack` (JSONB) — ordered list of offer IDs (primary + secondary + downsell)
- `monetization_density_score` (Float) — 0-100

### New table: `monetization_recommendations`
- `brand_id`, `content_item_id` (optional)
- `recommendation_type`: `offer_stack` / `funnel_fix` / `productization` / `owned_audience` / `density_improvement`
- `title`, `description`, `expected_revenue_uplift`, `expected_cost`, `confidence`
- `evidence` (JSONB), `is_actioned`

### Migration
`h8c3d4e5f6g7_revenue_ceiling_upgrade` — adds columns + creates table.

## Capital allocation integration

Extended from 7 to 9 allocation targets:
- `productization` (ROI ×5.0) — build high-margin products from proven content
- `owned_audience_nurture` (ROI ×3.5) — grow and monetize owned channels

Weights shift based on productization recommendation count and owned audience size.

## API

| Method | Path | Side effects |
|--------|------|-------------|
| POST | `/brands/{id}/revenue-intel/recompute` | Writes all outputs + MonetizationDecisions |
| GET | `/brands/{id}/offer-stacks` | Read-only |
| GET | `/brands/{id}/funnel-paths` | Read-only |
| GET | `/brands/{id}/owned-audience-value` | Read-only |
| GET | `/brands/{id}/productization` | Read-only |
| GET | `/brands/{id}/monetization-density` | Read-only |
| GET | `/dashboard/revenue-intel?brand_id=` | Read-only (bundled) |

## Operator Cockpit integration

Added to cockpit response: `top_offer_stacks` (3) and `worst_funnel_paths` (3).

## Non-negotiable compliance

| Rule | How it's met |
|------|-------------|
| Every revenue feature tied to measurable outcomes | Expected revenue uplift + evidence on every recommendation |
| Every post-click workflow attributable | Funnel scorer uses attribution events grouped by path |
| Every offer stack explainable | Evidence dict records: offers considered, why each included, segment fit |
| Every funnel fix stores evidence | Stage-by-stage counts, brand avg comparison, bottleneck ID |
| Every owned-audience action persisted | MonetizationRecommendation rows with evidence |
| Paid amplification gated by organic proof | Unchanged — Phase 6 winner gate still applies |
| Every productization includes upside, cost, confidence | All 4 product types include all 3 fields + break-even |
| Sponsor grounded in audience fit | Unchanged — Phase 7 sponsor packages use follower count + CPM |
| No vanity additions | Every engine output ties to dollar amounts |
| No disconnected modules | All engines feed MonetizationRecommendation, capital allocation reads it |

## Tests

- Unit: `tests/unit/test_revenue_engines.py` — 14 tests covering all 5 engines
- Integration: `tests/integration/test_revenue_flow.py` — recompute-then-read, side-effect-free GETs, dashboard bundle
