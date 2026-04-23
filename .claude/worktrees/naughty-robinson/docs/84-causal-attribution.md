# 84 — Causal Attribution Layer

## Purpose
Distinguishes likely causal lift from noise. Better than naive correlation — it scores temporal proximity, driver directness, and change magnitude to produce confidence-weighted credit allocation.

## 5 Tables
ca_attribution_reports, ca_signals, ca_hypotheses, ca_confidence_reports, ca_credit_allocations

## Driver Types (10)
content_change, offer_change, campaign_change, platform_shift, seasonal_pattern, experiment_result, account_state_change, provider_change, external_event, audience_shift

## Engine Logic
1. **Change-point detection** — finds significant shifts (>15%) in metric time series
2. **Candidate cause extraction** — matches change points to temporally proximate system events
3. **Causal confidence scoring** — 40% temporal proximity + 30% directness + 30% magnitude
4. **Multi-factor credit allocation** — proportional to confidence, with cautious flags for low-confidence
5. **Noise penalty** — flags hypotheses below 10% confidence or <5% change as likely noise

## Confidence Thresholds
- High confidence: ≥70% → "Promote confidently"
- Moderate: ≥50% → "Promote cautiously"
- Below 50% → "Do not act yet — may be noise"
- Below 10% → Noise-flagged

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Attribution summary (top drivers + direction + magnitude) in context |
| Experiment engine | Causal confidence gates promote-winner decisions |
| Portfolio allocator | Credit allocation informs budget reallocation |
| Opportunity cost | Causal confidence feeds action ranking |
| Gatekeeper | Low-confidence attributions flagged before promotion |
| Offer lab | Offer-change lift/drop attributed causally |
| Growth commander | Confident drivers prioritized as commands |

## API (5 endpoints)
causal-attribution, causal-attribution/recompute, hypotheses, credits, confidence

## Worker
`recompute_causal_attribution` — every 6 hours
