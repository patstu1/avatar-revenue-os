# Provider Stack + Tiered Routing

## Overview
The system routes every content generation task to the cheapest provider that meets its quality requirement. 70% of calls go to budget providers, 20% to standard, 10% to premium.

## Provider Taxonomy

### Text (LLMs)
| Tier | Provider | Cost | Used for |
|------|----------|------|----------|
| Hero | Claude Sonnet 4.6 | $3/$15 per 1M tokens | Orchestration, strategy, hero copy |
| Standard | Gemini 2.5 Flash | $0.30/$2.50 per 1M tokens | Captions, descriptions, scheduling |
| Bulk | DeepSeek V3.2 | $0.28/$0.42 per 1M tokens | Hashtags, SEO, scanning, summaries |

### Images
| Tier | Provider | Cost | Used for |
|------|----------|------|----------|
| Hero | GPT Image 1.5 | ~$0.04/image | Ad creatives, hero shots |
| Standard/Bulk | Imagen 4 Fast | ~$0.02/image | Thumbnails, social graphics |
| Variety | Flux 2 Pro | ~$0.055/image | Alternative aesthetics |

### Video
| Tier | Provider | Cost | Used for |
|------|----------|------|----------|
| Hero | Runway Gen-4 Turbo | ~$0.10-0.48/clip | Cinematic hero content |
| Standard/Bulk | Kling AI | ~$0.07/sec | B-roll, social clips, reels |

### Avatar
| Tier | Provider | Cost | Used for |
|------|----------|------|----------|
| All | HeyGen | $29/mo unlimited | Talking heads (primary) |
| Budget | D-ID | Pay-per-use | Bulk affiliate review avatars |

### Voice
| Tier | Provider | Cost | Used for |
|------|----------|------|----------|
| Hero | ElevenLabs | ~$0.18-0.30/1K chars | Brand voice, hero narration |
| Standard | Fish Audio | ~$0.015/1K chars | Standard voiceovers |
| Bulk | Voxtral TTS | ~$0.016/1K chars | A/B test narrations, filler |

### Music
| Tier | Provider | Cost | Used for |
|------|----------|------|----------|
| All | Suno | ~$10-30/mo | Background tracks, jingles |

## Routing Logic
1. Every task is classified by quality tier based on platform + campaign type
2. Promoted content always gets hero tier
3. X/Twitter/Reddit default to bulk (nobody notices the difference)
4. Blog defaults to hero (reader-facing quality matters)
5. Everything else defaults to standard

## Cost Projections (300 posts/month)
- With tiered routing: ~$112/mo ($0.38/post)
- Without routing: ~$211/mo ($0.70/post)
- Savings: 47%

## Configuration
Set env vars per provider tier. See `.env.example` for the full list.

## API
- POST `/brands/{id}/content-routing/route` — classify + route a task
- GET `/brands/{id}/content-routing/decisions` — list routing history
- GET `/brands/{id}/content-routing/cost-reports` — cost rollups
- POST `/brands/{id}/content-routing/cost-reports/recompute` — regenerate
- GET `/brands/{id}/content-routing/monthly-projection` — forecast

## Migration
`content_routing_001` (down_revision: `content_form_001`)
