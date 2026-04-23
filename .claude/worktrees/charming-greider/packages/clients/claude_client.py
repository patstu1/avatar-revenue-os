"""Claude (Anthropic) client for the Operator Copilot.

Generates grounded natural-language responses from structured system context.
Falls back to rule-based generation when API key is missing or call fails.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are the Operator Copilot for AI Avatar Revenue OS — an autonomous content monetization platform \
that runs content farms across multiple platforms and niches.

IDENTITY:
- You are growth-obsessed, system-protective, profit-first, direct, and grounded.
- You are an expert on content monetization, affiliate marketing, social media growth, and platform algorithms.
- You guide the operator through every step: initial setup, account creation, niche selection, affiliate signup, scaling decisions, and troubleshooting.
- Every claim you make must be backed by the SYSTEM CONTEXT provided below.

RULES — STRICT:
1. ONLY answer from the SYSTEM CONTEXT provided. Do NOT invent data, metrics, or counts.
2. If the context is insufficient to answer, say so explicitly. Do NOT fabricate.
3. Always label truth boundaries: [LIVE], [BLOCKED], [RECOMMENDATION], [PROXY], [QUEUED], [MISSING_CREDENTIALS].
4. When listing items, cite the source module (e.g. "from scale_alerts", "from provider_registry").
5. Be concise. Use bullet points. Bold key numbers and provider names.
6. When an operator action is needed, state it as a direct imperative with exact steps.
7. Prioritize: critical blockers first, then failures, then pending actions, then recommendations.
8. If asked about something outside the system, say "That is outside the system's persisted state."

SETUP GUIDE MODE — when the operator asks about setup, account creation, or getting started:
1. Use the NICHE RESEARCH DATA to recommend the highest-scoring niches.
2. Use the AFFILIATE PROGRAMS DATA to recommend which affiliate programs to sign up for, per niche.
3. Recommend specific platforms for each niche (the data shows platform scores).
4. Give EXACT step-by-step instructions: "Step 1: Create a TikTok account with username @finance_tips_2026. Step 2: Sign up for ClickBank at clickbank.com..."
5. Recommend the account warmup timeline: seed (3 days) → trickle (10 days) → build (15 days) → scale.
6. When recommending accounts, specify: platform, niche, suggested username format, posting cadence.
7. When recommending affiliates, specify: program name, signup URL, expected commission, best content types for that program.

SCALING MODE — when the operator asks about scaling or adding accounts:
1. Use FLEET STATUS to show current account distribution.
2. Use EXPANSION RECOMMENDATIONS to identify gaps.
3. Use NICHE SCORES to recommend the highest-opportunity expansion targets.
4. Be specific: "Add 2 TikTok accounts in AI tools niche. Expected revenue: $X/mo based on current fleet performance."

RESPONSE MODES — use exactly one per response:
- GROUNDED_ANSWER: answering from live persisted data
- INSUFFICIENT_CONTEXT: context does not contain the answer
- BLOCKED_BY_MISSING_CREDENTIALS: the relevant capability is blocked by a missing API key
- RECOMMENDATION_ONLY: suggestion based on rules/heuristics, not live telemetry
- SETUP_GUIDE: step-by-step setup instructions
- SCALING_RECOMMENDATION: data-backed scaling advice
- OPERATOR_ACTION_SUMMARY: listing pending operator actions
- EXTERNALLY_EXECUTED_SUMMARY: summarizing results of an external execution
"""


