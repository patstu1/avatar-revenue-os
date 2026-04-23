# 62 — Winning-Pattern Memory

## Purpose

The Winning-Pattern Memory system captures, scores, clusters, and reuses what actually works across content performance and conversion performance. Every content item, once measured, feeds evidence into a permanent memory layer that the entire machine can query.

The system stops the machine from acting like every new content item starts from zero.

## Memory Model

### 6 Tables

| Table | Purpose |
|-------|---------|
| `winning_pattern_memory` | Patterns that meet the win threshold (score ≥ 0.6) |
| `winning_pattern_evidence` | Individual content items backing each winning pattern |
| `winning_pattern_clusters` | Grouped pattern families by type + platform |
| `losing_pattern_memory` | Patterns that fall below the loss threshold (score < 0.25) — suppressed |
| `pattern_reuse_recommendations` | Cross-platform reuse recommendations for winning patterns |
| `pattern_decay_reports` | Decay detection reports for patterns weakening over time |

### Pattern Fields

Each pattern stores: `pattern_type`, `pattern_name`, `pattern_signature` (sha256 hash), `platform`, `niche`, `sub_niche`, `content_form`, `offer_id`, `monetization_method`, `performance_band`, `confidence`, `win_score`, `decay_score`, `usage_count`, `last_seen_at`, `explanation`, `evidence_json`.

## Pattern Taxonomy

### 7 Pattern Types

1. **Hook** — direct_pain, curiosity, comparison, things_i_wish, dont_buy_until, authority_led, testimonial_led
2. **Creative Structure** — problem_solution_cta, listicle, before_after, talking_head_broll, text_carousel, fast_cut_comparison, demo_voiceover, objection_answer
3. **Content Form** — avatar_short_form, faceless_short_form, image_carousel, text_thread, product_demo, authority_article, review_page, email_sequence
4. **Offer Angle** — budget, premium, convenience, comparison, problem_relief, identity, productivity, health
5. **CTA** — soft, direct, link_in_bio, comment_to_get, save_share, urgency, newsletter_signup, product_click
6. **Monetization** — affiliate, lead_gen, premium_access, service, recurring, sponsor
7. **Audience Response** — objection_heavy_high_conversion, high_engagement_low_monetization, trust_building_winner, reach_winner, conversion_winner

## Scoring Logic

Win score = `0.25 × engagement_score + 0.30 × conversion_score + 0.30 × profit_score + 0.15 × reach_score`

| Component | Calculation |
|-----------|------------|
| engagement_score | min(1.0, avg_engagement_rate × 10) |
| conversion_score | min(1.0, avg_conversion_rate × 20) |
| profit_score | min(1.0, avg_profit / 100) |
| reach_score | min(1.0, total_impressions / 50000) |

**Sample penalty**: confidence = win_score × max(0.3, min(1.0, n / 10))

**Thresholds**: win ≥ 0.6, lose < 0.25, minimum evidence = 3

**Performance bands**: hero (>0.7), strong (>0.5), standard (>0.3), weak (≤0.3)

## Decay Logic

Decay detection compares previous `win_score` to current evidence-based `win_score`.

- **Score decline**: decay_rate > 15% → flagged
- **Overuse saturation**: usage_count > 20 → flagged
- **Recommendation**: "Retire or refresh" if decaying; "Monitor for fatigue" if overused but not declining

## Reuse Logic

For each winning pattern, the engine recommends reuse on platforms where that pattern has not yet been tried.

Expected uplift = win_score × 0.7 (cross-platform transfer discount).

Results are sorted by expected uplift, limited to top 20.

## How Memory Is Reused

### Downstream Consumers

| Consumer | How it uses pattern memory |
|----------|---------------------------|
| **Content Brief Generation** | Injects top 5 winning + top 3 losing patterns into `brief_metadata` |
| **Content Form Selector** | Boosts `confidence` score of content forms that have winning patterns |
| **Operator Copilot** | Includes top 10 winning + top 5 losing patterns in grounded context |
| **Experiment Engine** | Can query winning patterns to inform experiment design |
| **Portfolio Allocator** | Winning pattern clusters inform platform allocation weight |
| **Gatekeeper** | Pattern memory availability feeds autonomous readiness checks |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{brand_id}/pattern-memory` | GET | List winning patterns |
| `/{brand_id}/pattern-memory/recompute` | POST | Recompute all patterns from evidence |
| `/{brand_id}/pattern-clusters` | GET | List pattern clusters |
| `/{brand_id}/losing-patterns` | GET | List suppressed losing patterns |
| `/{brand_id}/pattern-reuse` | GET | List reuse recommendations |
| `/{brand_id}/pattern-decay` | GET | List decay reports |

### Workers

- `recompute_pattern_memory` — runs every 6 hours, executes the full chain: extract → score → persist → cluster → decay → reuse

### Frontend

Tabbed dashboard at `/dashboard/pattern-memory` with 5 views: Winning Patterns, Clusters, Losing Patterns, Reuse Recommendations, Decay Reports.
