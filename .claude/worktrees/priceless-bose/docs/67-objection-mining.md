# 67 — Objection Mining

## Purpose

Detects recurring buyer objections, hesitations, and trust blockers from audience responses and feeds them into content, offers, and follow-up. Not a comment log — it extracts monetizable resistance and routes it to the systems that can address it.

## 9 Objection Types

| Type | Monetization Impact | Response Angle |
|------|-------------------|----------------|
| price | 90% | Value demonstration, ROI |
| trust | 85% | Social proof, testimonials |
| proof | 80% | Data-heavy evidence |
| competitor | 75% | Honest comparison |
| skepticism | 70% | Transparency, behind-the-scenes |
| relevance | 60% | Segment-specific targeting |
| complexity | 55% | Simplification, walkthroughs |
| timing | 50% | Urgency + patience balance |
| identity | 40% | Aspirational identity matching |

## Sources

Comments, replies (via CommentIngestion). Architecture supports DMs, email replies, CRM notes, support tickets, and sales objections when those ingestion paths are active.

## Engine Logic

1. **Extraction** — keyword-based classification against 9 objection vocabularies
2. **Clustering** — groups signals by type with representative texts
3. **Severity scoring** — strong negative markers increase severity
4. **Monetization impact** — type-based impact ranking, boosted when offer is attached
5. **Response angle generation** — per-type content/CTA/offer angles from RESPONSE_ANGLES map
6. **Downstream routing** — each type maps to target channels (content_brief, offer_angle, cta_generation, landing_page, email_followup)

## Downstream Consumers

| Consumer | How objections flow |
|----------|-------------------|
| Content briefs | Top 3 objection clusters injected into brief_metadata with type, impact, response angle |
| Copilot | Top 5 objection clusters + priority summary in grounded context |
| Offer angle selection | Response angles map to offer_angle recommendations |
| CTA generation | CTA angles per objection type |
| Pattern memory | Audience response patterns informed by objection frequency |

## API

| Endpoint | Method |
|----------|--------|
| `/{brand_id}/objection-signals` | GET |
| `/{brand_id}/objection-clusters` | GET |
| `/{brand_id}/objection-responses` | GET |
| `/{brand_id}/objection-priority` | GET |
| `/{brand_id}/objection-mining/recompute` | POST |

## Worker

`recompute_objection_mining` — runs every 6 hours for all brands.
