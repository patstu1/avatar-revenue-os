# Database Schema — Phase 1 Tables

## Phase 1 Active Tables (11 core)

### organizations
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | VARCHAR(255) | |
| slug | VARCHAR(255) | UNIQUE, INDEXED |
| plan | VARCHAR(50) | free/pro/enterprise |
| is_active | BOOLEAN | |
| settings | JSONB | Org-level configuration |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### users
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | INDEXED |
| email | VARCHAR(255) | UNIQUE, INDEXED |
| hashed_password | VARCHAR(255) | bcrypt |
| full_name | VARCHAR(255) | |
| role | ENUM(admin,operator,viewer) | |
| is_active | BOOLEAN | |
| last_login_at | TIMESTAMPTZ | nullable |

### brands
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | INDEXED |
| name | VARCHAR(255) | |
| slug | VARCHAR(255) | INDEXED |
| description | TEXT | |
| niche / sub_niche | VARCHAR(255) | |
| target_audience | TEXT | |
| tone_of_voice | TEXT | |
| brand_guidelines | JSONB | |
| decision_mode | VARCHAR(50) | full_auto/guarded_auto/manual_override |
| is_active | BOOLEAN | |

### avatars
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| brand_id | UUID FK → brands | INDEXED |
| name | VARCHAR(255) | |
| persona_description | TEXT | Canonical identity |
| voice_style | VARCHAR(255) | |
| visual_style | VARCHAR(255) | |
| default_language | VARCHAR(10) | |
| personality_traits | JSONB | |
| speaking_patterns | JSONB | |
| visual_reference_urls | JSONB | |
| is_active | BOOLEAN | |

### avatar_provider_profiles
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| avatar_id | UUID FK → avatars | INDEXED |
| provider | VARCHAR(50) | tavus/heygen/fallback |
| provider_avatar_id | VARCHAR(255) | External ID |
| provider_config | JSONB | Provider-specific settings |
| capabilities | JSONB | What this provider can do |
| is_primary | BOOLEAN | Primary provider flag |
| is_fallback | BOOLEAN | Fallback provider flag |
| health_status | ENUM | healthy/warning/degraded/critical/suspended |
| last_health_check_at | TIMESTAMPTZ | |
| cost_per_minute | FLOAT | |

### voice_provider_profiles
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| avatar_id | UUID FK → avatars | INDEXED |
| provider | VARCHAR(50) | elevenlabs/openai_realtime/heygen/fallback |
| provider_voice_id | VARCHAR(255) | External ID |
| provider_config | JSONB | |
| capabilities | JSONB | |
| is_primary | BOOLEAN | |
| is_fallback | BOOLEAN | |
| health_status | ENUM | |
| cost_per_minute | FLOAT | |

### offers
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| brand_id | UUID FK → brands | INDEXED |
| name | VARCHAR(255) | |
| monetization_method | ENUM | affiliate/adsense/sponsor/product/course/membership/consulting/lead_gen |
| payout_amount | FLOAT | |
| epc | FLOAT | Earnings per click |
| conversion_rate | FLOAT | |
| average_order_value | FLOAT | |
| priority | INTEGER | |

### creator_accounts
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| brand_id | UUID FK → brands | INDEXED |
| avatar_id | UUID FK → avatars | nullable |
| platform | ENUM | youtube/tiktok/instagram/etc |
| account_type | ENUM | organic/paid/hybrid |
| platform_username | VARCHAR(255) | |
| All metric fields | FLOAT | revenue, profit, CTR, RPM, etc |
| All health fields | FLOAT | fatigue, saturation, drift scores |
| account_health | ENUM | healthy/warning/degraded/critical/suspended |

### audit_logs
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK | INDEXED |
| brand_id | UUID FK | nullable, INDEXED |
| user_id | UUID | nullable, INDEXED |
| actor_type | VARCHAR(50) | system/human |
| action | VARCHAR(255) | INDEXED |
| entity_type | VARCHAR(100) | INDEXED |
| entity_id | UUID | |
| details | JSONB | |

### system_jobs
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| brand_id | UUID FK | nullable |
| job_name | VARCHAR(255) | INDEXED |
| job_type | VARCHAR(100) | |
| queue | VARCHAR(100) | |
| status | ENUM | pending/queued/running/completed/failed/cancelled/retrying |
| celery_task_id | VARCHAR(255) | |
| error_message | TEXT | |
| retries / max_retries | INTEGER | |

### provider_usage_costs
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| brand_id | UUID FK | nullable |
| provider | VARCHAR(100) | INDEXED |
| provider_type | VARCHAR(50) | avatar/voice/llm/image/video |
| operation | VARCHAR(255) | |
| input_units / output_units | INTEGER | |
| cost | FLOAT | |
| currency | VARCHAR(3) | USD |

## Additional Tables (pre-created for future phases)

52 additional tables exist in the schema for phases 2-4 (content pipeline, scoring, decisions, publishing, analytics, experiments, learning, portfolio). These are migrated but not yet wired with service logic.
