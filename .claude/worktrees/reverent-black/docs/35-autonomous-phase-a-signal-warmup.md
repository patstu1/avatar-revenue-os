# Autonomous Execution Phase A — Signal Scanning, Auto Queue, Account Warm-Up

## 1. Overview

**Purpose:** Phase A is the **execution layer** that connects “scan for opportunities” to “queue work for accounts.” It runs a continuous loop:

**signal scanning → normalized, scored events → auto queue items → per-account warm-up plans → output ceilings (safe / profitable) → maturity tracking → ramp events.**

Operators get explainable, rule-based recommendations grounded in data already in the system (`TrendSignal`, `TopicSignal`, `MacroSignalEvent`, performance metrics, and platform policy seeds). This phase does not replace human approval for publishing; it **prioritizes and structures** what to do next per brand and per creator account.

---

## 2. Continuous Signal Scanning Engine

### 2.1 Signal taxonomy (conceptual vs canonical)

The product narrative groups **twelve** opportunity lenses (e.g. rising topics, profitable niches, sub-niche whitespace, comment demand, objections/questions, competitor gaps, sponsor-friendly trends, affiliate opportunities, recurring themes, seasonal windows, high-intent patterns, fatigue signals).

The scoring engine (`packages/scoring/signal_scanning_engine.py`) uses **eleven canonical `SIGNAL_TYPES`**, which map to those lenses:

| Canonical type | Typical product mapping |
|----------------|-------------------------|
| `rising_topic` | Rising topics |
| `niche_whitespace` | Profitable niches, sub-niche whitespace |
| `comment_demand` | Comment demand |
| `objection_pattern` | Objections / questions |
| `competitor_gap` | Competitor gaps |
| `sponsor_friendly` | Sponsor-friendly trends |
| `affiliate_opportunity` | Affiliate opportunities |
| `recurring_theme` | Recurring themes |
| `seasonal_window` | Seasonal windows |
| `high_intent` | High-intent patterns |
| `fatigue_signal` | Fatigue signals |

Raw rows are **classified** into one of these types via `classify_signal_type()` using heuristics over title, description, and metric fields.

### 2.2 Ingestion sources (engine vs persistence today)

**Canonical source labels** in the engine (`SIGNAL_SOURCES`) include: `trend_api`, `comment_analysis`, `competitor_monitor`, `search_console`, `social_listening`, `audience_survey`, `affiliate_network`, `sponsor_inbound`, `internal_analytics`, `seasonal_calendar`.

**What Phase A actually reads today** (`_gather_raw_signals` in `apps/api/services/autonomous_phase_a_service.py`):

| Persisted origin | Typical `source` on normalized event | Role |
|------------------|--------------------------------------|------|
| `TrendSignal` | `trend_api` | Trend / volume / velocity proxies |
| `TopicSignal` (+ `TopicCandidate`) | `TopicSignal.signal_source` or `internal_analytics` | Topic-level signals tied to the brand |
| `MacroSignalEvent` | `social_listening` | Macro / timing style events (brand-scoped or global) |

That triad lines up with **internal performance & discovery**, **topic intelligence**, and **macro timing**. The full ten-source story is the **target architecture** as live feeds are connected; until then, missing channels are implicitly empty or approximated via metadata on stored rows.

### 2.3 Normalization and scores

For each raw candidate, `normalize_signal()` produces:

- **Freshness** — exponential decay from `age_hours` with a **per-type half-life** (`_FRESHNESS_HALF_LIFE_HOURS`).
- **Monetization relevance** — base weight per signal type, plus niche keyword overlap (Jaccard-style) and a small bonus when the brand has active offers.
- **Urgency** — type baseline, competitive pressure, and decay pressure when freshness drops.
- **Confidence** — completeness of required fields plus a `data_completeness` input.

### 2.4 Actionability gate

A normalized signal is **`is_actionable`** only if all of the following hold:

- `freshness_score >= 0.15`
- `monetization_relevance >= 0.2`
- `confidence >= 0.3`

