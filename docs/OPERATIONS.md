# Operations — final-lock manual

This document is the single source of operating truth for the Avatar
Revenue OS once the system reaches final lock (Batch 6). It supersedes
any other runbook.

## 1. Canonical branch

- **`recovery/from-prod`** is the canonical production branch. All
  production deploys roll from this ref.
- `main` is a historical reference only. Do not merge `main` into
  `recovery/from-prod` or vice versa without explicit approval.
- Salvage branches (`salvage/*`) are read-only archives.

### Branch protection (to configure in the GitHub UI)

On `recovery/from-prod`:

- [x] Require pull request reviews before merging (1 reviewer).
- [x] Require status checks to pass before merging
      (`pytest`, `py_compile`).
- [x] Require conversation resolution before merging.
- [x] Do not allow force pushes.
- [x] Do not allow branch deletion.
- [x] Restrict who can push to matching branches: `patstu` +
      automation users only.
- [ ] Require signed commits: optional.

### Freeze rules

- **Freeze rule A — single canonical branch.** New code lands on
  `recovery/from-prod` only, via PR. No direct pushes from workstations
  in freeze windows.
- **Freeze rule B — proof-before-merge.** Every PR MUST include
  runtime proof (integration tests that exercise the new path against
  real Postgres).
- **Freeze rule C — no schema changes without a migration.** Every
  new / modified SQLAlchemy model MUST ship with a matching
  `packages/db/alembic/versions/NNN_*.py` migration that is safe to
  re-run (`IF NOT EXISTS` guarded).
- **Freeze rule D — no env-first credentials.** All business config
  (API keys, webhook secrets, inbound routing) is stored in
  `integration_providers`. Env vars are legacy fallbacks only and MUST
  emit `*.env_legacy_fallback` warning logs when used.
- **Freeze rule E — no deploy without health-check.** Every deploy
  MUST pass `/ops/health-check` with `healthy=true` before traffic is
  cut over.

## 2. Canonical deploy path

### Prerequisites (checked once, at provisioning)

1. Postgres 15 reachable at `DATABASE_URL` + `DATABASE_URL_SYNC`.
2. Redis reachable at `REDIS_URL` (for Celery).
3. `FERNET_KEYS` environment variable populated (secret encryption).
4. `API_SECRET_KEY` env var set to a 32+ char random value.
5. `STRIPE_WEBHOOK_SECRET` and `SHOPIFY_WEBHOOK_SECRET` configured via
   the operator UI (`/api/v1/operator/settings/providers`).
6. At least one `inbound_email_route` provider row configured via
   `/api/v1/operator/settings/inbound-route`.

### Deploy procedure

1. **Pre-flight (local)**
   ```bash
   cd ~/Developer/ai-avatar-recovery
   git fetch origin
   git log origin/recovery/from-prod..HEAD --oneline    # must be empty
   python3 -m pytest tests/integration/ -q              # must be green
   ```
2. **Build + push image** (CI pipeline owns this).
3. **Run migrations against prod DB**
   ```bash
   DATABASE_URL_SYNC=... alembic upgrade head
   ```
4. **Deploy stack**
   ```bash
   scripts/deploy.sh   # sets DEPLOY_MANIFEST_* envs, rolls containers
   ```
5. **Verify lock + health** before cutting traffic:
   ```bash
   curl https://<api>/ops/version        # sha matches intended deploy
   curl https://<api>/ops/lock-status    # matches_canonical=true
   curl https://<api>/ops/health-check   # healthy=true
   ```
6. **Smoke-test** the money path (see §4).

### DEPLOY_MANIFEST_* env vars

The deploy pipeline MUST set these at container start so
`/ops/lock-status` can verify the running binary:

| Var | Value |
|---|---|
| `DEPLOY_MANIFEST_SHA` | Git SHA of the deployed commit |
| `DEPLOY_MANIFEST_BRANCH` | `recovery/from-prod` |
| `DEPLOY_MANIFEST_AT` | ISO-8601 timestamp of the build |
| `DEPLOY_MANIFEST_BY` | User / CI identifier that triggered the deploy |
| `DEPLOY_MANIFEST_BUILD_ID` | CI build/job id |

## 3. Health checklist

`GET /ops/health-check` is the production "is the system alive" probe.
It runs these checks:

