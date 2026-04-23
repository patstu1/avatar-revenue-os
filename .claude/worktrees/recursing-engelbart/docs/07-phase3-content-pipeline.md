# Phase 3: Content Pipeline, QA, Approval & Publishing

## Module Purpose

Phase 3 implements the full content production lifecycle: brief generation through script creation, media orchestration, quality assurance, approval workflow, and publish routing. Every AI output is schema-validated. Every approval action is audited.

## Content Lineage

```
TopicCandidate → ContentBrief → Script → MediaJob → ContentItem → QAReport → Approval → PublishJob
                      ↓              ↓                    ↓
                   Offer         ScriptVariant        SimilarityReport
```

Every content item preserves full traceability: which brief generated it, which script was used, which offer is attached, and which recommendation triggered it.

## Publish Score Formula (v1)

```
PublishScore =
  0.15 * HookStrength +
  0.15 * MonetizationFit +
  0.14 * Originality +
  0.14 * Compliance +
  0.10 * RetentionLikelihood +
  0.08 * CTAClarity +
  0.08 * BrandConsistency +
  0.06 * ThumbnailCTRPrediction +
  0.10 * ExpectedProfitScore
```

Blocking conditions (prevent publish regardless of score):
- Compliance < 0.5 → blocked
- Originality < 0.4 → blocked (force rewrite or guarded path)

## QA Logic

6 quality dimensions weighted to composite:
- 20% Originality, 20% Compliance
- 15% each: Brand alignment, Technical quality, Audio quality, Visual quality

Automated checks:
- `disclosures_present` — missing disclosures BLOCK publication
- `sponsor_metadata_present` — missing sponsor metadata BLOCKS sponsored content
- `originality_above_threshold` — below 0.4 forces REVIEW path
- `compliance_above_threshold` — below 0.5 triggers review

QA status routing:
- **PASS**: composite ≥ 0.6, no blockers
- **REVIEW**: low originality or composite 0.4-0.6
- **FAIL**: blocking issues present or composite < 0.4

## Approval Workflow

Three actions, all audited:
1. **Approve** → status = approved, creates Approval record
2. **Reject** → status = rejected, creates Approval record with notes
3. **Request Changes** → status = revision_requested, creates Approval record

Auto-approval routing (determines `decision_mode`):
- High confidence + QA ≥ 0.7 + no blockers → `full_auto` (auto-approved)
- Medium confidence + QA ≥ 0.5 → `guarded_auto` (human review recommended)
- Low confidence or blockers → `manual_override` (human required)

## Media Orchestration

Provider selection uses capability-based routing:
1. Check avatar's provider profiles for required capability
2. Sort by: primary first, then fallback, then cost
3. Skip unhealthy providers
4. Create MediaJob with selected provider
5. Track retries, errors, cost

### Provider Adapters

| Provider | Type | Status |
|----------|------|--------|
| Tavus | Async avatar video | Adapter built, needs API key |
| ElevenLabs | Voice synthesis | Adapter built, needs API key |
| OpenAI Realtime | Live voice | Adapter built, needs API key |
| HeyGen LiveAvatar | Live streaming | Adapter built, needs API key |
| Fallback | Template-based | Fully functional |

Each adapter implements:
- `submit_job(request)` → MediaResponse
- `check_status(provider_job_id)` → MediaResponse
- Request/response dataclass models
- Retry logic (max 3 retries)
- Error persistence (error_message, error_details)
- Cost tracking

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /pipeline/briefs?brand_id= | List briefs |
| GET | /pipeline/briefs/{id} | Get brief |
| PATCH | /pipeline/briefs/{id} | Update brief |
| POST | /pipeline/briefs/{id}/generate-scripts | Generate script from brief |
| GET | /pipeline/scripts?brand_id= | List scripts |
| GET | /pipeline/scripts/{id} | Get script |
| PATCH | /pipeline/scripts/{id} | Update script |
| POST | /pipeline/scripts/{id}/score | Score script for publish readiness |
| POST | /pipeline/scripts/{id}/generate-media | Create media generation job |
| GET | /pipeline/media-jobs?brand_id= | List media jobs |
| GET | /pipeline/media-jobs/{id} | Get media job |
| POST | /pipeline/content/{id}/run-qa | Run QA scoring |
| GET | /pipeline/qa/{id} | Get QA + similarity reports |
| POST | /pipeline/content/{id}/approve | Approve content |
| POST | /pipeline/content/{id}/reject | Reject content |
| POST | /pipeline/content/{id}/request-changes | Request changes |
| POST | /pipeline/content/{id}/schedule | Schedule publish |
| POST | /pipeline/content/{id}/publish-now | Immediate publish |
| GET | /pipeline/content/{id}/publish-status | Get publish jobs |
| GET | /pipeline/content/library?brand_id=&status= | Content library |
| GET | /pipeline/approvals/queue?brand_id= | Pending approvals |

## What Requires Live Credentials

| Feature | Provider | Env Var |
|---------|----------|---------|
| AI script generation | OpenAI | `OPENAI_API_KEY` |
| Voice synthesis | ElevenLabs | `ELEVENLABS_API_KEY` |
| Avatar video | Tavus | `TAVUS_API_KEY` |
| Live avatar | HeyGen | `HEYGEN_API_KEY` |
| Asset storage | S3 | `S3_*` |

Without credentials: template-based script generation works, fallback media provider works, all QA/approval/publish logic works fully.
