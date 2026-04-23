# 70 — Landing Page Engine + Campaign Constructor

## Landing Page Engine

### Page Types (11)
product, review, comparison, advertorial, presell, optin, lead_magnet, quiz_funnel, authority, creator_revenue, sponsor

### Per Page
page_type, offer_id, headline, subheadline, hook_angle, proof/objection/cta/disclosure/media blocks, tracking_params, destination_url, status, publish_status, truth_label, performance_json, blocker_state

### Quality Scoring
35% trust (disclosure + proof + objection coverage) + 40% conversion fit (CTA + headline + offer CVR) + 25% objection coverage. Verdicts: pass/warn/fail.

### Truth Labels
- `recommendation_only` — page exists in system but not published externally
- `published` — live URL exists
- `no_page` — no page generated for this offer

## Campaign Constructor

### Campaign Types (8)
affiliate, lead_gen, product_conversion, creator_revenue, sponsor, newsletter_growth, authority_building, experiment

### Per Campaign
campaign_type, objective, target_platforms, target_accounts, audience, content_family, hook_family, landing_page_id, cta_family, offer, monetization_path, followup_path, budget_tier, expected_upside/cost/confidence, launch_status, truth_label

### Blocker Detection
- no_accounts — no target accounts assigned
- no_landing_page — monetization campaign without destination
- no_monetization — no revenue path defined
- suppressed_hook — hook family under failure-family suppression
- provider_blocked — provider dependency blocked

## Downstream Consumers

| Consumer | How it connects |
|----------|----------------|
| Content generation | Brief metadata includes campaign + landing page info |
| Copilot | Top 5 campaigns + campaign blockers in grounded context |
| Content form selector | Campaign content_family informs form selection |
| Live execution | Campaigns provide tracking params and destination URLs |
| Opportunity cost | Campaign confidence feeds action ranking |

## API Endpoints

### Landing Pages
`GET /{id}/landing-pages`, `POST /{id}/landing-pages/recompute`, `GET /{id}/landing-page-variants`, `GET /{id}/landing-page-quality`

### Campaigns
`GET /{id}/campaigns`, `POST /{id}/campaigns/recompute`, `GET /{id}/campaign-variants`, `GET /{id}/campaign-blockers`

## Workers
- `recompute_landing_pages` — every 8h
- `recompute_campaigns` — every 8h

## Remaining External Blockers
Publishing/execution of landing pages to external hosting (e.g. Vercel, Netlify, custom domain) requires external deployment integration. Pages are currently generated, scored, and stored in the system with `truth_label: recommendation_only`. When a publish integration is configured, the system updates to `published` with a live `destination_url`.
