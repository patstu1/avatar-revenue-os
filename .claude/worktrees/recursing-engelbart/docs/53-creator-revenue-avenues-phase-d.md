# Creator Revenue Avenues — Phase D: Unified Hub & Execution Truth

## Overview

Phase D is the final phase of the Creator Revenue Avenues Pack. It builds the unifying layer that aggregates all 9 revenue avenues into a single, ranked, truth-labeled hub.

## Avenues Unified

| Avenue | Phase | Source Table |
|---|---|---|
| UGC / Creative Services | A | `ugc_service_actions` |
| Services / Consulting | A | `service_consulting_actions` |
| Premium Access / Concierge | A | `premium_access_actions` |
| Licensing | B | `licensing_actions` |
| Syndication | B | `syndication_actions` |
| Data Products | B | `data_product_actions` |
| Merch / Physical Products | C | `merch_actions` |
| Live Events | C | `live_event_actions` |
| Owned Affiliate Program | C | `owned_affiliate_program_actions` |

## Tables

| Table | Purpose |
|---|---|
| `avenue_execution_truth` | Persisted per-avenue truth state snapshot per brand |
| `creator_revenue_opportunities` | Unified opportunity view (Phase A) |
| `creator_revenue_blockers` | Unified blocker surface (all phases) |
| `creator_revenue_events` | Unified revenue event ledger (all phases) |

## Hub Engine Logic

### Cross-Avenue Ranking

The hub computes a `hub_score` for each avenue:

```
hub_score = (total_expected_value × avg_confidence × urgency × readiness) / 1000
```

Where urgency and readiness are determined by truth state:

| State | Urgency | Readiness |
|---|---|---|
| blocked | 0.3 | 0.1 |
| recommended | 0.5 | 0.4 |
| queued | 0.7 | 0.6 |
| executing | 0.9 | 0.9 |
| live | 1.0 | 1.0 |

Avenues are sorted descending by `hub_score`.

### Truth State Classification

```python
classify_avenue_truth_state(action_count, blocked_count, blocker_count, has_revenue)
```

| Priority | Condition | State |
|---|---|---|
| 1 | has_revenue | `live` |
| 2 | action_count == 0 | `recommended` |
| 3 | all actions blocked | `blocked` |
| 4 | some blockers, some active | `queued` |
| 5 | actions exist, no blockers | `executing` |
| default | | `recommended` |

### Blocker Aggregation

All blockers from Phase A, B, and C detection are combined into the `creator_revenue_blockers` table. The hub queries blockers per avenue (including `avenue_type="all"` for cross-cutting blockers) and surfaces the top 5 per avenue.

### Revenue Event Rollup

Events are aggregated from `creator_revenue_events` into:
- Per-avenue totals (revenue, cost, profit, count)
- Grand totals across all avenues

### Operator Next Actions

The `determine_operator_next_action` function generates specific, actionable guidance based on truth state and active blockers:

- **live** → "Monitor performance and optimize."
- **blocked** → Specific resolution action based on blocker type
- **queued** → "Review queued plans and resolve remaining blockers."
- **executing** → "Execute the planned actions."
- **recommended** → "Recompute to generate plans."

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/creator-revenue-hub` | Full hub with ranked entries + rollups |
| POST | `/brands/{id}/creator-revenue-hub/recompute` | Persist truth snapshots (rate-limited) |
| GET | `/brands/{id}/creator-revenue-truth` | List persisted truth records |
| GET | `/brands/{id}/creator-revenue-blockers` | Unified blocker surface |
| GET | `/brands/{id}/creator-revenue-events` | Unified event ledger |

## Dashboards

1. **Creator Revenue Hub** — Master view with summary metrics, ranked table of all 9 avenues, event rollup
2. **Execution Truth** — Per-avenue truth cards with state, metrics, operator guidance, missing integrations
3. **Creator Revenue Blockers** — Unified blocker table with severity, description, resolution actions
4. **Creator Revenue Events** — Event ledger with per-avenue revenue, cost, profit, and totals

## Workers

| Task | Schedule | Purpose |
|---|---|---|
| `recompute_creator_revenue_hub` | Every 3h (m=10) | Persist truth snapshots for all brands |
| `recompute_creator_revenue_blockers` | Every 2h (m=5) | Refresh all-phase blockers |

Hub recompute depends on avenue-level recomputes running first (via their own schedules).

## Execution Boundaries Per Avenue

| Avenue | Execution Status | Missing Integrations |
|---|---|---|
| UGC / Creative Services | Plans are operator-executed | None |
| Services / Consulting | Plans are operator-executed | None |
| Premium Access | Plans are operator-executed | community_platform |
| Licensing | Plans are operator-executed | payment_processor |
| Syndication | Plans are operator-executed | payment_processor |
| Data Products | Plans are operator-executed | payment_processor |
| Merch / Physical Products | Plans are operator-executed | payment_processor, fulfillment_provider |
| Live Events | Plans are operator-executed | payment_processor, event_platform |
| Owned Affiliate Program | Plans are operator-executed | affiliate_tracking_tool |

All avenues generate structured execution plans with step-by-step instructions. The system does not auto-execute deals, transactions, or integrations. The operator must take the plans and execute through their existing tools.

## How Creator Revenue Connects to the Machine

1. **Content Pipeline** feeds content count → affects confidence across all avenues
2. **Avatar System** feeds avatar presence → affects UGC, merch confidence
3. **Offer Catalog** feeds offer count → affects consulting, premium access, affiliate program confidence
4. **Creator Accounts** feed account count → determines audience proxy
5. **Analytics** will eventually feed real revenue events into the event ledger
6. **All blocker detection** surfaces where the machine's inputs are incomplete

## Pack Completion Status

The Creator Revenue Avenues Pack (Phases A–D) is now complete:

| Phase | Focus | Status |
|---|---|---|
| A | UGC, Consulting, Premium Access, Opportunities, Blockers, Events | Complete |
| B | Licensing, Syndication, Data Products | Complete |
| C | Merch, Live Events, Owned Affiliate Program | Complete |
| D | Unified Hub, Execution Truth, Blocker/Event Unification | Complete |

Total tables: 13 (9 action tables + opportunities + blockers + events + execution truth)
Total API endpoints: 25+ (per-avenue CRUD + hub + truth + blockers + events)
Total dashboards: 16 (9 avenue + hub + truth + blockers + events + opportunities + 2 legacy)