| Check | Hard-fail? | Detail |
|---|---|---|
| `db_reachable` | **yes** | `SELECT NOW()` round-trips |
| `alembic_version_matches_code` | **yes** | `alembic_version.version_num` equals latest migration file revision |
| `critical_providers_configured` | **yes** | Every org with any provider rows has `stripe_webhook`, `inbound_email_route`, `smtp` enabled |
| `event_flow_recent` | no | Informational: SystemEvent count in last 60 minutes |
| `no_hard_stuck_stages` | **yes** | No `stage_states` with SLA past > 1 hour |
| `no_unacknowledged_error_escalations` | **yes** | No `gm_escalations` with status=open + severity=error |

Any hard-fail makes the overall `healthy` flag false. Load balancers
should treat `healthy=false` as degraded.

## 4. Smoke test (post-deploy)

1. **Inbound → classification:** POST a fake SendGrid inbound payload
   to `/api/v1/webhooks/inbound-email` with a matching inbound_route.
   Verify a new `email_reply_drafts` row appears.
2. **Draft → send:** Approve the draft via `/api/v1/operator/pending-drafts`;
   verify `status=sent` within 90 seconds.
3. **Proposal → payment:** POST a proposal, generate a payment link,
   replay a `checkout.session.completed` via `stripe trigger`. Verify
   `payments` row with `status=succeeded` + Proposal.status=paid.
4. **Client → intake → project:** Submit the intake form at
   `/api/v1/intake/{token}`. Verify `clients`, `intake_submissions`,
   `client_projects`, `project_briefs`, `production_jobs` rows.
5. **QA → delivery:** POST output to the job; verify auto-QA pass →
   Delivery row with followup_scheduled_at set.

## 5. Rollback procedure

### When to roll back

- `/ops/health-check` returns `healthy=false` after deploy.
- Five minutes post-deploy, any `qa.failed` event with
  `terminal=true` rate > 1/min (mass production failure).
- A Stripe webhook signature-verification failure rate above
  baseline.
- Operator decision.

### How to roll back

**Path A — fast revert (binary rollback, no schema change needed):**
```bash
scripts/rollback.sh <previous-sha>
# scripts/rollback.sh sets DEPLOY_MANIFEST_* back to the prior SHA
# and rolls the container image back. Alembic head stays on the
# most-recent revision (additive-only migrations are forward-safe).
```

**Path B — schema rollback** (only if absolutely necessary):
```bash
DATABASE_URL_SYNC=... alembic downgrade <previous-rev>
scripts/rollback.sh <previous-sha>
```

Data loss note: every migration from 010 onward is additive, so Path B
does NOT drop customer data. Dropping tables from 014_gm_control,
013_qa_delivery, 012_fulfillment, 011_clients_intake, or
010_proposals_payments **does** drop operator workflow state. Prefer
Path A unless the schema itself is the problem.

### Post-rollback

1. Hit `/ops/lock-status` — verify `deployed_sha` is the previous SHA.
2. Hit `/ops/health-check` — must be green.
3. Open a GMEscalation noting the rollback and the triggering failure.
4. Do not re-deploy until the root cause has a landed fix.

## 6. No more hidden off-system operating truth

The canonical operating surface is:

- **Config**: `integration_providers` table, read/write via
  `/api/v1/operator/settings/providers`.
- **Inbound routing**: `integration_providers` rows with
  `provider_key='inbound_email_route'`.
- **Webhook secrets**: same table, `provider_key='*_webhook'`.
- **Operator credentials**: `users` table, read/write via
  `/api/v1/operator/team`.
- **State of the revenue loop**: `clients`, `proposals`, `payments`,
  `client_projects`, `intake_requests`, `production_jobs`,
  `deliveries`.
- **Stage SLAs**: `stage_states` — written by the stage controller,
  scanned by the stuck-stage watcher.
- **Operator queue**: `gm_approvals` + `gm_escalations`.
- **Event ledger**: `system_events` — every canonical state transition
  emits one row here.

Any state that is NOT in one of the above tables is NOT operating
truth. Do not add new off-system spreadsheets, Notion boards, private
CLI scripts that read env vars, or `.env.*` files carrying business
config.

## 7. Canonical event taxonomy

All domain events go through `apps.api.services.event_bus.emit_event`
and land in `system_events` with `event_type` drawn from this
canonical list:

**monetization**
- `reply.draft.approved` / `.rejected` / `.sent` / `.send_failed`
- `proposal.created` / `.sent`
- `payment.link.created`
- `payment.completed`

**fulfillment**
- `client.created`
- `onboarding.started`
- `intake.sent` / `.completed`
- `project.created`
- `brief.created`
- `production.started`
- `qa.passed` / `.failed`
- `delivery.sent`
- `followup.scheduled`

**gm**
- `gm.approval.requested` / `.approved` / `.rejected`
- `gm.escalation.opened` / `.resolved`

Any service that introduces a new event type MUST document it here
before merge.
