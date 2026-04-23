# 68 — Opportunity-Cost Ranking

## Purpose

Ranks all possible actions by what the system loses by not doing them now. Not a generic priority score — it quantifies the dollar cost of delay per action per day.

## 10 Action Types

| Type | Base Delay $/day | Sensitivity |
|------|-----------------|-------------|
| fix_blocker | $12 | critical |
| activate_monetization | $10 | critical |
| promote_winner | $8 | high |
| kill_weak_lane | $6 | high |
| push_volume | $5 | normal |
| publish_asset | $4 | normal |
| switch_content_form | $3 | normal |
| launch_account | $2 | low |
| upgrade_provider | $2 | normal |
| run_experiment | $1 | low |

## Scoring

**Composite rank** = 30% upside + 30% delay cost + 25% urgency + 15% confidence

- **Upside**: raw expected return normalized to 0-1
- **Cost of delay**: base daily rate × (1 + upside/100), type-specific
- **Urgency**: 40% time sensitivity + 35% daily cost normalized + 25% confidence
- **Safe to wait**: composite < 0.25

## Downstream Consumers

| Consumer | Integration |
|----------|-------------|
| Copilot | Top 5 ranked actions in "what matters most" grounded context |
| Growth commander | Ranked actions inform command priority |
| Gatekeeper | Blocking actions bubble to top via fix_blocker type |
| Expansion advisor | Launch account actions ranked against alternatives |
| Portfolio allocator | Action rankings inform budget re-prioritization |

## API

| Endpoint | Method |
|----------|--------|
| `/{brand_id}/opportunity-cost` | GET |
| `/{brand_id}/opportunity-cost/recompute` | POST |
| `/{brand_id}/opportunity-cost/ranked-actions` | GET |

## Worker

`recompute_opportunity_cost` — runs every 4 hours for all brands.
