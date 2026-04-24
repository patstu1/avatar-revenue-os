# Provider Identity Architecture — AI Avatar Revenue OS

## Canonical Identity Model

Each avatar has a **single canonical identity** stored in the `avatars` table:
- Persona description
- Voice style
- Visual style
- Personality traits (JSONB)
- Speaking patterns (JSONB)

This canonical identity is **provider-agnostic**. Provider-specific configurations live in separate profile tables.

## Avatar Providers

### Supported Providers

| Provider | Role | Type | Use Case |
|----------|------|------|----------|
| **Tavus** | Primary | Async | Pre-rendered avatar video generation (lip-sync, custom backgrounds) |
| **HeyGen LiveAvatar** | Secondary | Live | Real-time avatar streaming for interactive use cases |
| **Fallback** | Fallback | Template | Static/template-based content when premium providers are unavailable |

### avatar_provider_profiles Table

Each avatar can have multiple provider profiles. The system selects the appropriate provider based on:
1. **Capability matching** — Does the provider support the required feature?
2. **Primary designation** — Prefer the primary provider
3. **Health status** — Skip unhealthy providers
4. **Fallback chain** — Fall back to designated fallback providers
5. **Cost optimization** — Consider cost_per_minute when multiple providers qualify

Fields:
- `provider` — tavus, heygen, fallback
- `provider_avatar_id` — External ID in the provider's system
- `provider_config` — Provider-specific configuration (JSONB)
- `capabilities` — What this provider can do (JSONB)
- `is_primary` / `is_fallback` — Designation flags
- `health_status` — healthy/warning/degraded/critical/suspended
- `cost_per_minute` — For cost tracking

## Voice Providers

### Supported Providers

| Provider | Role | Type | Use Case |
|----------|------|------|----------|
| **ElevenLabs** | Primary | Rendered | Premium text-to-speech, voice cloning, multi-language |
| **OpenAI Realtime** | Secondary | Live | Real-time conversational voice with function calling |
| **HeyGen** | Integrated | Live | Voice within live avatar sessions |
| **Fallback** | Fallback | Basic | Basic TTS when premium providers unavailable |

### voice_provider_profiles Table

Same structure as avatar providers:
- `provider` — elevenlabs, openai_realtime, heygen, fallback
- `provider_voice_id` — External voice ID
- `capabilities` — voice_cloning, streaming, realtime_conversation, languages, etc.
- Failover and health tracking fields

## Provider Failover Logic

```
1. Determine required capability (e.g., async_video, voice_cloning)
2. Filter profiles for this avatar that have the capability
3. Sort by: is_primary DESC, health_status ASC, cost_per_minute ASC
4. Select first healthy provider
5. If none healthy, check fallback providers
6. Log failover decision to audit_logs
7. Track usage to provider_usage_costs
```

## What Requires Live Credentials

| Provider | Env Var | Required For |
|----------|---------|-------------|
| Tavus | `TAVUS_API_KEY` | Video generation API calls |
| ElevenLabs | `ELEVENLABS_API_KEY` | Voice synthesis API calls |
| OpenAI | `OPENAI_API_KEY` | Script generation, realtime voice |
| HeyGen | `HEYGEN_API_KEY` | Live avatar streaming |

The provider profile CRUD, capability routing, health tracking, and cost logging all work without live credentials. Only actual API calls to external providers require keys.
