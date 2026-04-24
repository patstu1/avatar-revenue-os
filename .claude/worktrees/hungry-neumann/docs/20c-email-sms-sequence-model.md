# Email / SMS Sequence Model

Seven **sequence types** are generated per brand:

1. **Welcome** — day-0 value, proof/story, soft CTA
2. **Nurture** — education, common mistakes, case study
3. **Objection handling** — time, trust, price objections
4. **Conversion** — offer reveal, ethical urgency, FAQ
5. **Upsell** — congrats, complement product, coaching/community
6. **Reactivation** — win-back offer, preference center
7. **Sponsor-safe** — partner message with disclosure, editorial-first, opt-out

## Channel Support

Each sequence is assigned one of three channels:

- **email** — all steps are email
- **sms** — all steps are SMS
- **hybrid** — steps alternate between email and SMS

## Persistence

### Table: `message_sequences`

| Column | Type | Notes |
|---|---|---|
| `brand_id` | UUID FK → brands | indexed |
| `sequence_type` | String(80) | indexed; welcome / nurture / objection_handling / conversion / upsell / reactivation / sponsor_safe |
| `channel` | String(30) | email / sms / hybrid |
| `title` | String(500) | display title |
| `sponsor_safe` | Boolean | true for sponsor-safe sequences |
| `is_active` | Boolean | default true |

### Table: `message_sequence_steps`

| Column | Type | Notes |
|---|---|---|
| `sequence_id` | UUID FK → message_sequences | indexed |
| `step_order` | Integer | 1-indexed |
| `channel` | String(20) | email / sms (resolved from parent hybrid) |
| `subject_or_title` | String(500) | nullable |
| `body_template` | Text | includes brand voice suffix |
| `delay_hours_after_previous` | Integer | 0 for first step |

## API

- `GET /api/v1/brands/{brand_id}/message-sequences` — list active sequences with nested steps
- `POST /api/v1/brands/{brand_id}/message-sequences/generate` — delete + regenerate all sequences and steps

## Engine

`packages/scoring/revenue_ceiling_phase_a_engines.py`:

- `build_sequence()` — returns `(sequence_meta, steps)` for one sequence type + channel
- `generate_all_message_sequences()` — produces all 7 sequences with deterministic channel assignment

## Worker

Celery beat task `refresh_all_message_sequences` runs every 12 hours on the `revenue_ceiling` queue.
