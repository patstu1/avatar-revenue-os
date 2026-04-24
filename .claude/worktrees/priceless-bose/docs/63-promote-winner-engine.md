# 63 — Experiment / Promote-Winner Engine

## Purpose

Active testing-and-promotion system that deliberately tests competing variants, decides winners with statistical evidence, promotes winners into default behavior, and suppresses losers.

## Experiment Types

hook, content_form, cta_type, offer_angle, avatar_vs_non_avatar, faceless_vs_face_forward, short_vs_long, trust_vs_fast_scroll, posting_window, monetization_path, account_role_strategy

## Tables (7)

| Table | Purpose |
|-------|---------|
| `pw_active_experiments` | Live experiment definitions with hypothesis, tested variable, metrics |
| `pw_experiment_variants` | Competing variants within each experiment |
| `pw_experiment_assignments` | Content item → variant assignments |
| `pw_experiment_observations` | Metric observations per variant |
| `pw_experiment_winners` | Declared winners with margin + confidence |
| `pw_experiment_losers` | Declared losers, suppressed |
| `promoted_winner_rules` | Rules that change downstream behavior |

## Engine Logic

1. **Creation** — validates ≥2 variants, normalizes experiment type
2. **Assignment** — deterministic hash-based assignment for reproducibility
3. **Winner detection** — statistical significance test with configurable confidence threshold and minimum sample size
4. **Loser suppression** — losers marked `suppressed=True`
5. **Promote-winner** — generates `PromotedWinnerRule` entries that inject into briefs, form selection, monetization defaults
6. **Decay/retest** — checks promoted winners for performance decay (>30% drop), staleness (>90 days), or confidence erosion (<85%)
7. **Insufficient sample** — returns progress percentage when sample size is below threshold

## How Winners Are Promoted

When a winner is found:
1. `PromotedWinnerRule` rows are created with `rule_type` matching the tested variable
2. `brief_injection` rules inject preferred patterns into content brief generation
3. `default_content_form` rules boost content form selector confidence scores
4. `monetization_default` rules set preferred monetization paths
5. Winner is written to `WinningPatternMemory` for cross-system reuse
6. Losers are written to `LosingPatternMemory` for suppression

## Downstream Consumers

| Consumer | Integration |
|----------|-------------|
| Content brief generation | Injects `promoted_winner_rules` into `brief_metadata` |
| Content form selector | Boosts confidence of forms matching promoted winner rules |
| Operator copilot | Active experiments + promoted rules in grounded context |
| Pattern memory | Winners → `WinningPatternMemory`, losers → `LosingPatternMemory` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{brand_id}/experiments` | GET | List experiments |
| `/{brand_id}/experiments` | POST | Create experiment with variants |
| `/{brand_id}/experiments/{id}/observe` | POST | Add observation |
| `/{brand_id}/experiments/{id}/evaluate` | POST | Evaluate for winner |
| `/{brand_id}/experiment-winners` | GET | List winners |
| `/{brand_id}/experiment-losers` | GET | List losers |
| `/{brand_id}/promoted-rules` | GET | List active promotion rules |
| `/{brand_id}/experiments/decay-check` | POST | Check for decayed promotions |

## Worker

`evaluate_and_promote` — runs every 4 hours, evaluates all active experiments and checks promoted winners for decay.
