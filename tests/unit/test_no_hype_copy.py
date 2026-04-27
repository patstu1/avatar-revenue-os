"""Lock-in test: no hype/overclaim phrases in any of the AI Buyer Trust
component or page sources.

Greps the rendered Next.js component sources + the Python orchestrator's
public envelope strings + the engine's user-visible copy. Fails if any
banned phrase appears.

This is a string-only test — runs under the existing Python pytest harness
without requiring a JS test runner.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Files that render to the public-facing surface for the AI Buyer Trust Test.
TARGET_FILES = [
    "apps/web/src/app/page.tsx",
    "apps/web/src/app/ai-search-authority/page.tsx",
    "apps/web/src/app/ai-search-authority/score/page.tsx",
    "apps/web/src/app/ai-search-authority/snapshot/page.tsx",
    "apps/web/src/components/ai-buyer-trust/Test.tsx",
    "apps/web/src/components/ai-buyer-trust/ScoreResultCard.tsx",
    "apps/web/src/components/ai-buyer-trust/EvidenceList.tsx",
    "apps/web/src/components/ai-buyer-trust/DecisionLayerSections.tsx",
    "apps/web/src/components/ai-buyer-trust/HomepageTestCTA.tsx",
    "apps/api/services/ai_buyer_trust_service.py",
    "packages/scoring/ai_buyer_trust_engine.py",
    "apps/web/src/lib/proofhook-packages.ts",
]

# Phrases the operator forbids — overclaim, hype, fake-quiz language.
# Match is substring + lowercase (case-insensitive). We intentionally leave
# wiggle room for accurate sentences that *deny* the phrase (e.g. the FAQ
# answer "We do not promise guaranteed rankings"). Therefore any line that
# contains the banned phrase AND a denial token is treated as compliant.
BANNED = (
    "guaranteed rankings",
    "guaranteed citations",
    "guaranteed ai placement",
    "guaranteed ai recommendations",
    "guaranteed chatgpt",
    "guaranteed google ai overview",
    "rank in chatgpt",
    "dominate ai",
    "exploit ai search",
    "secret hack",
    "10x overnight",
    "ai will choose you",
    "instant authority",
    "hack the algorithm",
    "get found instantly",
    "get listed in ai",
)

# Tokens that mean a sentence is denying the banned phrase rather than
# making the claim.
DENIAL_TOKENS = (
    "no ranking",
    "no ai-placement",
    "no guaranteed",
    "do not promise",
    "not promise",
    "without making",
    "we don't sell",
    "we do not promise",
    "no promise",
    "not guarantee",
    "do not guarantee",
    "never claim",
    "copy rules",
    "never promise",
    "we don't promise",
)


def _line_is_denial(line: str) -> bool:
    lower = line.lower()
    return any(d in lower for d in DENIAL_TOKENS)


def _line_is_comment(line: str) -> bool:
    """Return True if the line is a source-code comment / docstring rather
    than rendered copy. Doctrine prohibition lines like "Copy rules: never
    claim guaranteed rankings" live in comments and are correct, not
    user-visible.
    """
    stripped = line.strip()
    if not stripped:
        return True
    # Python — line comments and bare docstring continuation lines
    if stripped.startswith("#"):
        return True
    # Python triple-quoted docstring boundary or content lines that begin
    # with a doc indicator. We can't perfectly track docstring state without
    # a real parser, so we use a conservative substring heuristic:
    if stripped.startswith('"""') or stripped.endswith('"""') or stripped.startswith("'''"):
        return True
    # TypeScript / JS — single-line and block-comment markers
    if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
        return True
    return False


def test_no_hype_phrases_in_public_surfaces():
    findings: list[tuple[str, int, str, str]] = []
    for rel in TARGET_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _line_is_comment(raw):
                continue
            lower = raw.lower()
            for phrase in BANNED:
                if phrase in lower and not _line_is_denial(raw):
                    findings.append((rel, i, phrase, raw.strip()))
    assert not findings, "Banned hype phrases detected:\n" + "\n".join(
        f"  {rel}:{i}: {phrase!r}\n    > {line}" for rel, i, phrase, line in findings
    )


# Lock the visual palette: forbid any electric-blue / amber / navy class
# in the AI Buyer Trust components and pages so they stay zinc-only with
# the existing ProofHook aesthetic.
PALETTE_BANNED = (
    "amber-",
    "blue-",  # electric blue and any blue
    "indigo-",
    "sky-",
    "cyan-",
    "navy",
    "yellow-",
    "orange-",
    "violet-",
    "purple-",
    "fuchsia-",
    "pink-",
    "lime-",
    "teal-",
    "rose-",
    "emerald-",
    "green-",
    "red-",
)


# Negative-positioning phrases — defensive copy ProofHook public surfaces
# should not use. Doctrine: lead with what ProofHook does, not what it
# refuses to promise.
NEGATIVE_POSITIONING = (
    "we do not promise",
    "we don't promise",
    "we will not promise",
    "we cannot promise",
    "we do not guarantee",
    "we don't guarantee",
    "we cannot guarantee",
    "we do not sell",
    "we don't sell",
    "no ranking guarantees",
    "no ai-placement promises",
    "no ai placement promises",
    "no guaranteed",
    "without making promises",
    "we are not",
    "we aren't",
    "we will not",
)


def test_affirmative_positioning_only_in_public_surfaces():
    """Public-facing copy must lead with what ProofHook does, not with
    'we do not / we don't / we are not' style defensive disclaimers."""
    findings: list[tuple[str, int, str, str]] = []
    for rel in TARGET_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _line_is_comment(raw):
                continue
            lower = raw.lower()
            for phrase in NEGATIVE_POSITIONING:
                if phrase in lower:
                    findings.append((rel, i, phrase, raw.strip()))
    assert not findings, "Negative-positioning phrases detected:\n" + "\n".join(
        f"  {rel}:{i}: {phrase!r}\n    > {line}" for rel, i, phrase, line in findings
    )


