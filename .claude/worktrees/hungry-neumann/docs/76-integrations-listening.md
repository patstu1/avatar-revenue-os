# 76 — Integrations + Listening OS

## Purpose
Business-intelligence ingestion and response layer. Not a connector list — it ingests signals from CRM, social, support, and internal systems, clusters them, and routes actionable intelligence to content generation, campaigns, and the operator.

## 8 Tables
il_connectors, il_connector_syncs, il_social_listening, il_competitor_signals, il_business_signals, il_listening_clusters, il_signal_responses, il_blockers

## Connector Types
crm, erp, internal_db, social_listening, analytics, support_desk, email_marketing, custom_api

## Signal Types
brand_mention, competitor_mention, objection_cluster, demand_signal, trend_signal, sales_signal, support_pain

## Engine Logic
1. **Connector sync evaluation** — checks endpoint, credentials, last sync status
2. **Signal clustering** — groups by type with sentiment, relevance, representative texts
3. **Competitor extraction** — scores competitor signals by opportunity (switching intent, disappointment)
4. **Business signal routing** — maps signals to content_generation, objection_mining, offer_lab, campaign_constructor, copilot
5. **Response recommendations** — per-cluster action recommendations with target system and priority

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Top 3 listening clusters with recommended actions |
| Content generation | Demand/trend signals route to content creation |
| Objection mining | Support pain signals feed objection clusters |
| Campaign constructor | Demand signals trigger campaign construction |
| Executive dashboard | Signal volume and sentiment trends |

## API (6 endpoints)
connectors, listening, competitor-signals, clusters, blockers, recompute

## Worker
`recompute_listening` — every 2 hours
