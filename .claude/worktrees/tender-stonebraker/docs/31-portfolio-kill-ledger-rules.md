# Portfolio Kill Ledger Rules (Phase D)

The kill ledger records **deliberate portfolio kills** when scoped entities fail enough threshold checks relative to peers, persists a **pre-kill performance snapshot**, a **replacement recommendation**, and **confidence**. A separate **hindsight** pass evaluates whether the kill looks correct after the fact using post-kill proxy metrics.

## Scopes

Supported `scope_type` values (see `KILL_SCOPES` in `kill_ledger_engine.py`):

- `topic_cluster` — niche clusters with weak engagement/revenue vs. thresholds.
- `offer` — offers failing conversion, revenue, or AOV floors.
- `content_family` — content items aggregated with performance metrics.
- `account` — creator accounts with weak growth, engagement, or revenue.
- `platform_mix` — synthetic UUID per platform from revenue share + engagement (deterministic `uuid5` per brand + platform key).
- `audience_segment` — segments missing conversion/LTV targets.
- `funnel` — `FunnelStageMetric` rows with weak throughput/revenue proxies.
- `paid_campaign` — paid amplification jobs with low ROAS, conversions, or CTR.
- `sponsor_strategy` — sponsor profiles missing revenue/renewal proxies.

## Kill rule (engine)

For each candidate, default thresholds are merged with optional overrides (`min_*` / `max_*`). The engine counts how many checks fail vs. how many apply. If **no** checks fail, the candidate is **not** killed. If at least one fails, a kill record is produced with:

- **kill_reason** — human-readable summary of failed checks.
- **performance_snapshot** — metrics used in evaluation (plus `thresholds_applied`, `failures`, and **`name`** when provided).
- **replacement_recommendation** — template action + urgency tier.
- **confidence** — increases with failure ratio and breadth of checks.

New rows are **append-only**; existing `scope_id` values are not duplicated for active kills.

## Hindsight rule (engine)

`review_kill_hindsight` compares pre-kill snapshot metrics to **post-kill proxy** metrics (service-layer derived from brand aggregates and time since kill). It sets:

- **hindsight_outcome** — narrative verdict.
- **was_correct_kill** — `True` / `False` / `None` when data is insufficient.
- **explanation** — stored in `explanation_json` on the review row.

Each kill entry receives **at most one** hindsight review row per recompute cycle (unreviewed entries only). The database enforces **one review per `kill_ledger_entry_id`** (`uq_kill_hindsight_reviews_kill_ledger_entry_id`); concurrent recomputes resolve safely via nested transactions.

## Persistence

- **`kill_ledger_entries`** — kills with `killed_at`, snapshot JSON, replacement JSON, `confidence_score`.
- **`kill_hindsight_reviews`** — FK to entry, outcome, correctness flag, explanation.

**POST** `/kill-ledger/recompute` runs **kill detection** then **hindsight refresh**. Optional **POST** `/kill-hindsight-reviews/recompute` runs hindsight only.

## Related code

- Engine: `packages/scoring/kill_ledger_engine.py`
- Service: `apps/api/services/kill_ledger_service.py`
- Routes: `apps/api/routers/mxp_kill_ledger.py`