def test_snapshot_page_renders_required_elements():
    """Static markup check for /ai-search-authority/snapshot — proves the
    page exists, has both CTAs, the report_id-aware copy, and the
    affirmative 'Free with email' framing without rendering JS."""
    path = REPO_ROOT / "apps/web/src/app/ai-search-authority/snapshot/page.tsx"
    assert path.exists(), "Snapshot page must exist"
    src = path.read_text(encoding="utf-8")

    # MarketingShell reused, not a new shell
    assert 'MarketingShell' in src
    assert 'pageId="ai-search-authority-snapshot"' in src

    # Both report_id branches present
    assert 'Your AI Buyer Trust result is ready for review' in src
    assert 'Full Authority Snapshot' in src

    # Both CTAs present
    assert 'Take the AI Buyer Trust Test' in src
    assert 'Request Snapshot Review' in src
    assert '/ai-search-authority/score' in src

    # Affirmative launch-pricing framing
    assert 'free with email' in src.lower() or 'Free with email' in src

    # Wires to the snapshot review API + handles the requested success state
    assert 'requestSnapshotReview' in src
    assert 'snapshot-requested' in src


def test_dashboard_renders_recommended_lanes_block():
    """Static markup check for the operator dashboard detail drawer —
    proves the AI Authority lane + Creative Proof companion blocks
    render, with the right testids."""
    path = REPO_ROOT / "apps/web/src/app/dashboard/ai-search-authority/page.tsx"
    assert path.exists()
    src = path.read_text(encoding="utf-8")
    assert 'RecommendedLanesBlock' in src
    assert 'AI Authority lane' in src
    assert 'Creative Proof companion' in src
    assert 'data-testid="recommended-lanes"' in src
    assert 'data-testid="lane-ai-authority"' in src
    assert 'data-testid="lane-creative-proof"' in src


def test_homepage_renders_commercial_sections():
    """Locks the homepage commercial structure: 5-second comprehension
    hero, how-it-works, buyer psychology, what-proofhook-builds, result
    to package, dual-lane package grid with whoItsFor + CTA per card,
    after-the-test, and the full commercial flow ladder."""
    path = REPO_ROOT / "apps/web/src/app/page.tsx"
    src = path.read_text(encoding="utf-8")

    # Hero clarity
    assert 'data-testid="home-hero"' in src
    assert 'Take the free AI Buyer Trust Test' in src
    assert 'Authority Snapshot is free with email' in src

    # All commercial sections imported and rendered
    for section in (
        'HowItWorksSection',
        'BuyerPsychologySection',
        'WhatProofHookBuildsSection',
        'ResultToPackageSection',
        'AfterTheTestSection',
        'CommercialFlowSection',
    ):
        assert section in src, f"homepage must import + render {section}"

    # Dual-lane package grid + per-package CTA
    assert 'data-testid="home-ai-authority-section"' in src
    assert 'data-testid="home-creative-section"' in src
    # Each package card surfaces whoItsFor copy + price/timeline + CTA
    assert "Who it" in src and "for" in src  # "Who it's for"
    assert 'packagePriceDisplay(pkg)' in src


def test_decision_layer_exports_all_commercial_sections():
    """The shared section module must expose the new commercial sections
    so both the homepage and the /ai-search-authority page reuse them."""
    path = REPO_ROOT / "apps/web/src/components/ai-buyer-trust/DecisionLayerSections.tsx"
    src = path.read_text(encoding="utf-8")
    for fn in (
        'export function HowItWorksSection',
        'export function AfterTheTestSection',
        'export function BuyerPsychologySection',
        'export function WhatProofHookBuildsSection',
        'export function ResultToPackageSection',
        'export function CommercialFlowSection',
    ):
        assert fn in src, f"DecisionLayerSections.tsx must export {fn}"

    # Result-to-package mapping table renders score bands
    assert 'data-testid="result-to-package-table"' in src
    assert 'Score band' in src
    assert 'Recommended build' in src

    # Commercial flow ladder mentions every commercial stage
    assert 'data-testid="commercial-flow"' in src
    for stage in (
        'Take the test',
        'Receive Authority Score',
        'Request reviewed Snapshot',
        'Operator-recommended package',
        'Written proposal',
        'Build + fulfillment',
        'Authority monitoring',
    ):
        assert stage in src, f"CommercialFlowSection must list {stage!r}"


