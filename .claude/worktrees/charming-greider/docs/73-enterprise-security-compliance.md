# 73 — Enterprise Security + Compliance OS

## Purpose
Real enterprise security/control layer with RBAC, audit trails, data isolation, compliance frameworks, and risk governance. Does not claim certification — builds control surfaces and evidence trails.

## 10 Tables
es_roles, es_permissions, es_user_groups, es_access_scopes, es_audit_trail, es_sensitive_data_policies, es_model_isolation, es_compliance_controls, es_risk_overrides

## RBAC (8 system roles)
super_admin (100), org_admin (90), brand_admin (80), approver (60), publisher (55), analyst (50), generator (40), viewer (10) + custom roles

## Action Permissions
| Action | Min Level | Authorized Roles |
|--------|-----------|-----------------|
| generate | 40 | super_admin, org_admin, brand_admin, generator |
| approve | 60 | super_admin, org_admin, brand_admin, approver |
| publish | 55 | super_admin, org_admin, brand_admin, publisher |
| admin | 80 | super_admin, org_admin, brand_admin |
| delete | 90 | super_admin, org_admin |
| override_risk | 90 | super_admin, org_admin |
| view | 10 | all roles |

## Scope Types
org, business_unit, client, brand, market, language, campaign, action

## Compliance Frameworks
- **GDPR**: data minimization, right to erasure, consent, processing records, cross-border
- **SOC 2**: logical access, provisioning, change management, monitoring, classification
- **HIPAA**: access control, audit controls, integrity, transmission security

## Sensitive Data Controls
data_class (public/internal/confidential/restricted/pii/financial/health), private_mode, model_restriction, training_leak_prevention, masking_rules

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Compliance gaps + risk overrides in grounded context |
| Generation | Permission check before content generation |
| Publishing | Permission check before publish |
| Provider usage | Model isolation policies enforce dedicated/private mode |

## API (9 endpoints)
roles, seed-roles, audit-trail, data-policies, compliance, compliance/recompute, model-isolation, risk-overrides

## Worker
`recompute_compliance` — daily at 5am
