# Expansion Pack 2 — Phase B: Pricing, Bundling & Retention

Phase B of Expansion Pack 2 adds three revenue-optimisation engines: **pricing intelligence**, **packaging & bundling**, and **retention & reactivation**. All outputs are persisted in Postgres and exposed under `/api/v1/brands/{brand_id}/…`, recomputed on demand or via Celery beat on the `revenue_ceiling` queue.

---

## Engine Documentation

| Engine | Doc file | Description |
|---|---|---|
| Pricing Intelligence | [24a-pricing-intelligence-engine.md](./24a-pricing-intelligence-engine.md) | Evaluates price elasticity, competitor positioning, and willingness-to-pay to recommend optimal price points for every active offer. |
| Packaging & Bundling | [24b-packaging-bundling-engine.md](./24b-packaging-bundling-engine.md) | Generates value-stack, gateway-premium, complementary, and discount bundles from the offer catalog. |
| Retention & Reactivation | [24c-retention-reactivation-engine.md](./24c-retention-reactivation-engine.md) | Scores churn risk per customer segment, recommends retention strategies, and designs reactivation campaigns for lapsed customers. |

---

## Operations

- **Migration**: revision `t1u2v3w4x5y6` (after Phase A `s0h1i2j3k4l5`). Run `alembic -c packages/db/alembic.ini upgrade head`.
- **Queue**: all tasks publish to `expansion_pack2` — no additional queue configuration required.
- **Role guard**: `POST …/recompute` endpoints require `OPERATOR` role. `GET` endpoints are readable by any brand-scoped user.

---

## Tables

Four tables created by migration `t1u2v3w4x5y6`:

| Table | Description | Details |
|---|---|---|
| `pricing_recommendations` | One row per active offer | See [24a](./24a-pricing-intelligence-engine.md) |
| `bundle_recommendations` | 1–4 rows per brand (bundle strategies) | See [24b](./24b-packaging-bundling-engine.md) |
| `retention_recommendations` | One row per customer segment | See [24c](./24c-retention-reactivation-engine.md) |
| `reactivation_campaigns` | One row per lapsed segment campaign | See [24c](./24c-retention-reactivation-engine.md) |

---

## Workers

| Task | Schedule | Queue | Details |
|---|---|---|---|
| `recompute_all_pricing_recommendations` | Every 8 h (`:12`) | `revenue_ceiling` | See [24a](./24a-pricing-intelligence-engine.md) |
| `recompute_all_bundle_recommendations` | Every 12 h (`:18`) | `revenue_ceiling` | See [24b](./24b-packaging-bundling-engine.md) |
| `recompute_all_retention_recommendations` | Every 6 h (`:22`) | `revenue_ceiling` | See [24c](./24c-retention-reactivation-engine.md) |
| `recompute_all_reactivation_campaigns` | Every 12 h (`:35`) | `revenue_ceiling` | See [24c](./24c-retention-reactivation-engine.md) |

---

## API Endpoints

All prefixed `/api/v1/brands/{brand_id}`.

| Method | Path | Role | Details |
|---|---|---|---|
| `GET` | `/pricing-recommendations` | Any | See [24a](./24a-pricing-intelligence-engine.md) |
| `POST` | `/pricing-recommendations/recompute` | OPERATOR | See [24a](./24a-pricing-intelligence-engine.md) |
| `GET` | `/bundle-recommendations` | Any | See [24b](./24b-packaging-bundling-engine.md) |
| `POST` | `/bundle-recommendations/recompute` | OPERATOR | See [24b](./24b-packaging-bundling-engine.md) |
| `GET` | `/retention-recommendations` | Any | See [24c](./24c-retention-reactivation-engine.md) |
| `POST` | `/retention-recommendations/recompute` | OPERATOR | See [24c](./24c-retention-reactivation-engine.md) |
| `GET` | `/reactivation-campaigns` | Any | See [24c](./24c-retention-reactivation-engine.md) |
| `POST` | `/reactivation-campaigns/recompute` | OPERATOR | See [24c](./24c-retention-reactivation-engine.md) |

---

## Frontend

The dashboard is mounted at `/dashboard/expansion-pack2-b` as a hub with three sub-pages:

| Route | Page | Engine |
|---|---|---|
| `/dashboard/expansion-pack2-b` | Hub (card links) | — |
| `/dashboard/expansion-pack2-b/pricing` | Pricing Intelligence | Pricing Intelligence Engine |
| `/dashboard/expansion-pack2-b/bundling` | Bundles & Packaging | Packaging & Bundling Engine |
| `/dashboard/expansion-pack2-b/retention` | Retention & Reactivation | Retention & Reactivation Engine |
