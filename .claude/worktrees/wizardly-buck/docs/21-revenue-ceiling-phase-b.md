# Revenue Ceiling Phase B — Index

This document is an index for the four Phase B engines. Each engine has its own dedicated doc with full schema, API, engine, and worker details.

| Engine | Doc |
|---|---|
| High-Ticket Conversion | [21a-high-ticket-conversion-logic.md](./21a-high-ticket-conversion-logic.md) |
| Productization | [21b-productization-logic.md](./21b-productization-logic.md) |
| Revenue Density | [21c-revenue-density-formulas.md](./21c-revenue-density-formulas.md) |
| Upsell / Cross-Sell | [21d-upsell-logic.md](./21d-upsell-logic.md) |

All outputs are **persisted** in Postgres and exposed under `/api/v1/brands/{brand_id}/…`.

## Operations

- **Migration**: revision `q8f0a1b2c3d4` (after Phase A `p7d8e9f0a1b2`). Run `alembic -c packages/db/alembic.ini upgrade head`.
- **Revenue density rows** require at least one **`content_items`** row for the brand; otherwise recompute returns `revenue_density_rows: 0`.
- **Upsell rows** require **at least two** active offers.

## Workers

Beat schedules (same queue as Phase A: `revenue_ceiling`): high-ticket, product opportunities, revenue density, upsell refresh — see `workers/celery_app.py`.

**Docker**: The `worker` service must list `revenue_ceiling` in `-Q` so these tasks are consumed (see `docker-compose.yml`).
