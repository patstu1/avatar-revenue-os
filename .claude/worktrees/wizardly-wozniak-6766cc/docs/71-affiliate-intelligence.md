# 71 — Elite Affiliate Intelligence + Execution Pack

## Affiliate Data Layer (13 tables)
af_network_accounts, af_merchants, af_offers, af_links, af_clicks, af_conversions, af_commissions, af_payouts, af_blockers, af_disclosures, af_leaks

## Offer Ranking (weighted 0-1)
25% EPC + 15% CVR + 10% commission + 10% refund risk + 10% trust + 10% content fit + 10% platform fit + 10% audience fit

## Truth Loop
content → af_link (with UTM/attribution) → af_click → af_conversion → af_commission → af_payout → profit attribution → ranking update

## Leak Detector
- high_clicks_zero_conversions (critical)
- very_low_conversion (high)
- blocked_offer_still_active (high)
- high_refund_rate (medium)

## Link Execution
Each link carries: offer_id, content_item_id, campaign_id, landing_page_id, platform, account_id, UTM params, disclosure_applied flag

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Top 5 offers + leaks + blockers in grounded context |
| Content generation | Best affiliate offer injected into brief metadata |
| Campaign constructor | Campaigns link to affiliate offers + landing pages |
| Landing page engine | Pages map to affiliate destinations |
| Pattern memory | Affiliate creative performance feeds winning/losing patterns |

## API (8 endpoints)
affiliate-offers, affiliate-offers/recompute, affiliate-links, affiliate-leaks, affiliate-blockers, affiliate-ranking, affiliate-commissions, affiliate-payouts

## Worker
`recompute_affiliate_intel` — every 4h

## Owned Affiliate Program (Part 7)
Architecture: `af_network_accounts` supports own-program tracking. Partner scoring, activation, and fraud checks are **deferred** — the data model supports them but the engine logic is not yet built. This is classified honestly as a future expansion, not a current gap in the affiliate revenue operating layer.

## External Blockers
Click/conversion/commission/payout data import from affiliate networks (Impact, ShareASale, CJ, etc.) requires external API integration. The tables and truth loop are fully wired; when network APIs are configured, data flows automatically through the existing pipeline.
