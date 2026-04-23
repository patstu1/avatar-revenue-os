# 81 — Digital Twin / Simulation Layer

## Purpose
Simulates key strategic decisions before execution. Not a toy forecast — it compares competing moves with expected profit, risk, confidence, and time-to-signal.

## 5 Tables
dt_simulation_runs, dt_scenarios, dt_assumptions, dt_outcomes, dt_recommendations

## 8 Scenario Types
push_volume_vs_launch_account, switch_content_form_vs_keep, push_offer_vs_switch_offer, premium_vs_cheap_asset, push_winner_vs_wait, expand_platform_vs_deepen, keep_campaign_vs_suppress, page_a_vs_page_b

## Engine Logic
1. **Scenario generator** — reads scaling accounts, experiment winners, weak offers, low-confidence campaigns
2. **Outcome estimator** — profit = upside - cost, risk_adjusted = profit × (1 - risk)
3. **Risk estimator** — based on uncertainty, cost, time horizon
4. **Confidence estimator** — stability-weighted from risk and cost
5. **Recommendation selector** — picks option with highest risk_adjusted_profit × confidence

## Each Scenario Answers
- What happens if we do X instead of Y?
- Which option has higher expected profit?
- Which option is safer?
- What evidence is missing to decide better?

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Top 3 simulation recommendations in grounded context |
| Expansion advisor | Push volume vs launch account simulated before acting |
| Portfolio allocator | Premium vs cheap simulated before budget allocation |
| Opportunity cost | Simulation profit deltas feed action ranking |
| Gatekeeper | Low-confidence recommendations flagged |

## API (4 endpoints)
simulations, simulations/run, simulations/scenarios, simulations/recommendations

## Worker
`run_simulations` — daily at 4am
