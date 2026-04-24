# 64 — Portfolio Capital Allocator

## Purpose

Active portfolio-level resource allocator that decides where to spend premium model budget, media-generation budget, content volume, operator attention, and monetization focus. Not a spreadsheet — it actively makes decisions that downstream systems consume.

## Allocation Targets

Allocates across: accounts, platforms, offers, content forms, monetization paths, experiments, creator revenue avenues, brands.

## Inputs Used

| Input | Source |
|-------|--------|
| Expected upside | ROI calculation from cost + return |
| Expected cost | Offer economics, provider costs |
| Confidence | Account health, pattern win scores |
| Account health | CreatorAccount.account_health |
| Content fatigue | Fatigue scores from pattern decay |
| Pattern memory | WinningPatternCluster avg_win_score |
| Experiment winners | ActiveExperiment status |
| Current performance | PerformanceMetric aggregates |
| Provider cost | Tiered routing cost data |
| Conversion quality | Offer conversion rates |

## Engine Logic

1. **Expected return scoring** — weighted: ROI 30%, confidence 20%, health 15%, pattern win 15%, fatigue penalty 10%, conversion quality 10%
2. **Constrained solver** — sorts by return score, applies min/max constraints, allocates budget proportionally
3. **Premium vs cheap** — hero tier for return score ≥ 0.55 or pattern win ≥ 0.6; bulk otherwise
4. **Experiment reserve** — 10% of total budget reserved for experiments
5. **Starvation** — targets with return score < 0.15 get ≤ 2% allocation, marked as starved
6. **Rebalancing** — compares current vs actual performance, boosts outperformers, starves underperformers

## Downstream Consumers

| Consumer | Integration |
|----------|-------------|
| Content routing | Allocation tier overrides provider selection (hero/bulk) |
| Content generation | Brief metadata includes allocation tier + budget + starved flag |
| Operator copilot | Allocation summary + starved lanes in grounded context |
| Portfolio worker | Allocation weights inform rebalancing |

## API

| Endpoint | Method |
|----------|--------|
| `/{brand_id}/capital-allocation` | GET |
| `/{brand_id}/capital-allocation/recompute` | POST |
| `/{brand_id}/capital-allocation/decisions` | GET |
| `/{brand_id}/capital-allocation/rebalances` | GET |

## Worker

`recompute_capital_allocation` — runs every 6 hours for all brands.
