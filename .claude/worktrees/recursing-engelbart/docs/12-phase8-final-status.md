# Phase 8 — Final status (overview)

**Canonical Phase 8 report:** [`docs/18-phase8-operational-report.md`](./18-phase8-operational-report.md) — architecture summary, operational vs partial vs credential-blocked, setup/test/deployment, migration chain, honest gaps.

## Quick reference

| Topic | Location |
|-------|----------|
| Full honest operational status | `docs/18-phase8-operational-report.md` |
| Local setup & ports | `docs/01-setup.md` |
| Environment variables | `.env.example` |
| Growth Pack / Commander | `docs/15-growth-commander.md`, `docs/16-growth-pack-architecture.md` |

## Phase 8 hardening applied (summary)

1. **Celery worker queues:** Docker Compose worker now consumes **`scale_alerts`** and **`growth_pack`** (aligned with `workers/celery_app.py` beat schedule).  
2. **`TrackedTask`:** DB persistence failures are **logged** instead of silently ignored.  
3. **Phase 6 ExpansionDecision:** Revenue **bottleneck classifier** results are persisted on growth intel recompute (`input_snapshot`, `score_components`, `explanation`).  
4. **Documentation:** `.env.example` and setup/test guidance kept consistent with Compose ports and test DB usage.

## Read vs recompute (Phase 6)

- **POST** `/api/v1/brands/{id}/growth-intel/recompute` → write path + **audit log** `growth_intel.recomputed`.  
- **GET** growth intel endpoints → read persisted rows only (no `flush`/`delete`/`add` in getters).

---

*For route counts, test counts, and credential matrices, see `docs/18-phase8-operational-report.md`.*
