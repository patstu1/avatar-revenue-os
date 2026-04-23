# 83 — Operator Permission Matrix

## Purpose
Explicitly governs autonomy levels by action class. Not generic RBAC — defines whether each action is fully autonomous, notify-only, requires approval, or is manual-only.

## 5 Tables
opm_matrix, opm_action_policies, opm_approval_requirements, opm_override_rules, opm_execution_modes

## 15 Action Classes

| Action | Default Mode | Approval Role | Override Role |
|--------|-------------|---------------|---------------|
| content_generation | fully_autonomous | — | brand_admin |
| content_publish | autonomous_notify | brand_admin | org_admin |
| campaign_launch | guarded_approval | brand_admin | org_admin |
| campaign_suppress | autonomous_notify | — | brand_admin |
| scaling_output | autonomous_notify | — | brand_admin |
| launch_account | guarded_approval | org_admin | super_admin |
| offer_switch | autonomous_notify | — | brand_admin |
| affiliate_offer_switch | autonomous_notify | — | brand_admin |
| email_send | guarded_approval | brand_admin | org_admin |
| sms_send | guarded_approval | brand_admin | org_admin |
| landing_page_publish | guarded_approval | brand_admin | org_admin |
| budget_escalation | guarded_approval | org_admin | super_admin |
| provider_config_change | manual_only | org_admin | super_admin |
| rollback_action | fully_autonomous | — | org_admin |
| governance_override | manual_only | super_admin | super_admin |

## 4 Autonomy Modes
- **fully_autonomous** — machine acts without any human involvement
- **autonomous_notify** — machine acts and notifies operator
- **guarded_approval** — machine proposes, operator approves before execution
- **manual_only** — operator must execute directly

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Autonomy summary (actions by mode) in grounded context |
| Gatekeeper | Permission check before autonomous actions |
| Publishing | Publish mode checked before content goes live |
| Campaigns | Campaign launch mode checked before activation |
| Scaling | Output scaling mode checked before volume changes |
| Workflows | Workflow steps respect permission matrix modes |

## API (5 endpoints)
matrix, seed, check/{action_class}, override/{action_class}, execution-modes
