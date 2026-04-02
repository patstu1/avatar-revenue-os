# 74 — Enterprise Admin + Workflow Builder

## Purpose
Multi-stage approval and workflow control system for enterprise teams. Not a simple admin page — it supports configurable no-code workflows with role-based steps, rejection/rollback, escalation, and override.

## 9 Tables
wf_definitions, wf_steps, wf_assignments, wf_instances, wf_instance_steps, wf_approvals, wf_rejections, wf_overrides, wf_templates

## Workflow Types
content_generation, landing_page_publish, campaign_launch, affiliate_rollout, provider_change, risk_override, governance_exception

## Step Types
draft_review, compliance_review, brand_review, legal_review, publish_approval, escalation, auto_check

## Built-in Templates
- **content_publish**: Draft Review → Brand Review → Publish Approval
- **campaign_launch**: Campaign Review → Compliance Check → Launch Approval
- **risk_override**: Override Request → Legal Review → Final Approval (super_admin)

## Workflow Lifecycle
1. Create from template or custom definition
2. Start instance for any resource (content_item, campaign, landing_page)
3. Each step requires specific role action (approve/reject)
4. Approval advances to next step; rejection rolls back to step 1
5. Override by super_admin/org_admin skips to completion
6. Published content requires workflow completion

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Publishing worker | Blocks publish if workflow is in_progress |
| Copilot | Pending workflows shown in grounded context |
| Content generation | Workflow instances created for generated content |
| Campaign launch | Campaign workflows gate launch approval |

## API
workflows, workflow-instances, from-template, approve, reject, override

## Scoping
Workflows can be scoped to: org, brand, business_unit, market, language, client
