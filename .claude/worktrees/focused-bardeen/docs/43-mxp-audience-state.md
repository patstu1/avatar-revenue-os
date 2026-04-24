# MXP: Audience State

## Purpose

The Audience State module models where the brand's audience sits across engagement lifecycle states (new, evaluating, committed, lapsed, at-risk) and recommends the best next action for each segment to maximize conversion and retention.

## Table

**`audience_state_reports`**

| Column | Type | Description |
|--------|------|-------------|
| brand_id | UUID FK | Parent brand |
| state_name | String | new, evaluating, committed, lapsed, at_risk |
| state_score | Float | 0–1 segment strength |
| transition_probabilities_json | JSONB | Probabilities of moving between states |
| best_next_action | String | Recommended action for segment |
| confidence_score | Float | 0–1 |
| explanation_json | JSONB | Segment details and reasoning |

## Engine Logic (`packages/scoring/mxp/audience_state.py`)

- Models audience as a set of states with transition probabilities.
- Estimates current distribution across states from engagement signals (follower growth, CTR trends, repeat visits).
- Computes best next action per state based on value-maximizing transitions.
- Confidence degrades when audience data is sparse.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brands/{id}/audience-states` | List audience states |
| POST | `/api/v1/brands/{id}/audience-states/recompute` | Recompute states |

## Worker

`workers/learning_worker/tasks.py` — `recompute_audience_states` runs on a 6-hour schedule via Celery beat.

## Dashboard

`/dashboard/audience-state/` — displays audience state distribution, transition probabilities, and recommended next actions.

## Execution vs Recommendation Boundary

- **Recommends only**: audience state scores inform the retention module, funnel runner, and content strategy but do not directly execute audience actions.

## Data Provenance

Audience signals are **proxy/synthetic** until live platform analytics APIs are connected. Transition probabilities are modeled from available engagement data.