Non-actionable signals are still stored for auditability but are **excluded** from auto-queue rebuilds (which only read actionable rows).

### 2.5 Tables

| Table | Purpose |
|-------|---------|
| `signal_scan_runs` | One row per scan execution (counts, duration, metadata). |
| `normalized_signal_events` | Scored, normalized signals linked to a run; includes `raw_payload_json` (includes `_origin` / `_origin_id` for traceability). |

---

## 3. Auto Queue Builder

**Role:** Turn **actionable** `normalized_signal_events` into **`auto_queue_items`** with a target account (when eligible), platform, niche context, monetization path, priority, and status.

### 3.1 Account matching and scoring

`build_auto_queue_items()` (`signal_scanning_engine.py`) scores account fit using:

- **Niche overlap** between signal keywords and account niche / sub-niche.
- **Account health** (low health suppresses or down-ranks).
- **Maturity bonus** — stable / scaling / `max_output` accounts get higher weight than newborn / warming.

### 3.2 Suppression, hold, and platform rules

- **Suppression** — e.g. platform policies may mark certain signal types as suppressed for a platform; very low monetization relevance on some types forces `suppressed`.
- **Low health** — accounts below a health threshold are not safe targets for normal queue types.
- **Hold** — newborn / at-risk style states and **accounts already at max output** can receive **hold** status with a `hold_reason` instead of an executable queue type.

### 3.3 Queue item types

`new_content`, `repurpose`, `reply_thread`, `offer_push`, `engagement_play`, `suppressed`.

### 3.4 Monetization paths

`affiliate`, `sponsor`, `owned_product`, `lead_gen`, `ad_revenue`, `community`, and `none` (used when no path clearly applies).

### 3.5 Table

| Table | Purpose |
|-------|---------|
| `auto_queue_items` | Active queue rows per brand; previous generation soft-deactivated on rebuild (`is_active`). |

---

## 4. Account Warm-Up + Max Output Engine

Pure logic lives in `packages/scoring/account_warmup_engine.py`; persistence and orchestration in `autonomous_phase_a_service.py`.

### 4.1 Warm-up phases (content and cadence)

| Phase | Engine id | Posting / intent |
|-------|-------------|------------------|
| Phase 1 — Warm-up | `phase_1_warmup` | Lowest cadence from platform warmup spec; **60%** value / **30%** engagement / **5%** offer / **5%** repurpose (content mix JSON). |
| Phase 2 — Ramp | `phase_2_ramp` | Higher cadence; **45%** value / **25%** engagement / **15%** offer / **15%** repurpose. |
| Phase 3 — Max output | `phase_3_max_output` | **35%** value / **20%** engagement / **25%** offer / **20%** repurpose; targets approach platform max cadence when healthy. |
| Phase 4 — Adaptive throttle | `phase_4_adaptive_throttle` | Mix shifts toward offers under guardrails; cadence adapts from recent weekly performance. |

Phase selection uses **post count**, **account age**, **violations**, and **engagement rate** thresholds (`_WARMUP_PHASE_THRESHOLDS`). Trust and engagement targets **rise** from phase 1 through phase 4.

### 4.2 Output calculation

`compute_account_output()` derives:

- **Current** — inferred from recent `PerformanceMetric` rollup (`posts_last_7d` scaled to a weekly view in the service).
- **Recommended** — blends warm-up plan targets with **health** (step up, hold, or step down).
- **Max safe** — from platform policy **`max_safe_posts_per_day × 7`** (seeded from `PLATFORM_SPECS`).
- **Max profitable** — when cost/revenue exist, uses **ROAS** tiers to cap weekly output; otherwise follows recommended output.

### 4.3 Throttle triggers

- **Health below threshold** — recommended output reduced; `throttle_reason` may cite health.
- **ROAS insufficient** — profitable cap below plan; throttle message references ROAS / profitable ceiling.

### 4.4 Tables

