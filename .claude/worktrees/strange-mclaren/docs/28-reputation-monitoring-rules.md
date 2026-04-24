# Reputation monitoring rules (MXP Phase C)

## Purpose

Long-term **survivability and reputation** risk for a brand is scored from structured inputs (not black-box ML): platform signals, audience text, disclosure consistency, claim language, synthetic-pattern cues, engagement quality, and sponsor concentration.

## Tables

- **`reputation_reports`**: One active brand-level report per recompute with aggregate score, primary risks, mitigations, expected impact, confidence.
- **`reputation_events`**: One row per primary risk factor over threshold for auditability.

## Risk dimensions (weights sum to 1.0)

Defined in `packages/scoring/reputation_engine.py`:

| Key | Weight | Signals |
|-----|--------|---------|
| `platform_warning_risk` | 0.18 | Strikes, warnings, policy keywords, account strike averages. |
| `spam_pattern_drift` | 0.12 | Spam/growth-hack keywords, bot follower proxy. |
| `audience_trust_decline` | 0.16 | Trust keywords, unfollow rate, low engagement. |
| `disclosure_inconsistency` | 0.10 | Sponsored posts without disclosure vs policy. |
| `claim_risk_accumulation` | 0.12 | Aggressive claim keywords and density. |
| `synthetic_pattern_risk` | 0.10 | Synthetic / AI / deepfake language. |
| `engagement_quality_degradation` | 0.12 | Generic comment patterns, low-quality engagement. |
| `sponsor_risk_drift` | 0.10 | Sponsor controversy keywords, portfolio concentration. |

## Outputs

- **`reputation_risk_score`**: Weighted sum of dimension scores (0–1).
- **`primary_risks_json`**: Top factors with `{ risk_type, score, detail }`.
- **`recommended_mitigation_json`**: Prioritized `{ risk_type, action, urgency }` entries for dimensions scoring above the engine threshold.
- **`expected_impact_if_unresolved`**: Composite downside proxy (0–1 scale).
- **`confidence_score`**: Data richness vs uncertainty.

## Service

`recompute_reputation` loads brand, accounts, content, performance maps, runs `assess_reputation`, persists one report and events, deletes prior active rows for the brand.

## API

- `GET /api/v1/brands/{brand_id}/reputation` — active reports
- `GET /api/v1/brands/{brand_id}/reputation-events` — persisted `reputation_events` (latest first)
- `POST /api/v1/brands/{brand_id}/reputation/recompute`

## Worker

`recompute_all_reputation` — beat schedule in `workers/celery_app.py` (every 12 hours on `mxp` queue).
