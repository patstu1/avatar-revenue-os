# Operator Copilot

## Overview
The Operator Copilot is a grounded conversational interface powered by **Claude (Anthropic)** as the primary reasoning/generation layer. Every response is grounded in persisted system state — no hallucination. When Claude is unavailable, the copilot falls back to a rule-based structured response generator.

## Generation Architecture
- **Primary**: Claude (Anthropic) via `packages/clients/claude_client.py` — generates natural-language responses from structured system context
- **Fallback**: Rule-based engine (`packages/scoring/copilot_engine.py`) — used when `ANTHROPIC_API_KEY` is missing, or Claude fails (timeout, rate limit, auth error)
- **Credential**: `ANTHROPIC_API_KEY` environment variable. When absent, copilot still works via fallback.
- **Model**: `claude-sonnet-4-20250514` (configurable)

## Grounding Enforcement
Claude receives a strict system prompt that forbids free invention:
1. ONLY answer from SYSTEM CONTEXT provided
2. If context is insufficient, say so explicitly
3. Always label truth boundaries: [LIVE], [BLOCKED], [RECOMMENDATION], [PROXY], [QUEUED], [MISSING_CREDENTIALS]
4. Cite source modules for every claim

## Response Modes
- `GROUNDED_ANSWER` — answering from live persisted data
- `INSUFFICIENT_CONTEXT` — context does not contain the answer
- `BLOCKED_BY_MISSING_CREDENTIALS` — capability blocked by missing API key
- `RECOMMENDATION_ONLY` — suggestion based on rules/heuristics
- `OPERATOR_ACTION_SUMMARY` — listing pending operator actions
- `EXTERNALLY_EXECUTED_SUMMARY` — summarizing external execution results

## Fallback Behavior
When Claude is unavailable (missing key, auth error, timeout, rate limit, malformed response):
1. Failure reason is persisted in `copilot_chat_messages.failure_reason`
2. `generation_mode` is set to `fallback_rule_based`
3. Rule-based engine generates the response
4. `truth_boundaries.generation_fallback = true` is set
5. Chat request never fails silently

## Persistence / Auditability
Each assistant message records:
- `generation_mode`: `claude` or `fallback_rule_based`
- `generation_model`: model name or `rule_engine`
- `context_hash`: SHA-256 hash of the grounding payload
- `failure_reason`: why fallback occurred (null if Claude succeeded)
- `truth_boundaries`: applied truth labels
- `grounding_sources`: which data sources were queried
- `confidence`: 0.95 for Claude, 0.7 for fallback

## Data Persistence
- Chat sessions persisted in copilot_chat_sessions
- Messages persisted in copilot_chat_messages with generation tracking
- Response citations tracked in copilot_response_citations
- Action summaries aggregated in copilot_action_summaries
- Issue summaries aggregated in copilot_issue_summaries

## Data Sources (grounded retrieval)
The copilot reads from:
- operator_alerts (scale alerts)
- growth_commands (growth commander)
- creator_revenue_blockers
- messaging_blockers (CRM/email/SMS)
- buffer_blockers
- provider_blockers (provider registry)
- execution_blocker_escalations (autonomous execution)
- provider_registry (all 23 providers)
- All 232 system tables (via aggregate queries)

## Truth Boundary Rules
Every response includes a truth_boundaries field:
- **live**: data from persisted rows queried in real-time
- **synthetic**: data from heuristic scoring engines
- **proxy**: data estimated from indirect signals
- **queued**: action is queued but not yet executed
- **blocked**: action is blocked by missing credentials/config
- **recommendation_only**: suggestion based on rules, not live data
- **configured_missing_credentials**: code exists but credentials aren't set
- **architecturally_present**: module exists but SDK not yet wired

## Operator Behavior
The copilot personality is:
- Growth-obsessed — prioritizes revenue and scaling
- System-protective — flags risks and blockers proactively
- Profit-first — recommendations optimize for profit margin
- Direct — no ambiguity, no hedging
- Grounded — every claim backed by persisted state
- Intolerant of stale blockers — pushes operator to resolve

## Quick Prompts
| Prompt | What it queries |
|--------|----------------|
| What needs me right now? | Aggregated blockers + failures + pending actions |
| What is blocked? | All blocker sources across system |
| What failed today? | Recent failure rows |
| What should launch next? | Growth commands awaiting approval |
| What should be killed? | Kill ledger entries |
| What credentials are missing? | Provider registry credential check |
| What changed in 24 hours? | Audit logs + system jobs |
| What is still not fully built? | Provider integration status audit |
| Which providers are active? | Live providers from registry |
| Which providers need credentials? | Unconfigured providers |
| Provider roles? | Provider-to-capability mapping |

## Primary Model
Claude (Anthropic) is the designated primary reasoning model. Currently the copilot uses rule-based structured response generation. When ANTHROPIC_API_KEY is set, the copilot will pass structured system context to Claude for natural language generation.

## API Endpoints
- GET /brands/{id}/copilot/sessions
- POST /brands/{id}/copilot/sessions
- GET /copilot/sessions/{id}/messages
- POST /copilot/sessions/{id}/messages
- GET /brands/{id}/copilot/quick-status
- GET /brands/{id}/copilot/operator-actions
- GET /brands/{id}/copilot/missing-items
- GET /brands/{id}/copilot/providers
- GET /brands/{id}/copilot/provider-readiness

## Migration
Revision: copilot_001 (down_revision: provider_reg_001)