def test_ai_search_authority_page_includes_result_to_package_and_flow():
    """The /ai-search-authority page must surface the result-to-package
    mapping, the after-the-test stages, and the full commercial flow."""
    path = REPO_ROOT / "apps/web/src/app/ai-search-authority/page.tsx"
    src = path.read_text(encoding="utf-8")
    assert 'ResultToPackageSection' in src
    assert 'AfterTheTestSection' in src
    assert 'CommercialFlowSection' in src
    assert 'data-testid="ai-authority-packages"' in src


def test_snapshot_page_renders_request_flow_and_package_ladder():
    """The /ai-search-authority/snapshot page must show the four-step
    request flow, the package ladder it leads into, and connect every
    state back to the AI Authority lane."""
    path = REPO_ROOT / "apps/web/src/app/ai-search-authority/snapshot/page.tsx"
    src = path.read_text(encoding="utf-8")
    assert 'data-testid="snapshot-request-flow"' in src
    assert 'data-testid="snapshot-package-ladder"' in src
    assert 'Operator review' in src
    assert 'Snapshot delivery' in src


def test_score_result_card_surfaces_full_package_recommendation():
    """The result card must render the recommended package with price,
    timeline, whoItsFor language, and a Talk-to-ProofHook CTA paired
    with the Snapshot CTA."""
    path = REPO_ROOT / "apps/web/src/components/ai-buyer-trust/ScoreResultCard.tsx"
    src = path.read_text(encoding="utf-8")
    assert 'data-testid="recommended-next-step"' in src
    assert 'data-testid="recommended-primary-pkg"' in src
    assert 'packagePriceDisplay(' in src
    assert 'Talk to ProofHook' in src
    assert 'Who it' in src and "for" in src  # "Who it's for"


def test_packages_have_whoitsfor_and_lane_fields():
    """Every package in the canonical catalog must declare whoItsFor +
    lane so cards across the site render consistently."""
    path = REPO_ROOT / "apps/web/src/lib/proofhook-packages.ts"
    src = path.read_text(encoding="utf-8")

    # Type contract carries the new fields
    assert 'whoItsFor: string' in src
    assert 'lane: ProofHookLane' in src
    assert 'export type ProofHookLane' in src

    # Buyer-facing creative names locked in (slugs are unchanged for
    # Stripe metadata compatibility, only display names rotated).
    for buyer_name in (
        'UGC Starter Pack',
        'Proof Video Pack',
        'Hook Pack',
        'Paid Social Creative Pack',
        'Founder Clip Pack',
        'Creative Retainer',
    ):
        assert buyer_name in src, f"creative package must use buyer-facing name {buyer_name!r}"

    # Every slug must have at least one whoItsFor + lane assignment
    slugs = (
        'signal_entry',
        'momentum_engine',
        'conversion_architecture',
        'paid_media_engine',
        'launch_sequence',
        'creative_command',
        'ai_search_authority_snapshot',
        'ai_search_authority_sprint',
        'proof_infrastructure_buildout',
        'authority_monitoring_retainer',
        'ai_search_authority_system',
    )
    for slug in slugs:
        assert f'slug: "{slug}"' in src, f"package {slug} missing"

    # Both lanes must be referenced
    assert 'lane: "ai_authority"' in src
    assert 'lane: "creative_proof"' in src


def test_homepage_test_form_includes_honeypot():
    """The Test.tsx form must include the honeypot input field so bots
    that auto-complete by name fill it and get rejected by the backend."""
    path = REPO_ROOT / "apps/web/src/components/ai-buyer-trust/Test.tsx"
    src = path.read_text(encoding="utf-8")
    assert 'bot_field' in src, "Test.tsx must wire the honeypot field"
    assert 'tabIndex={-1}' in src, "Honeypot must be tab-skipped"
    assert 'autoComplete="off"' in src, "Honeypot must be autocomplete-off"
    assert 'left: "-10000px"' in src, "Honeypot must be visually hidden"


def test_visual_palette_is_zinc_only_in_new_surfaces():
    findings: list[tuple[str, int, str, str]] = []
    for rel in TARGET_FILES:
        path = REPO_ROOT / rel
        if not path.exists() or not rel.endswith(".tsx"):
            continue
        for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _line_is_comment(raw):
                continue
            lower = raw.lower()
            for token in PALETTE_BANNED:
                # Avoid false positives like 'red ' or comments — match a
                # tailwind class form: token + digits OR token at word edge
                # in a className-like position.
                if (
                    f' {token}' in lower
                    or f'"{token}' in lower
                    or f"'{token}" in lower
                    or f' {token}' in lower
                ):
                    findings.append((rel, i, token, raw.strip()))
    assert not findings, "Non-zinc Tailwind colors detected:\n" + "\n".join(
        f"  {rel}:{i}: {token!r}\n    > {line}" for rel, i, token, line in findings
    )
