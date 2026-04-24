# 78 — Enterprise-Grade Affiliate Operating System

## Layers Built

### Core (from prior pass — 13 tables)
af_network_accounts, af_merchants, af_offers, af_links, af_clicks, af_conversions, af_commissions, af_payouts, af_blockers, af_disclosures, af_leaks + ranking engine + leak detector

### Enterprise Governance (this pass — 7 tables)
af_governance_rules, af_banned_entities, af_approvals, af_audit_events, af_risk_flags, af_own_partners, af_own_partner_conversions

## Total: 20 affiliate tables

## Governance Controls
- Banned merchant/category lists with enforcement
- Max commission rate rules
- Approval-required workflows for offers/merchants
- Risk flagging (low trust, high refund, no EPC data)
- Full audit trail for affiliate actions
- Platform-specific disclosure rules

## Merchant/Network Ranking
- Merchants ranked by aggregate offer EPC + trust + volume
- Networks ranked by merchant count + offer volume

## Owned Affiliate Program
- Partner onboarding with scoring
- Conversion quality monitoring
- Fraud detection (low quality ratio, flagged conversions)
- Automatic partner suppression when score drops below threshold
- Asset kit assignment tracking
- Revenue/payout tracking per partner

## Truth Loop (end-to-end)
content → af_link (UTM + attribution) → af_click → af_conversion → af_commission → af_payout → profit → ranking update → governance check → next decision

## API (8 core + 7 enterprise = 15 endpoints)
Core: offers, recompute, links, leaks, blockers, ranking, commissions, payouts
Enterprise: governance-rules, banned, approvals, risk-flags, partners, governance/recompute, partners/recompute
