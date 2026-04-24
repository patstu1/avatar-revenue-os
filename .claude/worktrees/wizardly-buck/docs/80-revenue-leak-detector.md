# 80 — Revenue Leak Detector

## Purpose
Detects where the machine is losing revenue across content, landing pages, campaigns, offers, affiliate flows, platforms, and accounts. Routes corrective actions to the right systems.

## 5 Tables
rld_reports, rld_events, rld_clusters, rld_corrections, rld_loss_estimates

## 14 Leak Types

| Leak Type | Severity | Corrective Target |
|-----------|----------|-------------------|
| high_impressions_low_ctr | high | content_generation |
| high_clicks_low_conversion | critical | landing_page_engine |
| high_engagement_low_monetization | high | offer_lab |
| weak_landing_page | high | landing_page_engine |
| weak_cta_path | medium | campaign_constructor |
| wrong_destination | high | landing_page_engine |
| weak_offer_selection | high | offer_lab |
| weak_affiliate_choice | medium | affiliate_intel |
| underused_winner | high | capital_allocator |
| weak_followup | medium | campaign_constructor |
| blocked_provider | critical | provider_registry |
| weak_upsell_path | medium | offer_lab |
| under_monetized_account | high | account_state |
| under_monetized_platform | medium | capital_allocator |

## Prioritization
priority_score = estimated_loss × urgency × confidence / 100

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Leak summary (count, loss, critical, top type) in grounded context |
| Opportunity cost | Leak fix actions feed action ranking |
| Offer lab | Weak offer leaks trigger revision |
| Campaign constructor | Weak CTA/followup leaks trigger campaign revision |
| Landing page engine | Weak page leaks trigger page rebuild |
| Growth commander | Critical leaks escalated as commands |

## API (5 endpoints)
revenue-leaks, revenue-leaks/recompute, revenue-leaks/events, revenue-leaks/clusters, revenue-leaks/corrections

## Worker
`recompute_revenue_leaks` — every 4 hours
