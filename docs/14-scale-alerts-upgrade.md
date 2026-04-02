# Scale Alerts + Launch Candidate Upgrade

## Architecture

Same pattern as all prior phases: **POST recompute writes, GETs are read-only.**

4 independent recompute endpoints + 2 targeted mutations (acknowledge/resolve).

## Tables

| Table | Purpose |
|-------|---------|
| `operator_alerts` | Scale-related alerts with type, urgency, confidence, metrics, status lifecycle |
| `launch_candidates` | Typed account launch candidates with full economics |
| `scale_blocker_reports` | Detected blockers with current vs threshold values |
| `notification_deliveries` | Delivery tracking per channel with retry state |
| `launch_readiness_reports` | Composite readiness score with components and gating |

## Scale Alerts Engine

15 alert types fired from scale recommendation + brand health signals:

| Alert type | Trigger |
|-----------|---------|
| `scale_now` | Scale winners harder recommendation |
| `scale_soon` | Add experimental/trend/authority account |
| `hold_and_monitor` | Monitor recommendation |
| `do_not_scale_yet` | Readiness below threshold |
| `reduce_existing_account` | Reduce/suppress weak account |
| `suppress_account` | Low trust average |
| `improve_funnel_before_scaling` | Many open leaks |
| `improve_offer_before_scaling` | Weak offer fit/diversity |
| `improve_retention_before_scaling` | High content fatigue |
| `improve_originality_before_scaling` | High originality drift |
| `expansion_opportunity_detected` | Niche/language expansion |
| `cannibalization_warning` | Risk > 0.5 |
| `saturation_warning` | Average saturation > 0.6 |
| `platform_shift_recommendation` | Platform-specific expansion |
| `niche_shift_recommendation` | Niche spinoff recommended |

Each alert includes: type, title, summary, explanation, recommended action, confidence, urgency, expected upside/cost, time-to-signal, supporting metrics, blocking factors, linked IDs.

## Launch Candidate Engine

11 candidate types from scale recommendation mapping:

`flagship_expansion`, `experimental_account`, `niche_spinoff`, `offer_specific_account`, `platform_specialist_account`, `language_expansion_account`, `geo_localized_account`, `evergreen_authority_account`, `trend_capture_account`, `high_ticket_conversion_account`, `feeder_account`

Each candidate includes: type, platforms, niche/sub-niche, language, geography, avatar/persona, monetization path, content style, posting strategy, revenue range, launch cost, time-to-signal/profit, cannibalization risk, audience separation, confidence, urgency, supporting reasons, required resources, blockers.

## Scale Blocker Diagnostics

17 blocker types detected:

`low_scale_readiness`, `weak_funnel_economics`, `weak_offer_fit`, `weak_retention`, `weak_ctr`, `weak_conversion_rate`, `poor_account_health`, `high_content_fatigue`, `high_niche_saturation`, `high_cannibalization_risk`, `poor_audience_separation`, `weak_originality`, `weak_trust`, `insufficient_monetization_depth`, `insufficient_posting_capacity`, `insufficient_repeatability`, `insufficient_confidence`

Each with: type, severity, title, explanation, recommended fix, current vs threshold values, evidence.

## Launch Readiness Scoring

Composite score (0-100) from 9 weighted components:

| Component | Weight |
|-----------|--------|
| Scale readiness (÷100) | 20% |
| Expansion confidence | 15% |
| Audience separation | 10% |
| Saturation inverse | 10% |
| Monetization depth (÷5) | 10% |
| Funnel readiness (÷0.05) | 10% |
| Trust readiness (÷100) | 10% |
| Posting capacity (÷6) | 5% |
| Cannibalization inverse | 10% |

Recommendations: `launch_now` (≥70), `prepare_but_wait` (≥50), `monitor` (<50), `do_not_launch_yet` (gated).

Gating factors: readiness < 35, trust < 50, cannibalization > 0.6, CVR near zero.

## Notification Delivery

### Channels

| Channel | Status |
|---------|--------|
| `in_app` | **Operational** — delivered immediately on alert creation |
| `email` | **Adapter ready** — SMTP credentials needed |
| `slack` | **Adapter ready** — webhook URL needed |
| `sms` | **Adapter ready** — API key needed |

Each delivery persists: channel, recipient, payload, status, attempts, last_error, delivered_at.

### Alert lifecycle

`unread` → `acknowledged` (operator clicks) → `resolved` (operator resolves with optional notes)

Both transitions create audit log entries.

## API

| Method | Path | Side effects |
|--------|------|-------------|
| GET | `/brands/{id}/alerts` | Read-only |
| POST | `/brands/{id}/alerts/recompute` | Writes alerts + in-app notifications |
| POST | `/alerts/{id}/acknowledge` | Updates alert status + audit log |
| POST | `/alerts/{id}/resolve` | Updates alert status + audit log |
| GET | `/brands/{id}/launch-candidates` | Read-only |
| POST | `/brands/{id}/launch-candidates/recompute` | Writes candidates |
| GET | `/launch-candidates/{id}` | Read-only |
| GET | `/brands/{id}/scale-blockers` | Read-only |
| POST | `/brands/{id}/scale-blockers/recompute` | Writes blocker reports |
| GET | `/brands/{id}/launch-readiness` | Read-only |
| POST | `/brands/{id}/launch-readiness/recompute` | Writes readiness report |
| GET | `/brands/{id}/notifications` | Read-only |

## Workers

| Worker | Schedule |
|--------|----------|
| `recompute_all_alerts` | Every 4 hours |
| `process_notification_deliveries` | Every 15 minutes |

## Thresholds and tuning

| Parameter | Default | Effect |
|-----------|---------|--------|
| Cannibalization risk warning | > 0.5 | Fires cannibalization_warning alert |
| Saturation warning | avg > 0.6 | Fires saturation_warning alert |
| Fatigue warning | avg > 0.55 | Fires improve_retention alert |
| Originality drift | avg > 0.45 | Fires improve_originality alert |
| Trust suppression | < 50 | Fires suppress_account alert |
| Leak count | > 5 | Fires improve_funnel alert |
| Launch readiness gate | < 35 | Blocks launch recommendation |

## Tests

- Unit: `tests/unit/test_scale_alerts_engine.py` — 17 tests
- Integration: `tests/integration/test_scale_alerts_flow.py` — 5 tests (need Postgres)
