# Buffer Distribution Layer

## Overview

Buffer is the **primary social distribution layer** for AI Avatar Revenue OS. All social publishing flows through Buffer rather than direct platform-native API calls. This provides a single integration point for multi-platform publishing while keeping platform/account targeting logic inside our system.

## Architecture

```
Content Item / Distribution Plan
         ↓
  [Buffer Publish Job]  ← created by recompute or worker
         ↓
  [Target Buffer Profile]  ← maps to a Buffer-connected social account
         ↓
  [Submit to Buffer API]  ← hands off payload to Buffer
         ↓
  [Buffer handles scheduling/publishing]
         ↓
  [Status Sync pulls back results]  ← queued → scheduled → published / failed
```

## Tables

| Table | Purpose |
|---|---|
| `buffer_profiles` | Maps creator accounts to Buffer-connected profiles/channels per platform |
| `buffer_publish_jobs` | Individual publish handoffs to Buffer with status lifecycle |
| `buffer_publish_attempts` | Tracks each API call attempt for auditing and retry tracking |
| `buffer_status_syncs` | Records of periodic status sync operations |
| `buffer_blockers` | Issues preventing distribution with operator action instructions |

## Buffer Profile Management

Each Buffer profile represents one social account connected through Buffer:

- **brand linkage** — which brand owns this profile
- **creator account linkage** — which of our creator accounts maps to this profile
- **platform** — tiktok, instagram, youtube, twitter, reddit, linkedin, facebook
- **external Buffer profile ID** — the ID used in Buffer's API
- **credential status** — connected, not_connected, expired, revoked
- **sync status** — synced, stale, error, never

## Publish Job Lifecycle

1. **pending** — job created, not yet submitted to Buffer
2. **submitted** — sent to Buffer API, awaiting Buffer processing
3. **queued** — Buffer has queued the post
4. **scheduled** — Buffer has scheduled the post for a specific time
5. **published** — Buffer confirms the post went live
6. **failed** — Buffer or our system reports a failure
7. **cancelled** — job was cancelled before publishing

## Failure Handling

When a publish job cannot be submitted:

1. The `BufferPublishAttempt` records the failure with error details
2. The job status is set to `failed` with the error message
3. A `BufferBlocker` is created with:
   - The blocker type (missing API key, expired token, etc.)
   - The severity (critical, high, medium, low)
   - A clear description of the issue
   - An exact operator action needed to resolve it
4. The operator sees the blocker on the Buffer Blockers Dashboard

No publish failure is silent. Every failure is persisted and escalated.

## Status Sync

The status sync worker periodically polls Buffer's API to update job statuses:

- Checks all submitted/queued/scheduled jobs
- Maps Buffer's status strings to our normalized statuses
- Persists sync run records for auditing
- Updates published timestamps when posts go live

Without a Buffer API key, sync simulates transitions for development.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/buffer-profiles` | List all Buffer profiles for a brand |
| POST | `/brands/{id}/buffer-profiles` | Create a new Buffer profile |
| PATCH | `/buffer-profiles/{id}` | Update a Buffer profile |
| GET | `/brands/{id}/buffer-publish-jobs` | List all publish jobs for a brand |
| POST | `/brands/{id}/buffer-publish-jobs/recompute` | Scan for content and create publish jobs |
| POST | `/buffer-publish-jobs/{id}/submit` | Submit a single job to Buffer |
| POST | `/brands/{id}/buffer-status-sync/recompute` | Pull latest statuses from Buffer |

POST recompute endpoints are rate-limited via `recompute_rate_limit`.

## Workers

| Task | Schedule | Description |
|---|---|---|
| `submit_pending_jobs` | Every 15 minutes | Submits all pending publish jobs to Buffer |
| `sync_buffer_statuses` | Every 30 minutes | Pulls back statuses for submitted/queued/scheduled jobs |

Both workers process all active brands, handling each independently.

## Dashboards

1. **Buffer Profiles** — Create, view, and manage Buffer-connected social accounts
2. **Buffer Publish Queue** — View all publish jobs with status, scan for new content, submit to Buffer
3. **Buffer Status** — Trigger status syncs and view results
4. **Buffer Blockers** — View unresolved issues preventing distribution

## Truth Boundary

### What Buffer covers:
- Multi-platform social post scheduling and publishing
- Post queue management
- Basic analytics (via Buffer's own dashboard)

### What remains outside Buffer:
- **Platform-native API features** — Stories, Reels, DMs, live streams, thread replies
- **Direct API publishing** — All social posts go through Buffer, not direct platform APIs
- **Real-time engagement** — Comment management, inbox, community features
- **Advanced platform analytics** — Detailed per-post metrics require platform-native integrations
- **Content creation** — Buffer receives finished content; it does not generate content

### Credential requirement:
- `BUFFER_API_KEY` must be set in environment configuration
- Each Buffer profile must be connected via Buffer's dashboard
- The system honestly reports when credentials are missing via blockers and escalations

## Data Provenance

- **Profiles with `credential_status: connected`** — Ready for real Buffer API calls
- **Profiles with `credential_status: not_connected`** — Blocked; jobs created but cannot submit
- **Jobs with status `submitted` (no API key)** — Simulated submission for development
- **Sync results without API key** — Status transitions are simulated

When `BUFFER_API_KEY` is configured and profiles are connected, the system makes real Buffer API calls and all statuses reflect actual Buffer state.

## Integration with Other Modules

- **Distribution Plans** (Autonomous Phase B) — Create Buffer publish jobs from approved distribution plans
- **Content Runner** (Autonomous Phase B) — Buffer is the publish target for the content runner
- **Blocker Detection** (Autonomous Phase D) — Missing Buffer credentials are detected as blockers
- **Brain Escalation** (Brain Phase D) — Missing credentials generate operator escalations
- **Readiness Brain** (Brain Phase D) — Buffer connectivity contributes to platform readiness scoring
