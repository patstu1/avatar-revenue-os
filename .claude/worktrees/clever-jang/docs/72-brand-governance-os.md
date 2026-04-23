# 72 — Brand Governance OS

## Purpose
Real governance layer protecting brand quality across multiple brands, business units, and clients. Not a settings page — it enforces rules that block non-compliant content.

## 10 Tables
bg_profiles, bg_voice_rules, bg_knowledge_bases, bg_knowledge_docs, bg_audience_profiles, bg_editorial_rules, bg_asset_libraries, bg_style_tokens, bg_violations, bg_approvals

## Voice Rule Types
banned_phrase, required_phrase, tone, claim, cta, disclosure, trust_risk, style

## Editorial Scoring
tone_compliance + disclosure_compliance + claim_accuracy + proof_completeness + cta_completeness + style_standard → pass/warn/fail

## Multi-Brand Isolation
Each rule, knowledge base, audience, asset, violation, and approval is brand_id-scoped. The engine checks content brand_id matches governance brand_id.

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Content generation | Brief metadata includes governance rules (tone, banned phrases, required phrases, disclosures) |
| Quality governor | Governance violations feed quality scoring |
| Copilot | Governance violations surfaced in grounded context |
| Landing page engine | Disclosure rules apply to page blocks |
| Campaign constructor | Campaign tone/CTA rules checked against governance |

## API (9 endpoints)
governance-profiles, governance-voice-rules, governance-knowledge, governance-audiences, governance-assets, governance-violations, governance-approvals, governance/recompute, governance/{content_item_id}/evaluate

## Worker
`recompute_brand_governance` — every 4h
