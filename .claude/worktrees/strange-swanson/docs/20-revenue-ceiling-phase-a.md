# Revenue Ceiling Phase A — Index

This document is an index for the four Phase A engines. Each engine has its own dedicated doc with full schema, API, engine, and worker details.

| Engine | Doc |
|---|---|
| Offer Ladder | [20a-offer-ladder-logic.md](./20a-offer-ladder-logic.md) |
| Owned Audience | [20b-owned-audience-strategy.md](./20b-owned-audience-strategy.md) |
| Email / SMS Sequences | [20c-email-sms-sequence-model.md](./20c-email-sms-sequence-model.md) |
| Funnel Leak Detection | [20d-funnel-leak-model.md](./20d-funnel-leak-model.md) |

All outputs are **persisted** in Postgres and exposed under `/api/v1/brands/{brand_id}/…`.

## Workers

Celery beat schedules tasks on queue **`revenue_ceiling`**: offer ladder recompute, owned-audience recompute, message sequence refresh, funnel leak recompute.

**Docker**: The `worker` service must list `revenue_ceiling` in `-Q` so these tasks are consumed (see `docker-compose.yml`).

Requires broker (Redis) and a worker process; beat only schedules — it does not execute tasks.
