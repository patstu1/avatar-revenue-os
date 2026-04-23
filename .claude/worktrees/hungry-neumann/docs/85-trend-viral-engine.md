# 85 — Trend / Viral Opportunity Engine

## Purpose
Continuous opportunity-detection system that scans for breakout trends, scores them by revenue and strategic value, suppresses noise, and routes real opportunities into content generation, campaigns, and the copilot.

## 8 Tables
tv_signals, tv_velocity, tv_opportunities, tv_opp_scores, tv_duplicates, tv_suppressions, tv_blockers, tv_source_health

## Scan Cadence
- **Light scan (60 seconds)**: fetch signals, compute deltas, dedup — no expensive analysis
- **Deep analysis (every 5 minutes)**: full scoring, classification, opportunity creation — only on threshold-crossing signals (velocity > 0.5)

## Engine Logic
1. **Signal extraction** — normalize from discovery/listening sources, dedup against existing
2. **Velocity detection** — acceleration = (current - previous) / previous; breakout when accel > 1.0 or velocity > 2.0
3. **Novelty + dedup** — Jaccard similarity > 0.6 = duplicate, stored in tv_duplicates
4. **Opportunity scoring** — 20% velocity + 15% novelty + 10% relevance + 20% revenue + 10% platform + 10% account + 5% form - 5% saturation - 5% compliance
5. **Classification** — monetization (high revenue + relevance), pure_reach (high velocity + low revenue), authority_building (high relevance + low velocity), growth, community_engagement
6. **Suppression** — composite < 0.15, saturation > 0.8, matching suppression rules, off-brand

## Monetization vs Growth
| Type | When | Monetization Path |
|------|------|-------------------|
| monetization | revenue > 0.6, relevance > 0.5 | affiliate |
| pure_reach | velocity > 0.7, revenue < 0.3 | none_growth_only |
| authority_building | relevance > 0.6, velocity < 0.4 | organic |
| growth | velocity > 0.4 | soft_monetization or none |

## Truth Labels
live_source, internal_proxy, recommendation_only, blocked_by_credentials

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Top 3 trend opportunities in grounded context |
| Content generation | Best trend topic for next content brief |
| Campaign constructor | Trend-based campaign creation |
| Opportunity cost | Trend urgency feeds action ranking |
| Growth commander | Breakout trends become growth commands |

## API (7 endpoints)
trend-signals, trend-velocity, viral-opportunities, viral-opportunities/recompute, trend-blockers, trend-source-health, top-trend-opportunities

## Workers
- `trend_light_scan` — every 60 seconds
- `trend_deep_analysis` — every 5 minutes