| Table | Purpose |
|-------|---------|
| `account_warmup_plans` | Per-account phase, cadence, targets, content mix, ramp / failure JSON. |
| `account_output_reports` | Current / recommended / max safe / max profitable, throttle reason, health, saturation, etc. |
| `output_ramp_events` | Append-only style ramp decisions (`increase`, `decrease`, `hold`, `pause`, `resume`, `split`, …) when `compute_output_ramp_event()` emits an event. |

**Note:** Maturity rows are **written** during the same `recompute_account_output` pass as output reports (see §5).

---

## 5. Account Maturity States

### 5.1 States

Eight states (`MATURITY_STATES` in `account_warmup_engine.py`):

`newborn` → `warming` → `stable` → `scaling` → `max_output` → `saturated` → `cooling` → `at_risk`

### 5.2 Transition logic

`compute_maturity_state()` classifies using **age**, **posts**, **average engagement**, **follower velocity**, **average weekly posts**, **max weekly** (from platform caps), **violations**, and **health**. The latest report stores `previous_state`, `transition_reason` / explanation text, and rolling counters.

### 5.3 Table

| Table | Purpose |
|-------|---------|
| `account_maturity_reports` | One active row per recompute generation per account (older rows deactivated when output is recomputed). |

---

## 6. Platform Warm-Up Policies

### 6.1 Platforms

Seeded policies cover **TikTok, Instagram, YouTube, X (Twitter), Reddit, LinkedIn, Facebook** — aligned with keys in `PLATFORM_SPECS` inside `packages/scoring/growth_pack/platform_os.py`.

### 6.2 Policy fields (database)

`platform_warmup_policies` stores numeric ranges and JSON blobs:

- Initial posting range (`initial_posts_per_week_min` / `max`)
- Warm-up duration range (weeks min/max)
- Steady-state posting range
- **`max_safe_posts_per_day`**
- **`ramp_behavior`** (string)
- **`ramp_conditions_json`**, **`account_health_signals_json`**, **`spam_risk_signals_json`**, **`trust_risk_signals_json`**, **`scale_ready_conditions_json`**

On first use, `seed_platform_warmup_policies()` materializes rows from **`PLATFORM_SPECS`** (source of truth for cadence, max safe output, scale-ready strings, spam/fatigue signals, etc.).

---

## 7. API Endpoints

Base path: **`/api/v1/brands`** (router tag: **Autonomous Phase A: Signal Scan, Queue, Warmup**).

All routes require an **authenticated** user whose organization owns the `brand_id`. **Recompute** routes additionally require **`OperatorUser`** (elevated operator role) and apply **`recompute_rate_limit`**.

| # | Method | Path | Auth | Description |
|---|--------|------|------|-------------|
| 1 | `GET` | `/{brand_id}/signal-scans` | Current user | List recent `signal_scan_runs` (default limit 50, max 200). |
| 2 | `POST` | `/{brand_id}/signal-scans/recompute` | Operator | Run a full signal scan; insert normalized events; return summary. |
| 3 | `GET` | `/{brand_id}/auto-queue` | Current user | List active `auto_queue_items` ordered by priority. |
| 4 | `POST` | `/{brand_id}/auto-queue/rebuild` | Operator | Rebuild queue from actionable signals and accounts. |
| 5 | `GET` | `/{brand_id}/account-warmup` | Current user | List active `account_warmup_plans`. |
| 6 | `POST` | `/{brand_id}/account-warmup/recompute` | Operator | Recompute warm-up plans for all brand accounts. |
| 7 | `GET` | `/{brand_id}/account-output` | Current user | List active `account_output_reports`. |
| 8 | `POST` | `/{brand_id}/account-output/recompute` | Operator | Recompute output, **maturity**, and **ramp events** for accounts with active warm-up plans. |
| 9 | `GET` | `/{brand_id}/platform-warmup-policies` | Current user | List (and lazily seed) global platform warm-up policies. |

**Service helpers not yet exposed as HTTP:** `list_signal_events()` returns normalized events for a brand — useful for a future **`GET /{brand_id}/normalized-signals`** (or similar) if product wants a dedicated feed.

