# Phase 2: Discovery, Scoring & Recommendations

## Module Purpose

Phase 2 transforms raw topic signals into ranked, monetization-aware opportunity recommendations with persisted scoring, explainable decisions, and suppression reasoning.

The system answers: **What is the highest expected-profit content opportunity right now?**

## Schema Additions (13 tables)

| Table | Purpose |
|-------|---------|
| topic_sources | Registry of signal input sources |
| topic_candidates | Candidate topics discovered from signals |
| niche_clusters | Grouped niches with monetization/gap scoring |
| trend_signals | Platform trend data with velocity/volume |
| topic_signals | Signal-to-topic linkage |
| signal_ingestion_runs | Audit trail of every ingestion run |
| opportunity_scores | Persisted composite scores with all components |
| offer_fit_scores | Topic-to-offer fit with audience/intent/friction/revenue dimensions |
| profit_forecasts | Expected profit calculations with assumptions |
| recommendation_queue | Ranked queue of actionable opportunities |
| saturation_reports | Account-level saturation/fatigue/originality analysis |
| opportunity_decisions | Canonical decision records for opportunity scoring |
| monetization_decisions | Canonical decision records for monetization matching |

## Score Formulas

### Opportunity Score (v1)

```
OpportunityScore =
  0.22 * BuyerIntent +
  0.10 * TrendVelocity +
  0.08 * TrendAcceleration +
  0.10 * ContentGap +
  0.12 * HistoricalWinRate +
  0.12 * OfferFit +
  0.18 * ExpectedProfitScore +
  0.08 * PlatformSuitability
  + SeasonalBoost (0-0.15)
  + BrandFitBoost (0-0.10)
  - AudienceFatiguePenalty (0-0.30)
  - SimilarityPenalty (0-0.30)
  - SaturationPenalty (0-0.30)
  - RiskPenalty (0-0.20)
```

**Weights sum to 1.0.** All components normalized to [0, 1]. Result clamped to [0, 1].

Confidence levels:
- **high**: ≥6 signals with data, score > 0.6
- **medium**: ≥3 signals, score > 0.3
- **low**: ≥1 signal
- **insufficient**: no signals

### Profit Forecast (v1)

```
expected_revenue = impressions × CTR × conversion_rate × value_per_conversion
expected_profit = expected_revenue - generation_cost - distribution_cost
                  - fatigue_penalty - risk_penalty
```

Derived metrics: RPM, EPC, ROI.

### Offer Fit Score (v1)

```
fit = 0.25 * audience_alignment + 0.20 * intent_match +
      0.15 * (1 - friction) + 0.15 * repeatability + 0.25 * revenue_potential
```

### Saturation Score (v1)

```
saturation = 0.30 * topic_overlap + 0.25 * posting_rate_penalty +
             0.25 * audience_overlap + 0.20 * similar_content_ratio
```

Actions: suppress (>0.7), reduce (>0.5), monitor (>0.3), maintain (≤0.3).

## Scoring Rules

1. Never recommend a topic solely because it is trending
2. Every recommendation includes explanation and confidence
3. Every recommendation includes monetization path or explicit funnel objective
4. If signal is weak, classify as "monitor" not "scale"
5. All score components and penalties are persisted
6. Suppression reasons are stored in decision objects
7. Scores can be recomputed at any time

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /brands/{id}/signals/ingest | Ingest topics from any source |
| GET | /brands/{id}/signals | Get all signals for a brand |
| GET | /brands/{id}/niches | Get ranked niches |
| POST | /brands/{id}/niches/recompute | Recompute niche clusters |
| GET | /brands/{id}/opportunities | Get scored opportunities |
| POST | /brands/{id}/opportunities/recompute | Score all topics + build queue |
| GET | /brands/{id}/opportunities/queue | Get ranked recommendation queue |
| POST | /brands/{id}/opportunities/{topicId}/forecast | Compute profit forecast |
| POST | /brands/{id}/opportunities/{topicId}/offer-fit | Score all offers against topic |
| POST | /brands/{id}/opportunities/{topicId}/trigger-brief | Create content brief from recommendation |
| GET | /brands/{id}/trends | Get trend signals |
| POST | /brands/{id}/trends/recompute | Reclassify trend signals |
| GET | /brands/{id}/saturation | Get saturation reports (pass ?recompute=true to regenerate) |
| GET | /brands/{id}/profit-forecasts | Get all profit forecasts |
| GET | /brands/{id}/recommendations | Get unactioned recommendations |

## Signal Adapters

| Adapter | Status | Data Source |
|---------|--------|-------------|
| manual_seed | Live | User-provided topics via API |
| internal_performance | Live (reads DB) | Historical performance data |
| internal_comments | Live (reads DB) | Purchase-intent comments |
| trend_feed | Interface only | External trend APIs (needs credentials) |
| offer_inventory | Interface only | External affiliate network APIs (needs credentials) |

## Worker Schedules

Existing Celery beat schedules from Phase 1 support Phase 2:
- `scan_trends` — hourly
- `check_saturation` — every 6 hours

## Tuning Notes

All scoring weights are constants in `packages/scoring/*.py`. To tune:
- `WEIGHTS` dict in `opportunity.py` controls component weights
- Penalty clamps in `opportunity.py` control max penalty impact
- Threshold in `saturation.py` controls suppress/reduce/monitor/maintain cutoffs
- Forecast assumes $2.50 generation + $0.50 distribution cost by default

## What Is Live vs Adapter-Ready

**Live now (no credentials needed):**
- Manual topic ingestion
- Internal performance + comment signal adapters
- All scoring engines (deterministic, rules-based)
- All persistence and decision objects
- Recommendation queue building
- Brief triggering
- All frontend dashboards reading real data

**Adapter-ready (needs credentials):**
- Google Trends / social API ingestion (GenericTrendFeedAdapter)
- Affiliate network feed ingestion (GenericOfferInventoryAdapter)
- Platform-specific trend scanning (YouTube, TikTok APIs)
