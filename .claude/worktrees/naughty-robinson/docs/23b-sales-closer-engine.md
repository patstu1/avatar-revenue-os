# Expansion Pack 2 Phase A — Sales Closer Engine

Converts qualified leads into booked calls, proposals, and closed deals by generating 3–6 prioritised `CloserAction` rows per lead, each with a specific action type, channel, opener or subject line, timing directive, and rationale. All outputs are persisted in `closer_actions`.

---

## API

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/brands/{id}/lead-opportunities/closer-actions` | Any authenticated | All closer actions for the brand, ordered by `priority` asc. |

Closer actions are rebuilt as a by-product of `POST /brands/{id}/lead-qualification/recompute` — there is no separate recompute endpoint.

---

## Inputs

| Parameter | Source | Description |
|---|---|---|
| `qualification_tier` | Parent `LeadOpportunity` | `hot` \| `warm` \| `cold` |
| `lead_source` | Parent `LeadOpportunity` | Origin channel for action routing |
| `niche` | `Brand.niche` | Personalises opener language |
| `composite_score` | Parent `LeadOpportunity` | 0–1 |
| `urgency_score` | Parent `LeadOpportunity` | 0–1 |
| `budget_proxy_score` | Parent `LeadOpportunity` | 0–1 |
| `trust_readiness_score` | Parent `LeadOpportunity` | 0–1 |
| `avg_offer_aov` | Brand average AOV | Triggers high-AOV rule when ≥ 500 |
| `brand_name` | `Brand.name` | Used in subject lines and openers |

---

## Outputs

Each `CloserAction` row carries:

| Field | Type | Description |
|---|---|---|
| `action_type` | string | Specific action (see supported types below) |
| `priority` | int | Execution order: 1 = first, ascending |
| `channel` | string | `call` \| `dm` \| `email` \| `chat` |
| `subject_or_opener` | string | Templated subject line or opening message |
| `timing` | string | `immediate` \| `24h` \| `48h` \| `72h` |
| `rationale` | string | Why this action suits the lead's score profile |
| `expected_outcome` | string | Predicted result upon execution |
| `is_completed` | bool | Completion flag (default false) |

---

## Action Routing Table

| Tier | Source | Base action sequence (priority order) |
|---|---|---|
| `hot` | `call_booked` | `book_discovery_call` → `send_proposal` → `handle_objection` → `send_case_study` |
| `hot` | `dm` or `chat` | `send_pricing` → `premium_service_pitch` → `book_discovery_call` → `send_case_study` |
| `hot` | any other | `book_discovery_call` → `send_proposal` → `send_case_study` |
| `warm` | `call_booked` | `qualify_consult` → `send_testimonials` → `handle_objection` → `follow_up_chat` |
| `warm` | any other | `send_case_study` → `send_testimonials` → `follow_up_chat` → `offer_trial` |
| `cold` | any | `send_case_study` → `follow_up_chat` → `offer_trial` |

---

## High-AOV Rule

When `avg_offer_aov >= 500` and `qualification_tier == "hot"`, a `sponsor_negotiation_prep` action (`channel: call`, `timing: immediate`) is prepended as priority 1. Existing priorities shift up by one.

---

## Supported Action Types

| Action type | Default channel | Typical timing |
|---|---|---|
| `book_discovery_call` | call | immediate |
| `send_proposal` | email | 24h |
| `handle_objection` | email | 48h |
| `send_case_study` | email | 24h–48h |
| `send_pricing` | dm | immediate |
| `premium_service_pitch` | dm | 24h |
| `qualify_consult` | call | 24h |
| `send_testimonials` | email | 24h |
| `follow_up_chat` | chat | 72h |
| `offer_trial` | email | 72h |
| `sponsor_negotiation_prep` | call | immediate |

---

## Opener Generation

`subject_or_opener` strings are templated using `brand_name` and `niche`. Each of the 11 action types has a unique opener template. Example for `book_discovery_call` with a finance brand:

> "Hi! I'd love to explore how WealthPath can help with your Finance goals — when are you free for a quick discovery call?"

---

## Table: `closer_actions`

3–6 rows per `LeadOpportunity`. Fully deleted and rebuilt on every lead qualification recompute.

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier |
| `brand_id` | UUID FK → `brands.id` | Brand scope |
| `lead_opportunity_id` | UUID FK → `lead_opportunities.id` | Parent lead (nullable) |
| `action_type` | String(80) | Action to execute |
| `priority` | Integer | Execution order, 1-based |
| `channel` | String(30) | Delivery channel |
| `subject_or_opener` | String(500) | Templated opener |
| `timing` | String(30) | Timing directive |
| `rationale` | Text | One-sentence rationale |
| `expected_outcome` | Text | Predicted result |
| `is_completed` | Boolean | Completion flag |
| `is_active` | Boolean | Soft-delete flag |

---

## Scoring Engine

**File**: `packages/scoring/expansion_pack2_phase_a_engines.py` — function `generate_closer_actions()`.

Pure function, no I/O, no SQLAlchemy. Returns a list of dicts, each with the seven action fields plus `EP2A: True` marker.