def _hash_context(ctx: dict[str, Any]) -> str:
    raw = json.dumps(ctx, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_context_block(
    quick_status: dict[str, Any],
    operator_actions: list[dict[str, Any]],
    missing_items: list[dict[str, Any]],
    provider_summary: list[dict[str, Any]],
) -> str:
    """Serialize grounded context into a text block for Claude's user message."""
    sections: list[str] = []

    sections.append("## QUICK STATUS")
    sections.append(json.dumps(quick_status, indent=2, default=str))

    if operator_actions:
        sections.append(f"\n## OPERATOR ACTIONS ({len(operator_actions)} total)")
        for a in operator_actions[:15]:
            sections.append(
                f"- [{a.get('urgency', '?').upper()}] {a.get('title', '?')} "
                f"(source: {a.get('source_module', '?')})"
            )
            if a.get("description"):
                sections.append(f"  Detail: {a['description'][:200]}")

    if missing_items:
        sections.append(f"\n## MISSING / INCOMPLETE ITEMS ({len(missing_items)} total)")
        for m in missing_items[:15]:
            sections.append(
                f"- **{m.get('item', '?')}** [{m.get('truth_level', '?')}]: "
                f"{m.get('description', '')[:200]}"
            )
            if m.get("action"):
                sections.append(f"  Action: {m['action']}")

    sections.append(f"\n## PROVIDER STACK ({len(provider_summary)} providers)")
    live = [p for p in provider_summary if p.get("effective_status") == "live"]
    blocked = [p for p in provider_summary if p.get("credential_status") == "not_configured" and p.get("env_keys")]
    primary = [p for p in provider_summary if p.get("is_primary")]

    sections.append(f"Live: {len(live)} | Blocked by credentials: {len(blocked)} | Primary: {len(primary)}")
    for p in provider_summary[:25]:
        role = "PRIMARY" if p.get("is_primary") else ("FALLBACK" if p.get("is_fallback") else "OPTIONAL")
        sections.append(
            f"- {p.get('display_name', '?')} ({p.get('category', '?')}) — "
            f"{role} — creds: {p.get('credential_status', '?')} — "
            f"status: {p.get('effective_status', p.get('integration_status', '?'))}"
        )

    return "\n".join(sections)


class ClaudeCopilotClient:
    """Real Anthropic Claude client for grounded copilot responses."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get(ANTHROPIC_API_KEY_ENV, "")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate_response(
        self,
        query: str,
        quick_status: dict[str, Any],
        operator_actions: list[dict[str, Any]],
        missing_items: list[dict[str, Any]],
        provider_summary: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate a grounded response via Claude.

        Returns:
            content: str
            generation_mode: "claude" | "fallback_rule_based"
            model: str
            confidence: float
            truth_boundaries: dict
            grounding_sources: list
            citations: list
            context_hash: str
            failure_reason: str | None
        """
        context_payload = {
            "quick_status": quick_status,
            "operator_actions": operator_actions[:15],
            "missing_items": missing_items[:15],
            "provider_summary": provider_summary,
        }
        context_hash = _hash_context(context_payload)
        context_block = _build_context_block(
            quick_status, operator_actions, missing_items, provider_summary,
        )

        if not self.is_configured():
            return {
                "content": None,
                "generation_mode": "fallback_rule_based",
                "model": "none",
                "confidence": 0.0,
                "truth_boundaries": {},
                "grounding_sources": [],
                "citations": [],
                "context_hash": context_hash,
                "failure_reason": "ANTHROPIC_API_KEY not configured",
            }

        user_message = (
            f"<system_context>\n{context_block}\n</system_context>\n\n"
            f"OPERATOR QUESTION: {query}"
        )

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            t0 = time.monotonic()

            response = await client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            content = response.content[0].text if response.content else ""

            logger.info(
                "claude.copilot_response",
                model=self.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                elapsed_ms=elapsed_ms,
            )

            response_mode = "GROUNDED_ANSWER"
            for mode in ("INSUFFICIENT_CONTEXT", "BLOCKED_BY_MISSING_CREDENTIALS",
                         "RECOMMENDATION_ONLY", "OPERATOR_ACTION_SUMMARY",
                         "EXTERNALLY_EXECUTED_SUMMARY"):
                if mode in content:
                    response_mode = mode
                    break

            return {
                "content": content,
                "generation_mode": "claude",
                "model": self.model,
                "confidence": 0.95,
                "truth_boundaries": {
                    "status": "live",
                    "source": "claude_grounded",
                    "response_mode": response_mode,
                },
                "grounding_sources": ["system_context"],
                "citations": [],
                "context_hash": context_hash,
                "failure_reason": None,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "elapsed_ms": elapsed_ms,
                },
            }

        except anthropic.AuthenticationError as exc:
            failure = f"Claude auth failure: {exc}"
            logger.warning("claude.auth_error", error=str(exc))
        except anthropic.RateLimitError as exc:
            failure = f"Claude rate limited: {exc}"
            logger.warning("claude.rate_limit", error=str(exc))
        except anthropic.APITimeoutError as exc:
            failure = f"Claude timeout: {exc}"
            logger.warning("claude.timeout", error=str(exc))
        except anthropic.APIError as exc:
            failure = f"Claude API error: {exc}"
            logger.error("claude.api_error", error=str(exc))
        except Exception as exc:
            failure = f"Claude unexpected error: {exc}"
            logger.exception("claude.unexpected_error")

        return {
            "content": None,
            "generation_mode": "fallback_rule_based",
            "model": self.model,
            "confidence": 0.0,
            "truth_boundaries": {},
            "grounding_sources": [],
            "citations": [],
            "context_hash": context_hash,
            "failure_reason": failure,
        }
