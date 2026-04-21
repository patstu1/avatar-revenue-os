# Avatar Revenue OS — Production Lock

Locked at: 2026-04-21T02:11:12Z
Operator: root @ 5.78.187.31

## Canonical release

- Branch: recovery/from-prod
- SHA:    fdec48b3780045da5a51fafde8eeb3e211065af3
- Path:   /opt/avatar-revenue-os

## Deploy summary

- Pre-deploy backup: /var/backups/aro/20260421T011030Z/pre-fdec48b.dump (3.9G)
- Schema sync: ensure_schema.py -> create_all produced 479 tables (was 462)
- Alembic head: 014_gm_control (single, after multi-head cleanup)
- All 14 containers healthy (api, caddy, postgres, redis, scheduler, web,
  worker-analytics, worker-buffer-meta, worker-default, worker-generation,
  worker-outreach, worker-publishing, worker-qa-cinema, worker-revenue-ceilings)

## Ops snapshots

### /ops/version
{"canonical_branch":"recovery/from-prod","git_head":"unknown","alembic_head_revision":"014_gm_control","python":"3.11.15","generated_at":"2026-04-21T02:11:12.231762+00:00"}

### /ops/health-check
{"healthy":true,"canonical_branch":"recovery/from-prod","generated_at":"2026-04-21T02:11:12.109601+00:00","checks":[{"name":"db_reachable","ok":true,"detail":"2026-04-21 02:11:12.093804+00:"},{"name":"alembic_version_matches_code","ok":true,"detail":"db=014_gm_control code=014_gm_control"},{"name":"critical_providers_configured","ok":true,"detail":"1 orgs checked"},{"name":"event_flow_recent","ok":true,"detail":"868 events in last 60m"},{"name":"no_hard_stuck_stages","ok":true,"detail":[]},{"name":"no_unacknowledged_error_escalations","ok":true,"detail":"0 open error escalations"}]}

## Live proof results — 4 pillars, all PASS

Executed 2026-04-21 on real prod (org TestCorp / eb0fd0c0-03dd-40a9-9cb7-795e50aa8705).

### H.1 Intake
- POST /api/v1/leads -> lead_opportunities row id=cf535f03-dc40-4955-b4ad-1fd771c05eb0
- GET /api/v1/leads/stats -> 119 total leads
- Operator pages render: /operator/, /operator/pipeline (all 8 sections),
  /operator/settings/inbound-route

### H.2 Conversion
Full chain inbound->draft->proposal->payment->client->intake:
  InboxConnection:   dba9f84f-0224-46a5-ac74-f69f21b336a7 (auto-provisioned)
  EmailThread:       22d298c8-7dd4-4ad2-9412-a5107ee2acb5
  EmailMessage:      8f43d932-4253-48c8-8014-7b8871b0b388
  EmailClassification: e58ceed5-3e1b-44d8-b501-067a92130a70 (intent=warm_interest)
  EmailReplyDraft:   1be81988-2521-4283-a641-02c783688b13 (auto_send, approved by policy)
  Proposal:          c04c04d2-414c-4804-a43d-32f85dddd973 (status=paid, 150000 cents)
  PaymentLink:       3cf50d36-469a-4fdb-a34d-689565bf4e4b (status=completed)
  Payment:           c5224e8d-503d-431d-9382-4b5faa8c095c (status=succeeded)
  Client:            95c66510-91f1-44e5-997f-324d886e0e84 (is_new=True)
  IntakeRequest:     c1414bb1-2b28-4e53-a12a-bb98937ffb94 (status=sent)
Events: proposal.created, proposal.sent, payment.link.created,
  payment.completed, client.created, onboarding.started, intake.sent (all fired).

### H.3 Fulfillment
Intake-submit cascade to delivery:
  IntakeSubmission:  107a662a-8e62-4c33-ac61-8e4c4cdff121 (is_complete=True)
  ClientProject:     1aa09eb8-bc1a-410b-9333-19758685f9b7 (status=completed)
  ProjectBrief v1:   9fc72cf7-453a-4507-bea0-ba2481fa6317 (status=approved)
  ProductionJob:     6a587fd5-9cab-49a5-ba86-dcbfa40908d5 (status=completed)
  ProductionQAReview: 1 row, result=passed, score=0.85
  Delivery:          status=sent, followup_scheduled_at=2026-04-28
Events: intake.completed, project.created, brief.created, production.started,
  qa.passed, delivery.sent, followup.scheduled (all fired).

### H.4 GM control
  GMApproval:   d9690bfc (pending->approved, decided_by=admin@testcorp.com)
  GMEscalation: f12f5f40 (opened), 9eeaa486 (opened by watcher), all resolved
  StageState watcher: checked=2, stuck=2, escalations_opened=2
Events: gm.approval.requested, gm.approval.approved, gm.escalation.opened (x3),
  gm.escalation.resolved (all fired).

## Integration providers (system-owned)

28 rows enabled for TestCorp org. Batch 3A-6 additions:
- stripe_webhook       (migrated from STRIPE_WEBHOOK_SECRET env on 20260421)
- inbound_email_route  (migrated from PROOFHOOK_INBOUND_ORG_ID env on 20260421,
                        extra_config.to_address=reply@reply.proofhook.com)

## Post-lock follow-up items (non-blocking)

1. Caddy config: /ops/* is routed to Next.js frontend instead of API.
   Works directly via docker exec but not via https://app.nvironments.com/ops/*.
   One-line Caddyfile addition needed.
2. DEPLOY_MANIFEST_* env vars exported in shell but not persisted to .env on
   this deploy, so /ops/lock-status.deployed_sha is currently empty.
   One-time .env append after operator decides retention.
3. deploy.sh line 5: bug "no such service: worker" (should enumerate
   worker-default, worker-outreach, etc). Worked around by docker compose up -d.
4. Canonical requirements.lock removed on prod (was stale, missing stripe).
   Needs regeneration: docker exec aro-api pip freeze > requirements.lock
   and committed back.
5. Stripe dashboard webhook URL + SendGrid Inbound Parse URL:
   operator should verify these still point at app.nvironments.com.
6. Remove now-redundant env vars after confirming DB-first paths hit in logs:
   STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET, PROOFHOOK_INBOUND_ORG_ID, SMTP_*,
   IMAP_*, OPS_TOKEN.

## Canonical operator entry points

- Operator home:          https://app.nvironments.com/api/v1/operator/
- Pipeline dashboard:     https://app.nvironments.com/api/v1/operator/pipeline
- Pending drafts:         https://app.nvironments.com/api/v1/operator/pending-drafts
- Provider settings:      https://app.nvironments.com/api/v1/operator/settings/providers
- Inbound route:          https://app.nvironments.com/api/v1/operator/settings/inbound-route
- Webhooks log:           https://app.nvironments.com/api/v1/operator/webhooks
- Team / invites:         https://app.nvironments.com/api/v1/operator/team
- GM control board:       https://app.nvironments.com/api/v1/operator/gm

## Canonical deploy + rollback

Deploy:   cd /opt/avatar-revenue-os && git pull --ff-only origin recovery/from-prod && ./deploy.sh
Rollback: cd /opt/avatar-revenue-os && scripts/rollback.sh <prior-sha>

