# Deal Desk Logic (Phase D)

The Deal Desk engine turns **offer**, **sponsor**, and **audience-segment** scopes (plus a **brand** fallback when no scopes exist) into a single recommended **deal strategy**, **pricing stance**, **packaging** JSON, **expected margin**, **expected close probability**, and **confidence**, with a plain-language **explanation**.

## Decision mapping (deterministic)

Signals are normalized from each deal context: `deal_value`, `lead_quality`, `urgency`, `competition_intensity`, plus brand-level `brand_authority_score` from aggregated account and performance metrics.

| Condition (simplified) | Strategy |
|------------------------|----------|
| Very high value + strong lead quality | `custom_quote` |
| High competition + urgency | `strategic_discount` |
| Low lead quality | `nurture_sequence` |
| High value + high authority | `hold_price` |
| Strong value mid-funnel | `push_upsell` |
| Good quality + moderate value | `bundle_discount` |
| High value + weak quality | `require_human_approval` |
| Default | `package_standard` |

**Pricing stance** derives from strategy + competition + authority: `premium`, `competitive`, `penetration`, or `hold`.

**Packaging** is a structured JSON (`items`, `terms`, `discount_pct`) chosen by strategy and niche label.

## Outputs

- **deal_strategy** — one of `STRATEGIES` in `deal_desk_engine.py`.
- **pricing_stance** — one of `PRICING_STANCES`.
- **packaging_recommendation** — JSON bundle suitable for CRM or quoting tools.
- **expected_margin** — adjusted from brand average margin by stance.
- **expected_close_probability** — adjusted from brand average close rate by strategy.
- **confidence** — weighted from lead quality, authority, and value score.
- **explanation** — human-readable rationale (also stored under `explanation_json` in the database).

## Persistence

- **`deal_desk_recommendations`** — one row per scope after each recompute (active recommendations replaced for that brand).
- **`deal_desk_events`** — append-style `recommendation_generated` events linking to each new recommendation row.

Recompute is **POST-only** (`/deal-desk/recompute`). Reads are **GET-only**.

## Related code

- Engine: `packages/scoring/deal_desk_engine.py`
- Service: `apps/api/services/deal_desk_service.py`
- Routes: `apps/api/routers/mxp_deal_desk.py`
