# Autonomous Execution Phase B: Policies, Runner, Distribution, Monetization, Suppression

## Overview

Phase B bridges Phase A's signal-to-queue pipeline into actual execution. It adds:

1. **Execution Policy Engine** — decides autonomous vs guarded vs manual per action type
2. **Continuous Content Runner** — advances approved queue items through the full pipeline
3. **Cross-Platform Distribution Engine** — adapts content into platform-native variants
4. **Autonomous Monetization Router** — selects the optimal revenue path per content piece
5. **Autonomous Suppression Engine** — pauses weak lanes, reduces output, and blocks expansion

## Database Tables (7)

| Table | Purpose |
|---|---|
| `execution_policies` | Per-brand policy per action type (mode, risk, cost, approval, rollback, kill-switch) |
| `autonomous_runs` | Tracks each content runner execution from queue to completion |
| `autonomous_run_steps` | Step-level audit trail for each run (12 steps: queued → completed) |
| `distribution_plans` | Cross-platform derivative and timing plans |
| `monetization_routes` | Selected revenue path with funnel, follow-ups, revenue estimate |
| `suppression_executions` | Persisted suppression actions with trigger, duration, lift condition |
| `execution_failures` | Failure tracking with recovery actions |

## 1. Execution Policy Engine

Evaluates each action type against 7 factors:

- **Confidence** — how sure the system is the action is correct
- **Risk** — inherent risk level of the action type
- **Cost** — resource/budget cost class
- **Compliance sensitivity** — regulatory exposure
- **Platform sensitivity** — platform-specific risk
- **Budget impact** — remaining budget pressure
- **Account health impact** — target account health

### Policy Modes

| Mode | Behavior |
|---|---|
| `autonomous` | Execute without operator approval |
| `guarded` | Execute but notify operator; pause on risk threshold |
| `manual` | Require explicit operator approval before execution |

### Kill-Switch Classes

- `none` — no automatic stop
- `soft` — auto-pause if metrics degrade
- `hard` — immediate halt with operator notification
- `emergency` — halt all execution for the action type

## 2. Continuous Content Runner

### Pipeline Steps (12)

1. `queued` — item enters pipeline
2. `policy_check` — execution mode resolved
3. `content_brief_creation` — brief generated from queue item
4. `content_generation` — script/media created
5. `derivative_creation` — platform variants produced
6. `distribution_planning` — cross-platform plan created
7. `monetization_routing` — revenue path selected
8. `publish_queued` — content queued for publication
9. `publishing` — content pushed to platform
10. `follow_up` — post-publish monetization/engagement actions
11. `monitoring` — performance tracking active
12. `completed` — run finished

Each step is persisted in `autonomous_run_steps` with status, timestamps, input/output JSON.

## 3. Cross-Platform Distribution Engine

Takes a source concept and creates a staggered distribution plan:

- **Excludes** the source platform (no self-duplication)
- **Excludes** unhealthy or at-risk accounts
- **Excludes** accounts at max output capacity
- **Assigns** platform-appropriate derivative types
- **Staggers** timing (min 12h between platforms)
- **Guards** against duplication overload

### Derivative Types

short_clip, carousel, thread, blog_post, newsletter_segment, story, reel, static_image, quote_card, audio_snippet

## 4. Autonomous Monetization Router

### Supported Routes (18)

| Route | Class | Funnel |
|---|---|---|
| affiliate | partnership | content → link → merchant checkout |
| owned_product | direct_sale | content → landing page → cart → checkout |
| lead_gen | lead_capture | content → opt-in → nurture → offer |
| booked_calls | direct_sale | content → calendar → call → close |
| services | direct_sale | content → inquiry → proposal → contract |
| high_ticket | direct_sale | content → application → call → close |
| sponsors | partnership | content → audience proof → pitch → deal |
| newsletter_media | recurring | content → subscribe → nurture → monetize |
| recurring_subscription | recurring | content → trial → subscribe → retain |
| community | recurring | content → join → engage → upsell |
| live_events | direct_sale | content → register → attend → offer |
| ugc_creative_services | direct_sale | content → portfolio → inquiry → contract |
| licensing | passive_income | content → catalog → license → royalty |
| premium_access | recurring | content → preview → subscribe → retain |
| data_products | passive_income | content → sample → purchase → access |
| syndication | passive_income | content → distribution deal → royalty |
| merch_physical | direct_sale | content → store → cart → ship |
| affiliate_program_owned | partnership | content → program → sign-up → promote |

Each route includes required follow-up actions persisted in `follow_up_requirements_json`.

## 5. Autonomous Suppression Engine

### Suppression Types

| Type | Trigger |
|---|---|
| `pause_lane` | Account health < 0.25 with active output |
| `reduce_output` | Saturation > 0.8 with output > 5/wk |
| `suppress_queue_item` | Queue item below priority threshold |
| `suppress_content_family` | Content family avg priority < 0.2 + high fatigue |
| `suppress_account_expansion` | Account in at_risk or cooling state |
| `suppress_monetization_path` | Revenue down + engagement < 1.5% |

Each suppression persists: type, scope, trigger reason, duration, lift condition, confidence.

## API Endpoints (9)

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/execution-policies` | List active policies |
| POST | `/brands/{id}/execution-policies/recompute` | Recompute all policies |
| GET | `/brands/{id}/autonomous-runs` | List content runs |
| POST | `/brands/{id}/autonomous-runs/start` | Start runs from queue |
| GET | `/brands/{id}/distribution-plans` | List distribution plans |
| POST | `/brands/{id}/distribution-plans/recompute` | Create plans for running runs |
| GET | `/brands/{id}/monetization-routes` | List active routes |
| POST | `/brands/{id}/monetization-routes/recompute` | Select routes for running runs |
| GET | `/brands/{id}/suppression-executions` | List active suppressions |

All POST endpoints are rate-limited and require operator role.

## Workers (4)

| Worker | Schedule | Task |
|---|---|---|
| Content Runner | Every 1h | Consume ready queue items → start autonomous runs |
| Distribution Planner | Every 2h | Create distribution plans for running runs |
| Monetization Router | Every 2h | Select monetization routes for running runs |
| Suppression Checker | Every 4h | Evaluate and persist suppression actions |

## Dashboards (5)

1. **Execution Policy** — table of all action types with mode, risk, approval, kill-switch
2. **Content Runner** — status summary cards + run table with step tracking
3. **Distribution Plans** — plan list with target platforms and derivatives
4. **Monetization Router** — route table with class, funnel, revenue estimate
5. **Suppression Engine** — status summary + suppression table with types and lift conditions

## Data Boundaries

- Performance metrics default to proxy values until live platform integrations provide real data
- Content generation/publishing steps are queued but not executed until live provider credentials are configured
- Monetization routing is computed from available offer data; actual conversion tracking requires live attribution
- Suppression evaluation uses the same proxy-aware metric sources as Phase A

## What's Complete vs Blocked

| Item | Status |
|---|---|
| 7 DB models + migration | Complete |
| Execution policy engine (pure functions) | Complete |
| Monetization router (18 routes, 5 classes) | Complete |
| Suppression engine (6 types) | Complete |
| Distribution planner (7 platforms) | Complete |
| Content runner pipeline (12 steps) | Complete |
| Service layer (10 functions) | Complete |
| API endpoints (9) | Complete |
| Workers (4 recurring tasks) | Complete |
| Dashboards (5 pages) | Complete |
| Unit tests | Complete |
| Live content generation | Blocked by provider credentials |
| Live publishing | Blocked by platform API tokens |
| Live attribution/conversion | Blocked by analytics integrations |
