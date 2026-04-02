# 79 — Offer Lab

## Purpose
Real offer-development and offer-optimization system that generates variants, tests pricing/positioning, creates bundles/upsells, detects issues, and learns from measured performance.

## 10 Tables
ol_offers, ol_variants, ol_pricing_tests, ol_positioning_tests, ol_bundles, ol_upsells, ol_downsells, ol_cross_sells, ol_blockers, ol_learning

## Variant Types (8)
budget, premium, convenience, authority, comparison, problem_relief, identity, recurring_value

## Offer Scoring (5 factors)
30% expected upside + 20% confidence + 15% platform fit + 15% margin + 20% trust adjustment

## Issue Detection
- no_expected_upside — offer not validated
- no_price_point — margin calculation impossible
- low_confidence — needs testing
- trust_platform_mismatch — high trust offer on low-fit platform

## Revision Recommendations
revise_pricing, run_test, add_proof, change_positioning, suppress_offer, keep_current

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Landing page engine | Best offer drives page content |
| Campaign constructor | Campaigns select best offer for their type |
| Affiliate system | Offer lab feeds affiliate offer ranking |
| Content generation | Best offer angle injected into briefs |
| Copilot | Best offer surfaced in grounded context |
| Opportunity cost | Offer performance feeds action ranking |

## API (6 endpoints)
offers, offers/recompute, variants, bundles, blockers, learning

## Worker
`recompute_offer_lab` — every 8 hours
