# Phase 7 — Full intelligence layer (sponsor, comment-cash, knowledge graph, roadmap, capital, cockpit)

## Architecture

Same pattern as Phases 5–6: **POST recompute writes, GETs are read-only.**

- `POST /brands/{id}/phase7/recompute` — runs all 5 engines, cleans prior Phase 7 rows, persists fresh outputs. Operator role required.
- All GET endpoints return persisted data only.

## 1. Sponsor sales engine

### Sponsor-safe category detection

`is_sponsor_safe` checks brand niche against an unsafe keyword list (gambling, adult, weapons, etc.). Safe categories include finance, health, technology, education, etc. Default: safe unless flagged.

### Sponsor package recommendation

`recommend_sponsor_packages` generates package suggestions based on brand metrics:

| Package | Trigger |
|---------|---------|
| `sponsored_integration` | Follower total ≥ 10,000 |
| `brand_awareness` | Total impressions ≥ 50,000 |
| `multi_platform_bundle` | 2+ creator accounts |
| `growth_milestone` | Pre-threshold fallback |

Suggested rates scale with follower count and CPM track record.

## 2. Comment-to-cash engine

### Comment intent classification

`classify_comment_intent` detects:
- **Purchase intent**: "where can I buy", "drop the link", "how much", "discount code", etc.
- **Objections**: "too expensive", "scam", "doesn't work", "better alternative", etc.
- **Questions**: presence of "?"

### Cash signal extraction

`extract_comment_cash_signals` produces actionable signals:
- `purchase_intent_cluster` — with suggested offer and content angle
- `objection_pattern` — with suggestion for objection-handling content
- `question_cluster` — when ≥ 3 questions detected, suggests Q&A content

## 3. Knowledge graph model

Nodes and edges persisted in `knowledge_graph_nodes` / `knowledge_graph_edges`.

### Relationship types

| Edge type | From → To |
|-----------|-----------|
| `niche_uses_platform` | niche → platform |
| `platform_in_geography` | platform → geography |
| `niche_best_offer` | niche → offer (weight = EPC) |
| `niche_best_hook` | niche → hook (weight = win_score) |
| `hook_performs_on_platform` | hook → platform (weight = RPM) |
| `segment_in_niche` | segment → niche |

Node deduplication: same `(node_type, label)` pair produces one node across multiple accounts.

## 4. Roadmap logic

`generate_roadmap` produces up to 10 prioritized recommendations across 6 categories:

| Category | Source |
|----------|--------|
| `content` | Clone winners (win_score drives priority) |
| `account_launch` | Scale engine recommendation |
| `offer` | Thin offer catalog detection |
| `niche_expansion` | Phase 6 geo/language recs |
| `experiment` | Fix revenue leaks |
| `suppression` | Low trust score average |

Items are sorted by `priority_score` (0–100) and capped at 10.

## 5. Capital allocation logic

`compute_capital_allocation` distributes budget across 7 targets:

| Target | Base weight | Adjustments |
|--------|------------|-------------|
| `content_volume` | 30% | −5% if leaks or paid candidates |
| `paid_amplification` | 15% | +5% if paid candidates ready |
| `funnel_optimization` | 15% | +10% if > 3 open leaks |
| `new_accounts` | 10% | +10% if scale engine says "add_*" |
| `sponsor_outreach` | 10% | — |
| `geo_language_expansion` | 10% | +5% if geo recs exist |
| `reserve` | 10% | Absorbs reductions |

Budget base = max(explicit budget, 30% of total profit, $100). ROI multipliers attached per target.

## 6. Operator cockpit guide

The cockpit (`GET /brands/{id}/operator-cockpit`) aggregates the complete operational picture:

- **Top roadmap items** (5) — highest-priority actions across all categories
- **Capital allocation** — where the next dollar should go
- **Open leaks** (5) — biggest revenue leaks from Phase 6
- **Scale action** — current Phase 5 recommendation key + explanation
- **Growth blockers** (5) — Phase 4 bottleneck classifier output
- **Trust average** — mean trust score across accounts
- **Sponsor packages** (3) — top sponsor opportunities
- **Comment-to-cash signals** (5) — actionable comment patterns
- **Expansion targets** — geo/language opportunities from Phase 6

The cockpit is read-only. "Recompute All Intelligence" button triggers `POST /brands/{id}/phase7/recompute`.

## API

| Method | Path | Side effects |
|--------|------|-------------|
| POST | `/brands/{id}/phase7/recompute` | Writes all Phase 7 outputs |
| GET | `/brands/{id}/sponsor-opportunities` | Read-only |
| GET | `/brands/{id}/comment-cash-signals` | Read-only |
| GET | `/brands/{id}/roadmap` | Read-only |
| GET | `/brands/{id}/capital-allocation` | Read-only |
| GET | `/brands/{id}/knowledge-graph` | Read-only |
| GET | `/brands/{id}/operator-cockpit` | Read-only |

## Tests

- Unit: `tests/unit/test_phase7_engines.py` — sponsor ranking, comment intent, knowledge graph, roadmap generation, capital allocation
- Integration: `tests/integration/test_phase7_flow.py` — recompute-then-read, GETs-are-side-effect-free, cockpit aggregation, knowledge graph persistence
