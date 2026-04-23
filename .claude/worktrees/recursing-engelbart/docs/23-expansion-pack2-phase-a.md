# Expansion Pack 2 — Phase A: Sales Closer, Lead Qualification & Offer Creation

Phase A of Expansion Pack 2 adds three revenue-acceleration engines: **sales closing action queues**, **multi-dimensional lead qualification**, and **owned-product opportunity detection**. All outputs are persisted in Postgres and exposed under `/api/v1/brands/{brand_id}/…`, recomputed on demand or via Celery beat on the `revenue_ceiling` queue.

---

## Engine Documentation

| Engine | Doc file | Description |
|---|---|---|
| Lead Qualification | [23a-lead-qualification-engine.md](./23a-lead-qualification-engine.md) | Scores inbound leads across urgency, budget, sophistication, offer fit, and trust readiness — tiers each as hot/warm/cold with a recommended next action. |
| Sales Closer | [23b-sales-closer-engine.md](./23b-sales-closer-engine.md) | Generates 3–6 prioritised closer actions per lead — discovery calls, proposals, objection handling, case studies, and more. |
| Owned Offer Creation | [23c-owned-offer-creation-engine.md](./23c-owned-offer-creation-engine.md) | Detects owned-product opportunities from comment themes, funnel objections, content engagement, and audience segments — with offer type, price range, demand score, and estimated first-month revenue. |

---

## Operations

- **Migration**: revision `s0h1i2j3k4l5` (after Phase C `r9g1h2i3j4k5`). Run `alembic -c packages/db/alembic.ini upgrade head`.
- **Queue**: all tasks publish to `revenue_ceiling` — no additional queue configuration required.
- **Role guard**: `POST …/recompute` endpoints require `OPERATOR` role. `GET` endpoints are readable by any brand-scoped user.
- **Closer action regeneration**: closer actions are rebuilt as a by-product of lead qualification recompute — no separate endpoint.
- **Dependency ordering**: Owned Offer Creation reads `CommentCluster` and `FunnelLeakFix` rows from earlier engines. Run at least one Revenue Ceiling Phase A recompute first.

---

## Tables

Four tables created by migration `s0h1i2j3k4l5`:

| Table | Description | Details |
|---|---|---|
| `lead_opportunities` | One row per scored lead signal | See [23a](./23a-lead-qualification-engine.md) |
| `closer_actions` | 3–6 rows per lead opportunity | See [23b](./23b-sales-closer-engine.md) |
| `lead_qualification_reports` | One aggregate row per brand | See [23a](./23a-lead-qualification-engine.md) |
| `owned_offer_recommendations` | One row per triggered detection rule | See [23c](./23c-owned-offer-creation-engine.md) |

---

## Workers

| Task | Schedule | Queue | Details |
|---|---|---|---|
| `recompute_all_lead_qualification` | Every 6 h | `revenue_ceiling` | See [23a](./23a-lead-qualification-engine.md) |
| `recompute_all_owned_offer_recommendations` | Every 8 h | `revenue_ceiling` | See [23c](./23c-owned-offer-creation-engine.md) |

---

## API Endpoints

All prefixed `/api/v1/brands/{brand_id}`.

| Method | Path | Role | Details |
|---|---|---|---|
| `GET` | `/lead-opportunities` | Any | See [23a](./23a-lead-qualification-engine.md) |
| `GET` | `/lead-opportunities/closer-actions` | Any | See [23b](./23b-sales-closer-engine.md) |
| `GET` | `/lead-qualification` | Any | See [23a](./23a-lead-qualification-engine.md) |
| `POST` | `/lead-qualification/recompute` | OPERATOR | See [23a](./23a-lead-qualification-engine.md) |
| `GET` | `/owned-offer-recommendations` | Any | See [23c](./23c-owned-offer-creation-engine.md) |
| `POST` | `/owned-offer-recommendations/recompute` | OPERATOR | See [23c](./23c-owned-offer-creation-engine.md) |

---

## Frontend

The dashboard is mounted at `/dashboard/expansion-pack2-a` as a hub with three sub-pages:

| Route | Page | Engine |
|---|---|---|
| `/dashboard/expansion-pack2-a` | Hub (card links) | — |
| `/dashboard/expansion-pack2-a/leads` | Lead Qualification | Lead Qualification Engine |
| `/dashboard/expansion-pack2-a/closer` | Sales Closer Actions | Sales Closer Engine |
| `/dashboard/expansion-pack2-a/offers` | Owned Offer Opportunities | Owned Offer Creation Engine |