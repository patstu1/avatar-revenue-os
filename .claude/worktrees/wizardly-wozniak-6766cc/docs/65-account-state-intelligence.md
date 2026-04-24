# 65 — Account-State Intelligence

## Purpose

Live account-state engine that classifies every account into one of 12 operating states and changes system behavior accordingly. Not cosmetic labels — each state has policies that affect content forms, monetization intensity, posting cadence, expansion eligibility, and blocked actions.

## 12 Account States

| State | Monetization | Cadence | Expansion | Behavior |
|-------|-------------|---------|-----------|----------|
| newborn | none | slow | no | Establish presence |
| warming | low | normal | no | Build consistency |
| early_signal | low | normal | no | Double down on engagement |
| scaling | medium | aggressive | yes | Increase volume + test monetization |
| monetizing | high | aggressive | yes | Optimize conversions |
| authority_building | medium | normal | yes | Trust-building long-form |
| trust_repair | none | slow | no | Pause monetization, value-first |
| saturated | low | reduced | no | Refresh creative, reduce volume |
| cooling | low | reduced | no | Investigate decline |
| weak | none | minimal | no | Quality audit, consider pivot |
| suppressed | none | paused | no | Platform resolution |
| blocked | none | paused | no | Platform support + backup |

## Inputs

age_days, post_count, impressions, engagement_rate, conversion_rate, fatigue_score, saturation_score, account_health, total_revenue, total_profit, blocker_state

## Downstream Impact

| Consumer | How state changes behavior |
|----------|--------------------------|
| Content form selector | Penalizes forms not suitable for current state |
| Content routing | Blocks hero tier for newborn/warming/weak/suppressed/blocked |
| Content generation | Brief metadata includes state, monetization policy, blocked actions |
| Capital allocator | Account health feeds expected return scoring |
| Copilot | Full account state summary in grounded context |
| Expansion advisor | Only expansion-eligible states can trigger expansion |
| Kill/scale logic | Weak/blocked states feed starvation decisions |

## API

| Endpoint | Method |
|----------|--------|
| `/{brand_id}/account-state` | GET |
| `/{brand_id}/account-state/recompute` | POST |
| `/{brand_id}/account-state/transitions` | GET |
| `/{brand_id}/account-state/actions` | GET |

## Worker

`recompute_account_state_intel` — runs every 4 hours for all brands.
