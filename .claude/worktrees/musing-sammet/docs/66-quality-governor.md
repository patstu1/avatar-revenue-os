# 66 — Quality Governor

## Purpose

Pre-publish content quality control gate that scores content across 10 dimensions and prevents quality collapse from volume scaling. Not a vague quality label — it actively blocks bad content and prescribes specific improvements.

## 10 Quality Dimensions

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| hook_strength | 15% | Power words, questions, length, hook effectiveness |
| clarity | 10% | Body text word count, structure |
| novelty | 10% | Jaccard similarity to recent titles |
| conversion_fit | 15% | CTA presence + offer attachment |
| trust_risk | 10% | Trust-violating language + account health |
| fatigue_risk | 10% | Account fatigue + recent post volume |
| duplication_risk | 10% | SHA256 body hash match against existing content |
| platform_fit | 8% | Content type appropriateness for target platform |
| offer_fit | 7% | Offer conversion rate quality |
| brand_fit | 5% | Niche and tone of voice alignment |

## Verdicts

- **pass** (score ≥ 0.60) — publish allowed
- **warn** (score 0.40-0.59) — publish allowed with warnings
- **fail** (score < 0.40 OR trust_risk/duplication_risk < 0.20) — publish blocked

## Auto-Block

Content is automatically blocked if:
- `trust_risk` score < 0.20 (trust-violating language detected)
- `duplication_risk` score < 0.20 (exact duplicate detected)
- Total score < 0.40

Blocked content has `status` set to `quality_blocked`.

## Downstream Impact

| Consumer | How quality affects behavior |
|----------|---------------------------|
| Publishing worker | Checks quality gate before publish — blocks if `publish_allowed == false` |
| Copilot | Quality failures + blocks surfaced in grounded context |
| Experiment routing | Failed content excluded from experiment variants |
| Content brief revision | Improvement actions prescribe specific fixes per dimension |
| Kill/scale logic | Consistently failing accounts accumulate quality blocks |

## API

| Endpoint | Method |
|----------|--------|
| `/{brand_id}/quality-governor` | GET |
| `/{brand_id}/quality-governor/recompute` | POST |
| `/{brand_id}/quality-governor/{content_item_id}/score` | POST |
| `/{brand_id}/quality-governor/blocks` | GET |

## Worker

`recompute_quality_governor` — runs every 2 hours, scores all pending content.
