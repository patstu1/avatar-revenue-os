# MXP: Creative Memory

## Purpose

The Creative Memory module stores and retrieves high-performing creative atoms (hooks, CTAs, formats, visual styles, topics) to enable the content generation pipeline to reuse proven patterns and avoid originality drift.

## Table

**`creative_memory_atoms`**

| Column | Type | Description |
|--------|------|-------------|
| brand_id | UUID FK | Parent brand |
| atom_type | String | hook, cta, format, visual_style, topic |
| platform | String | Platform where atom performed |
| niche | String | Niche context |
| content_json | JSONB | Atom content (text, style, metadata) |
| performance_summary_json | JSONB | avg_ctr, uses, retention metrics |
| originality_caution_score | Float | 0–1 overuse risk |
| confidence_score | Float | 0–1 |

## Engine Logic (`packages/scoring/mxp/creative_memory.py`)

- Scans recent published content performance to extract top-performing creative atoms.
- Groups atoms by type and platform.
- Computes `originality_caution_score` based on reuse frequency to flag overuse risk.
- Stores new atoms and updates performance summaries for existing ones.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brands/{id}/creative-memory-atoms` | List creative atoms |
| POST | `/api/v1/brands/{id}/creative-memory-atoms/recompute` | Refresh memory |

## Worker

`workers/learning_worker/tasks.py` — `recompute_creative_memory` runs on a 12-hour schedule via Celery beat.

## Dashboard

`/dashboard/creative-memory/` — displays creative atoms with performance metrics, originality caution scores, and platform/niche grouping.

## Execution vs Recommendation Boundary

- **Queues operator action**: creative memory atoms are surfaced for the content generation pipeline to consume. The generation worker pulls from creative memory when building content briefs.
- No autonomous execution — atoms inform generation but don't trigger it.

## Data Provenance

Atom performance data is **proxy/synthetic** when engagement metrics are seeded rather than imported from live platform APIs.
