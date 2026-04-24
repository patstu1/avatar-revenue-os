# 77 — Executive Intelligence + Service Layer

## Purpose
Executive command and governance layer with KPI reporting, predictive analytics, cost/usage attribution, provider reliability, and hybrid human+AI oversight mode.

## 7 Tables
ei_kpi_reports, ei_forecasts, ei_usage_cost, ei_provider_uptime, ei_oversight_mode, ei_service_health, ei_alerts

## KPIs Tracked
total_revenue, total_profit, total_spend, content_produced, content_published, total_impressions, avg_engagement_rate, avg_conversion_rate, active_accounts, active_campaigns

## Forecast Engine
Trend-based prediction from historical values with stability-weighted confidence, risk/opportunity factor identification.

## Oversight Modes
- **full_auto** — AI accuracy >95%, auto rate >70%
- **hybrid** — AI accuracy >85%
- **human_primary** — AI accuracy >70%
- **human_only** — AI accuracy <70%

## Provider Reliability Grades
A (99%+), B (95-99%), C (90-95%), D (80-90%), F (<80%)

## Executive Alerts
- zero_revenue (critical)
- declining_forecast (high)
- provider_reliability (high)
- ai_accuracy_low (high)

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Executive summary (revenue, profit, content, campaigns, critical alerts) |
| Command center | KPIs + alerts feed top-level dashboard |
| Gatekeeper | Oversight mode informs autonomous readiness |
| Portfolio allocator | KPIs inform budget reallocation |

## API (6 endpoints)
kpis, forecasts, uptime, oversight, alerts, recompute

## Worker
`recompute_executive_intel` — daily at 6am
