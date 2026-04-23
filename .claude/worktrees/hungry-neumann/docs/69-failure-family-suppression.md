# 69 — Failure-Family Suppression

## Purpose

Detects recurring failing pattern groups and prevents the machine from repeating them. Not single-post failure logs — this suppresses whole bad pattern families.

## 9 Family Types

hook_type, content_form, offer_angle, cta_style, platform_mismatch, publish_timing, avatar_mode, creative_structure, monetization_path

## Suppression Logic

| Threshold | Mode | Duration |
|-----------|------|----------|
| 3+ failures | Temporary | 30 days |
| 6+ failures | Persistent | 90 days |

After expiration, the family can be retested.

## Engine

1. **Failure clustering** — groups failing content + losing patterns by shared attributes
2. **Repeat detection** — identifies families hitting the suppression threshold
3. **Rule generation** — creates temporary or persistent suppression rules with expiration dates
4. **Decay/retest** — expired rules are deactivated, families marked for retesting
5. **Alternative recommendation** — each family type has a recommended alternative

## Downstream Consumers

| Consumer | How suppression blocks |
|----------|----------------------|
| Content form selector | Suppressed content forms get confidence -0.5 |
| Content generation | Brief metadata includes `suppressed_families` with type, key, mode, reason |
| Copilot | Failure families + active suppressions in grounded context |
| Experiment engine | Suppressed families excluded from experiment design |
| Portfolio allocator | Suppressed lanes inform starvation decisions |

## API

| Endpoint | Method |
|----------|--------|
| `/{brand_id}/failure-families` | GET |
| `/{brand_id}/failure-families/recompute` | POST |
| `/{brand_id}/suppression-rules` | GET |
| `/{brand_id}/suppression-events` | GET |
| `/{brand_id}/failure-families/decay-check` | POST |

## Worker

`recompute_failure_families` — runs every 6 hours, includes decay check.
