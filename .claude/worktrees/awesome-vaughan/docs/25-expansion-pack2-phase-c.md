# Expansion Pack 2 — Phase C: Advanced Revenue Optimization

Phase C adds four engines that close the loop between growth acquisition and financial health.

## Engine Documentation

| # | Engine | Doc |
|---|--------|-----|
| 1 | Referral & Ambassador | [25a-referral-ambassador-engine.md](25a-referral-ambassador-engine.md) |
| 2 | Competitive Gap Hunter | [25b-competitive-gap-hunter.md](25b-competitive-gap-hunter.md) |
| 3 | Outbound Sponsor Sales | [25c-outbound-sponsor-sales-engine.md](25c-outbound-sponsor-sales-engine.md) |
| 4 | Profit Guardrail & Cash Governor | [25d-profit-guardrail-cash-governor.md](25d-profit-guardrail-cash-governor.md) |

## Key Files

| Layer | Path |
|-------|------|
| Models | `packages/db/models/expansion_pack2_phase_c.py` |
| Migration | `packages/db/alembic/versions/u2v3w4x5y6z7_expansion_pack2_phase_c_tables.py` |
| Scoring Engines | `packages/scoring/expansion_pack2_phase_c_engines.py` |
| Service Layer | `apps/api/services/expansion_pack2_phase_c_service.py` |
| Router | `apps/api/routers/expansion_pack2_phase_c.py` |
| Schemas | `apps/api/schemas/expansion_pack2_phase_c.py` |
| Workers | `workers/revenue_ceiling_worker/tasks.py` (5 tasks) |
| Beat Schedule | `workers/celery_app.py` (5 entries: `ep2c-*`) |
| TS API Client | `apps/web/src/lib/expansion-pack2-phase-c-api.ts` |
| Frontend Hub | `apps/web/src/app/dashboard/expansion-pack2-c/page.tsx` |
| Sub-pages | `referral/`, `competitive-gap/`, `sponsor-sales/`, `profit-guardrails/` |
| Sidebar | `apps/web/src/components/Sidebar.tsx` |
| Unit Tests | `tests/unit/test_expansion_pack2_phase_c_engines.py` |
| API Tests | `tests/integration/test_expansion_pack2_phase_c_api.py` |
| Worker Tests | `tests/integration/test_expansion_pack2_phase_c_workers.py` |

## Database Tables

| Table | Unique Constraint |
|-------|-------------------|
| `referral_program_recommendations` | `(brand_id, customer_segment)` |
| `competitive_gap_reports` | `(brand_id, competitor_name, offer_id)` |
| `sponsor_targets` | `(brand_id, target_company_name)` |
| `sponsor_outreach_sequences` | `(sponsor_target_id, sequence_name)` |
| `profit_guardrail_reports` | `(brand_id, metric_name)` |
