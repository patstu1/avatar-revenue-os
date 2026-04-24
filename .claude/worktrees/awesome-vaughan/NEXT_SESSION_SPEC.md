# NEXT SESSION IMPLEMENTATION SPEC

## Current State
- Commit: `cd1baa2` on `main`
- All services healthy (API, Postgres, Redis, Worker, Scheduler, Web, Caddy)
- Integration control plane backend LANDED (DB models + service + API)
- Tables NOT yet created in running DB (need `ensure_schema.py` or rebuild)

## What Is Built (backend foundation)

### `packages/db/models/integration_registry.py`
- `IntegrationProvider` — 26 columns, encrypted credential storage, health tracking, tier routing
- `CreatorPlatformAccount` — 22 columns, platform connections, roles, warmup state

### `apps/api/services/integration_manager.py`
- `seed_provider_catalog()` — populates 24 default providers
- `set_credential()` — encrypts API key before DB storage
- `get_credential()` — decrypts at runtime
- `list_providers()` — returns providers with masked credentials
- `get_provider_for_task()` — tier-aware routing (hero/standard/bulk with fallback)

### `apps/api/routers/integrations_dashboard.py`
- `POST /integrations/seed` — seed provider catalog
- `GET /integrations/providers` — list all with status
- `POST /integrations/providers/{key}/credential` — set encrypted credential
- `GET /integrations/route` — get best provider for task
- `POST /integrations/providers/{key}/enable|disable` — toggle

### Provider Catalog (24 providers)
```
LLM:        claude (hero), gemini_flash (standard), deepseek (bulk), groq (bulk)
Image:      openai_image (hero), imagen4 (standard), flux (standard)
Video:      kling (standard), runway (hero)
Avatar:     heygen (hero), did (standard)
Voice:      elevenlabs (hero), fish_audio (standard), voxtral (bulk)
Publishing: buffer, publer, ayrshare
Analytics:  youtube_analytics, tiktok_analytics, instagram_analytics
Trends:     serpapi
Email:      smtp
Inbox:      imap
Payment:    stripe
```

---

## What Must Be Built Next Session

### 1. Wire integration_manager into content pipeline
**Files to modify:**
- `apps/api/services/content_pipeline_service.py` — replace `_try_ai_generation()` to call `get_provider_for_task(db, org_id, "llm", quality_tier)` instead of reading env vars directly
- `apps/api/services/content_generation_service.py` — same: use integration_manager for API key lookup
- `workers/generation_worker/tasks.py` — use integration_manager for media provider selection
- `workers/publishing_worker/tasks.py` — use integration_manager for publishing provider selection
- `packages/clients/analytics_clients.py` — use integration_manager for analytics credentials

### 2. Build frontend integrations page
**File:** `apps/web/src/app/dashboard/integrations/page.tsx` (replace current basic page)

**UI must show:**
- Provider grid grouped by category (LLM, Image, Video, Avatar, Voice, Publishing, Analytics, Email, Payment)
- Each provider card: name, status badge (configured/unconfigured/healthy/down), enable/disable toggle
- Click provider → modal: enter API key (masked input), test connection button, save
- Provider priority drag-and-drop or number input
- Quality tier selector per provider

**API client:** `apps/web/src/lib/integrations-api.ts`
```typescript
export const integrationsApi = {
  seed: () => api.post('/api/v1/integrations/seed'),
  list: (category?: string) => api.get('/api/v1/integrations/providers', { params: { category } }),
  setCredential: (key: string, apiKey: string) => api.post(`/api/v1/integrations/providers/${key}/credential`, null, { params: { api_key: apiKey } }),
  enable: (key: string) => api.post(`/api/v1/integrations/providers/${key}/enable`),
  disable: (key: string) => api.post(`/api/v1/integrations/providers/${key}/disable`),
  route: (category: string, tier: string) => api.get('/api/v1/integrations/route', { params: { category, quality_tier: tier } }),
};
```

### 3. Build creator accounts management page
**File:** `apps/web/src/app/dashboard/accounts/page.tsx` (enhance existing)

**UI must show:**
- List of all creator platform accounts
- Add account: platform selector, username, brand assignment, niche, archetype
- Connection status badge
- Connect via Buffer/Publer flow
- Warmup state selector
- Monetization role selector
- Pause/resume/scale controls

### 4. Provider health testing
**Add to `integration_manager.py`:**
```python
async def test_provider_health(db, org_id, provider_key):
    """Actually call the provider API to verify connectivity."""
    # Get decrypted credential
    # Make a minimal API call (e.g., list models for LLM, whoami for publishing)
    # Update health_status + last_health_check + avg_latency_ms
```

### 5. Credential encryption upgrade
Current: XOR with hashed API_SECRET_KEY (simple, functional)
Target: Replace with `cryptography.fernet.Fernet` for production-grade encryption
Add `cryptography` to requirements.txt

### 6. Auto-migration from .env to DB
On first boot after upgrade:
- Read existing .env credentials
- If integration_providers table is empty, auto-seed + auto-migrate credentials from env vars
- This ensures zero-downtime migration from env-first to DB-first

### 7. OAuth connection flows
For platforms that support OAuth (YouTube, TikTok, Instagram via Buffer):
- Add OAuth redirect endpoints
- Store tokens in IntegrationProvider.oauth_token_encrypted
- Implement token refresh logic

---

## Routing Architecture (how providers are selected)

```
Content generation request arrives
  ↓
classify_task_tier(platform, content_type) → "hero" | "standard" | "bulk"
  ↓
get_provider_for_task(db, org_id, "llm", tier) → best configured provider
  ↓
get_credential(db, org_id, provider_key) → decrypted API key
  ↓
call provider API with the key
  ↓
update provider.total_calls, total_cost_usd, last_successful_call
```

Same pattern for image, video, avatar, voice, publishing.

## Tables to create on next deploy
```sql
-- Run ensure_schema.py or:
-- integration_providers (26 columns)
-- creator_platform_accounts (22 columns)
```

## Non-negotiable rules for next session
1. Do NOT revert to .env-first credential loading
2. All provider selection MUST go through integration_manager.get_provider_for_task()
3. All credential access MUST go through integration_manager.get_credential()
4. Frontend MUST show real provider status, not hardcoded lists
5. Encryption MUST be upgraded to Fernet before any production credentials are stored
