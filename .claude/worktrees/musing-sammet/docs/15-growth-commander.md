# Revenue Growth Commander + Portfolio Launch Architecture

## Purpose

Autonomous growth commander that produces **exact commands** — not advisory recommendations. Every command includes a comparison (new account profit vs more output on existing), cannibalization analysis, success/failure thresholds, and a concrete first-week plan.

## Architecture

Composes on top of existing scale alerts infrastructure. Reads from `scale_recommendations`, `launch_candidates`, `scale_blocker_reports`, `launch_readiness_reports`. Produces `growth_commands`.

```
Scale Engine → Scale Recommendations → Scale Alerts Engine → {Alerts, Candidates, Blockers, Readiness}
                                                                         ↓
                                                              Growth Commander Engine
                                                                         ↓
                                                              Growth Commands (persisted, versioned)
                                                                         ↓
                                                              growth_command_runs (audit + portfolio_directive)
                                                                         ↓
                                                              operator_alerts (growth_commander_priority, top urgency)
```

POST recompute writes. All GETs are read-only. Failed recomputes set `growth_command_runs.status=failed`, persist `error_message`, and emit `growth_commander.recompute_failed` audit log entries. Successful runs write `portfolio_directive` (top-level portfolio control: target account count vs current, hold vs expand stance, explanation, evidence, downstream action). Prior command rows are **superseded** (`is_active=false`, `superseded_at`, `superseded_by_run_id`), not deleted, so commands remain auditable.

## Command types

| Type | When issued |
|------|-----------|
| `fix_funnel_first` | > 5 leaks AND high-severity blockers. Highest priority — blocks all expansion. |
| `add_offer_first` | Thin offer catalog (< 2) when scale engine recommends offer diversification. |
| `launch_account` | Launch candidate exists, readiness adequate, cannibalization manageable. |
| `increase_output` | Exploitation beats expansion (incremental existing > incremental new × 0.85). |
| `suppress_account` | Critical/suspended account health. |
| `pause_account` | Low profit per post + high fatigue. |
| `shift_platform` | Platform-specific expansion recommended. |
| `shift_niche` | Niche spinoff recommended. |
| `merge_accounts` | Overlapping accounts with high cannibalization. |
| `do_nothing` | No action justified — stable portfolio. |

## Every command includes

| Field | Purpose |
|-------|---------|
| `exact_instruction` | The concrete command (not advice) |
| `comparison` | `{incremental_new, incremental_existing, ratio, winner}` — mandatory on every command |
| `platform_fit` | `{platform, fit_score, reason}` |
| `niche_fit` | `{niche, sub_niche, fit_score, reason}` |
| `monetization_path` | `{primary_method, secondary_method, expected_rpm}` |
| `cannibalization_analysis` | `{risk, overlap_accounts, mitigation}` |
| `success_threshold` | `{metric, target_value, timeframe_days}` |
| `failure_threshold` | `{metric, floor_value, timeframe_days, action_on_failure}` |
| `first_week_plan` | Day-by-day output plan (7 days for launch commands) |
| `blocking_factors` | What must be resolved first |
| `evidence` | Supporting data snapshot |
| `execution_spec` | Executable context: platform, niche/sub-niche, **content_role** (mapped from candidate type), avatar/persona line, monetization path, language/geo where applicable |
| `required_resources` | Estimated cash outlay, ops hours week one, creative dependencies, urgency score |

## Portfolio control directive (per recompute)

Persisted on `growth_command_runs.portfolio_directive` and returned on recompute; also exposed as `latest_portfolio_directive` on `GET /portfolio-assessment` after at least one successful recompute.

| Field | Purpose |
|-------|---------|
| `current_account_count` | Active creator accounts for the brand |
| `recommended_account_count` | From `scale_recommendations.recommended_account_count` |
| `account_count_delta` | Target minus current |
| `explanation` | Deterministic narrative tying scale key, comparison winner, leaks, platform balance |
| `confidence` | Anchored to `expansion_confidence` from scale recommendation |
| `evidence` | Structured inputs (scale key, incremental profits, leaks, platform lists) |
| `downstream_action` | What to run next (execute top command, then recompute) |
| `urgency` | Max urgency across generated commands |
| `hold_vs_expand` | `expand` \| `hold` \| `remediate_before_expand` \| `cut_or_consolidate` |
| `next_best_command_type` | Type of the highest-priority command |
| `comfort_mode` | Always `false` — engine scans for upside or blockers |

## Heuristics (explicit and documented)

### Comparison threshold
- New account expansion recommended only when `incremental_new > incremental_existing × 1.15`
- More output recommended when `incremental_existing > incremental_new × 0.85`
- Tie when neither condition met

### Cannibalization gating
- Risk > 0.6: launch requires explicit niche-differentiated angle or different platform
- Risk > 0.4: launch requires separated sub-niche and content style
- Risk < 0.4: safe to launch

### Command ranking
1. Fixes first (`fix_funnel_first`, `add_offer_first`)
2. Launches (`launch_account`)
3. Output increases (`increase_output`)
4. Platform/niche shifts
5. Suppressions/pauses
6. Hold (`do_nothing`)

Within each group, sorted by priority descending.

### Platform fit scoring
- 0.9 if no existing accounts on target platform
- 0.7 if 1 existing account
- 0.4 if 2+ existing accounts

### Success/failure thresholds
| Command | Success metric | Failure metric | Failure action |
|---------|---------------|----------------|----------------|
| `launch_account` | Weekly profit > 30% of expected upside within 60 days | Weekly profit < -$20 within 90 days | `pause_account` |
| `increase_output` | Incremental RPM > $2 within 30 days | RPM decline > 15% within 45 days | `revert_output_volume` |

## Portfolio balance analysis

`assess_portfolio_balance` detects:
- **Overbuilt** platforms: > 50% share with 2+ accounts
- **Underbuilt** platforms: single account on platform when total >= 3
- **Absent** platforms: no accounts at all

## Whitespace detection

`find_whitespace` finds:
- Platforms with zero accounts
- Geo/language expansion opportunities from Phase 6 recommendations
- Scored by opportunity potential

## API

| Method | Path | Side effects |
|--------|------|-------------|
| POST | `/brands/{id}/growth-commands/recompute` | Supersedes prior commands; writes new `growth_commands` with `created_in_run_id`; completes `growth_command_runs`; syncs `operator_alerts` (`growth_commander_priority`); audit log `growth_commander.recomputed` |
| GET | `/brands/{id}/growth-commands` | Read-only (active commands only) |
| GET | `/brands/{id}/growth-command-runs` | Read-only audit history (includes `portfolio_directive` per run) |
| GET | `/brands/{id}/portfolio-assessment` | Read-only: live balance + whitespace + `latest_portfolio_directive` when available |

## Operator Cockpit integration

Top 5 growth commands included in cockpit response as `growth_commands`.

## UI

Dashboard `/dashboard/growth-commander`: active commands (with execution spec, resources, evidence), portfolio tab (balance + **portfolio control directive**), whitespace, recent recomputes.

## Tests

- Unit: `tests/unit/test_growth_commander.py` — command generation, portfolio directive, content role mapping, comparison, cannibalization, ranking, balance, whitespace
- Integration: `tests/integration/test_growth_commander_flow.py` — recompute-then-read, runs, GETs, portfolio assessment including `latest_portfolio_directive`

## Migrations

- `growth_commands` + `growth_command_runs` base tables; follow-up adds `execution_spec`, `required_resources`, supersede columns, `portfolio_directive` on runs.
