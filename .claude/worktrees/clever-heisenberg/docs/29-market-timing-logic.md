# Market timing logic (MXP Phase C)

## Purpose

Scores **when** to lean into launches, monetization, or paid tests using niche + calendar month + **macro signal** inputs. Logic is explicit and inspectable in `packages/scoring/market_timing_engine.py`.

## Tables

- **`market_timing_reports`**: One row per applicable **category** after each recompute (timing score, window label, recommendation, uplift estimate, confidence, explanation JSON).
- **`macro_signal_events`**: Append-only style events keyed by `signal_type` and `signal_metadata_json.value` (e.g. `cpm_index`, `election_cycle`, `ad_spend_trend`). `brand_id` is nullable but typically set for org-scoped ingestion.

## Categories (8)

1. `recession_resistant` — evergreen niches + `recession_indicator` macro.
2. `sponsor_friendly_cycle` — sponsor-attractive niches + Q4/Q1 + `ad_spend_trend`.
3. `seasonal_buying` — niche peak months vs current month.
4. `holiday_monetization` — month-based retail / gifting windows.
5. `election_volatility` — `election_cycle` signal present (negative uplift on paid).
6. `platform_algorithm_shift` — `platform_update` signal.
7. `cpm_friendly` — cheap months and/or low `cpm_index`.
8. `low_competition_launch` — quiet months and/or low `competitor_launch_count`.

## Macro signals

The engine accepts a list of `{ signal_type, value, source }`. Known types include:

`recession_indicator`, `cpi_trend`, `ad_spend_trend`, `election_cycle`, `platform_update`, `cpm_index`, `competitor_launch_count`.

Changing **`cpm_index`** or **`election_cycle`** changes which windows surface and the numeric `timing_score` / `expected_uplift` for the same brand context—verified in unit tests.

## Service behavior

`recompute_market_timing`:

1. Deletes active `market_timing_reports` for the brand.
2. Loads existing `macro_signal_events` for the brand; if none, inserts baseline synthetic rows (development-friendly) so categories still evaluate.
3. Calls `evaluate_market_timing(brand_context, macro_signals)` and persists each result row with `explanation_json: { "explanation": "<text>" }`.

## API

- `GET /api/v1/brands/{brand_id}/market-timing` — active timing report rows
- `GET /api/v1/brands/{brand_id}/macro-signal-events` — persisted macro inputs for the brand
- `POST /api/v1/brands/{brand_id}/market-timing/recompute`

## Worker

`recompute_all_market_timing` — beat schedule in `workers/celery_app.py` (every 12 hours, `mxp` queue).