**Dashboard client:** `apps/web/src/lib/autonomous-phase-a-api.ts` calls **`GET /{brand_id}/account-maturity`**. That route should be implemented to return active `account_maturity_reports` (mirroring other list endpoints) so the Account Maturity page and the table above stay aligned.

---

## 8. Workers / Beat Schedule

Celery beat entries in `workers/celery_app.py` (queue: **`default`** for `workers.autonomous_phase_a_worker.*`):

| Beat key | Task | Schedule |
|----------|------|----------|
| `phase-a-signal-scan-every-2h` | `run_all_signal_scans` | Every 2 hours at :25 |
| `phase-a-auto-queue-rebuild-every-2h` | `rebuild_all_auto_queues` | Every 2 hours at :30 |
| `phase-a-warmup-recompute-every-4h` | `recompute_all_warmup` | Every 4 hours at :35 |
| `phase-a-output-recompute-every-4h` | `recompute_all_output` | Every 4 hours at :40 |
| `phase-a-maturity-recompute-every-4h` | `recompute_all_maturity` | Every 4 hours at :45 |

**Operational note:** The beat schedule assumes a Celery task module (e.g. `workers.autonomous_phase_a_worker.tasks`) that iterates brands and invokes the same service functions as the API recompute endpoints. Deployments should verify that package is present and registered in `app.autodiscover_tasks`.

---

## 9. Dashboard Pages

Six focused UIs under the **Autonomous Execution** area of the web app (plus the parent hub):

| Route | Purpose |
|-------|---------|
| `/dashboard/signal-scanner` | Signal scan runs and scanning context for the brand. |
| `/dashboard/auto-queue` | Prioritized queue items, suppression / hold reasons. |
| `/dashboard/account-warmup` | Per-account warm-up phase, cadence, and content mix. |
| `/dashboard/max-output` | Output report: current vs recommended vs safe / profitable caps. |
| `/dashboard/account-maturity` | Maturity state, transitions, health-linked narrative. |
| `/dashboard/platform-warmup-policies` | Read-only (or reference) view of platform policy rows. |

**Hub:** `/dashboard/autonomous-execution` — entry point and cross-links for the Phase A loop.

---

## 10. Data Boundaries

- **Inputs:** Phase A **does not** call live TikTok/Instagram/etc. trend APIs by itself. It **reads** existing **`TrendSignal`**, **`TopicSignal`**, and **`MacroSignalEvent`** rows (plus **`PerformanceMetric`** for output and warm-up history).
- **When live platform APIs and comment/competitor pipelines exist**, the same tables (or adjacent ingest paths) can hold richer rows; the scanning step will automatically pick them up.
- **Until then**, behavior is **deterministic and rules-based** from whatever is already persisted (including seeded or synthetic upstream data).
- **Labeling:** Elsewhere in the OS, responses use **`synthetic_proxy`** vs **`live_import`** to mark trust level. Phase A normalized events carry provenance in **`raw_payload_json`** (e.g. `_origin`, `_origin_id`). Operators should treat outputs as **planning-grade** until feeds are explicitly `live_import`-backed; adding a top-level `data_source` on normalized events would align Phase A with MXP-style labeling if product standardizes on that column.

---

## 11. What’s Complete vs Blocked

| Area | Status |
|------|--------|
| Schema & models | **Complete** — `packages/db/models/autonomous_phase_a.py` and related migrations. |
| Engines | **Complete** — `signal_scanning_engine`, `account_warmup_engine` (pure functions). |
| Services & API | **Complete** for the nine routes in §7; **gap** — wire **`GET .../account-maturity`** for dashboard parity. |
| UI | **Complete** — pages listed in §9. |
| Workers | **Scheduled** in Celery beat; **verify** worker package exists in the deployment artifact. |
| Tests | **Recommended** — add API/integration tests for recompute idempotency and queue rebuild; scoring modules are suitable for **unit** tests. |

**Blocked on live credentials / feeds:**

- Real-time platform trend APIs  
- Live comment intelligence  
- Live competitor monitoring  

Until those exist, Phase A remains a **credible control plane** over **internal** signals and policy — not a substitute for real-time network data.
