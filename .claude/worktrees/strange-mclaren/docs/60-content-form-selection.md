# Content Form Selection + Mix Allocation

## Overview

Selects the best content-form mix per account, platform, and funnel stage. Avatar is one option — not the default.

## Content Form Taxonomy

| Form | Family | Length | Avatar Mode | Cost Band |
|------|--------|--------|-------------|-----------|
| avatar_led_video | video | short | full_avatar | high |
| faceless_short_form | video | short | none | low |
| voiceover_video | video | short | voice_only | medium |
| text_led_post | text | short | none | low |
| carousel_image | image | short | none | low |
| long_form_video | video | long | none | high |
| proof_testimonial | mixed | long | none | medium |
| product_demo | video | long | none | medium |
| founder_expert | video | long | none | high |
| ugc_style | video | short | none | low |
| hybrid_format | video | short | avatar_overlay | medium |

## Selection Logic

Scoring considers: platform fit, monetization fit, funnel stage fit, avatar availability, voice availability, saturation, fatigue, trust needs, account maturity, and cost band.

Implementation: `packages/scoring/content_form_engine.py` — `recommend_content_forms(...)`.

## Mix Report Logic

Aggregates recommendations by platform (upside-weighted allocation) and emits funnel-stage templates with equal split across stage-appropriate forms.

Implementation: `compute_mix_reports(recommendations)`.

## Truth Boundaries

All recommendations use `truth_label: "recommendation"` — these are model-derived suggestions, not live execution data.

## Interactions

- **Provider Registry**: `TAVUS_API_KEY` / `ELEVENLABS_API_KEY` (and related providers) inform avatar/voice availability in services and blockers.
- **Buffer**: Content forms inform distribution plan payloads.
- **Creator Revenue**: Content form affects which revenue avenues are viable.
- **Growth Systems**: Form mix affects scaling strategy and account role decisions.

## API

| Method | Path |
|--------|------|
| GET | `/api/v1/brands/{id}/content-forms` |
| POST | `/api/v1/brands/{id}/content-forms/recompute` |
| GET | `/api/v1/brands/{id}/content-form-mix` |
| POST | `/api/v1/brands/{id}/content-form-mix/recompute` |
| GET | `/api/v1/brands/{id}/content-form-blockers` |

Recompute endpoints require operator role or higher. Celery workers refresh recommendations, mix reports, and blockers on a periodic schedule (every 4–6 hours).

## Migration

`content_form_001` (`down_revision`: `expansion_adv_001`) — tables `content_form_recommendations`, `content_form_mix_reports`, `content_form_blockers`.

## Tests

- Unit: `tests/unit/test_content_form_engine.py`
- Integration: `tests/integration/test_content_form_flow.py`
