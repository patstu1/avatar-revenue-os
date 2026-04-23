# Last-Mile Closure — Final Acceptance Fixes

Status: **Complete**

This document covers all fixes implemented in the last-mile closure pass to close every remaining issue from the final acceptance audit.

---

## 1. Affiliate Network Connector

### What Changed
- Built real API clients for **Impact**, **ShareASale**, and **CJ Affiliate** (`packages/clients/affiliate_network_clients.py`).
- Each client uses HTTPX async, environment-variable-based authentication, and returns structured `{success, data}` or `{success: false, error}` responses.
- Built `affiliate_sync_service.py` — auto-syncs conversion/commission data from configured network accounts.
- Added `POST /{brand_id}/affiliate-sync` endpoint to the affiliate intel router.
- Added env vars: `IMPACT_ACCOUNT_SID`, `IMPACT_AUTH_TOKEN`, `SHAREASALE_API_TOKEN`, `SHAREASALE_API_SECRET`, `SHAREASALE_MERCHANT_ID`, `CJ_API_KEY`.

### Behavior
- Sync iterates over all active `AffiliateNetworkAccount` records for a brand.
- Dispatches to the matching client based on `network_name`.
- Imports conversions/commissions into the existing `AffiliateConversionEvent` / `AffiliateCommissionEvent` tables.
- Updates network account status to `synced` or `sync_failed`.

### Truth Label
- `configured_missing_credentials` until network API keys are set.
- `live` once credentials are configured and sync succeeds.

---

## 2. Landing Page External Publishing

### What Changed
- Added `publish_page()` to `landing_page_service.py` with support for multiple publish methods: `manual`, `vercel`, `netlify`, `s3_static`.
- Added `POST /{brand_id}/landing-pages/{page_id}/publish` endpoint.
- Quality gate: publish is **blocked** if the most recent `LandingPageQualityReport` verdict is `fail`.
- Manual publish requires a `destination_url`.

### Truth-Label Transition
- `recommendation_only` → `published` on successful publish.
- `LandingPagePublishRecord` created with `published_url`, `publish_method`, and `truth_label = "published"`.
- Page model fields `publish_status`, `truth_label`, and `status` all flip to `published`.

---

## 3. Recovery Action Auto-Execution

### What Changed
- Added `execute_pending_recovery_actions()` to `recovery_engine_service.py`.
- The recovery worker (`scan_recovery`) now calls this after `recompute_recovery`.
- Auto-executes pending rollback, reroute, and throttle actions for incidents in `auto_recovering` status.

### Permission Enforcement
- Each action type checks the **permission matrix** via `check_action()` before execution.
- If the action class is `guarded` or `manual`, the action is set to `awaiting_approval` instead of executed.
- `RecoveryOutcome` records are created when all actions for an incident are processed.

---

## 4. Permission Matrix — Framework-Wide Enforcement

### What Changed
- Created `permission_enforcement.py` — the framework-level enforcement module.
- `enforce_permission(db, org_id, action_key)` raises `PermissionDenied` for `manual_only` and `guarded_approval` actions.
- `ACTION_MAP` maps worker-level action names to permission matrix action classes.

### Where Enforced
- **Publishing worker** (`auto_publish.py`): calls `enforce_permission(db, org_id, "auto_publish")` before creating Buffer jobs. If denied, the brand is skipped with `permission_denied` reason.
- **Recovery worker**: each recovery action checks permission before execution.
- Any downstream system can import and call `enforce_permission()` for real blocking.

### Behavior
- `fully_autonomous` / `autonomous_notify`: allowed (notification may be needed).
- `guarded_approval`: **blocked** — requires operator approval.
- `manual_only`: **blocked** — requires operator to execute manually.

---

## 5. Disclosure Auto-Injection

### What Changed
- Created `disclosure_injection_service.py` with platform-specific disclosure rules for YouTube, Instagram, TikTok, X, LinkedIn, and a default fallback.
- `inject_disclosure_into_content()` — pure function that inserts the correct disclosure text at the right position (description_top, caption_start, or text_end).
- `check_and_inject_disclosure()` — DB-backed function that checks content metadata for affiliate/sponsored flags and injects if needed.
- `validate_disclosure_present()` — checks if disclosure keywords are present in text.

### Where Enforced
- **Publishing worker** (`auto_publish.py`): calls `check_and_inject_disclosure(db, ci.id)` before building Buffer publish payloads.
- If content has affiliate links or is sponsored, disclosure is auto-injected before publish.
- If disclosure is already present, no duplicate injection occurs.

### Platform-Specific Rules
| Platform  | Affiliate Disclosure | Sponsored Disclosure | Placement |
|-----------|---------------------|---------------------|-----------|
| YouTube   | Full sentence + link | Sponsored by {name} | description_top |
| Instagram | #ad #affiliate | Paid partnership | caption_start |
| TikTok    | #ad #affiliate | #ad Sponsored by {name} | caption_start |
| X         | #ad | #ad Sponsored | text_end |
| LinkedIn  | Contains affiliate links. #ad | Sponsored content. #ad | text_end |

---

## 6. Buffer Credential Naming

### Status
Already unified on `BUFFER_API_KEY` across the entire repo:
- `.env.example`
- `external_clients.py`
- `buffer_distribution_service.py`
- `buffer_engine.py`
- `platform_registry_engine.py`
- `provider_registry_engine.py`
- `autonomous_readiness_engine.py`
- `auto_publish.py`
- All tests

Zero instances of `BUFFER_ACCESS_TOKEN` or `BUFFER_TOKEN` remain.

---

## Test Coverage

### Unit Tests (16/16 passed)
- Affiliate client credential blocking (Impact, ShareASale, CJ)
- Disclosure injection for YouTube, Instagram, TikTok, default platform
- Disclosure already-present detection
- Disclosure validation (present/missing)
- Permission enforcement action map
- PermissionDenied exception
- Buffer credential consistency
- Landing page publish adapters
- Operator permission defaults (rollback=autonomous, campaign=guarded, governance=manual)

### Integration Tests (15/15 passed)
- Affiliate sync with no networks / with network
- Landing page publish success / requires URL / blocked by quality / record created
- Recovery auto-execute with permission / skips non-auto-recovering
- Permission enforcement allows autonomous / blocks manual / blocks guarded / respects matrix override
- Disclosure injection DB-backed / content not found
- Buffer env var readiness
