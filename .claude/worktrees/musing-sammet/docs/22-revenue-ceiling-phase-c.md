# Revenue Ceiling Upgrades Pack — Phase C

Phase C adds five new revenue intelligence engines. All outputs are persisted in Postgres and exposed under `/api/v1/brands/{brand_id}/…`, recomputed on demand or via Celery beat on the `revenue_ceiling` queue.

## Detailed Documentation

| Engine | Doc |
|---|---|
| Recurring Revenue Engine | [22a — Recurring Revenue Logic](./22a-recurring-revenue-logic.md) |
| Sponsor Inventory and Pricing Engine | [22b — Sponsor Inventory Logic](./22b-sponsor-inventory-logic.md) |
| Trust Conversion Layer | [22c — Trust Conversion Logic](./22c-trust-conversion-logic.md) |
| Monetization Mix Optimizer | [22d — Monetization Mix Logic](./22d-monetization-mix-logic.md) |
| Organic-to-Paid Promotion Gate | [22e — Paid Promotion Gate](./22e-paid-promotion-gate.md) |

## Operations

- **Migration**: revision `r9g1h2i3j4k5` (after Phase B `q8f0a1b2c3d4`). Run `alembic -c packages/db/alembic.ini upgrade head`.
- **Queue**: all Phase C Celery tasks publish to the **`revenue_ceiling`** queue — the same queue as Phases A and B.
- **Role guard**: every `POST …/recompute` endpoint requires `OPERATOR` role. `GET` endpoints are readable by any brand-scoped user.
- **Frontend**: hub page at `/dashboard/revenue-ceiling-c` with 5 dedicated sub-pages (recurring, sponsors, trust, mix, promotion).