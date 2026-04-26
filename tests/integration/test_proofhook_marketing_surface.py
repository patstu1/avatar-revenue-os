"""ProofHook public marketing surface — source-level structural tests.

The Next.js app under apps/web has no frontend test runner (no jest /
vitest / playwright in apps/web/package.json), so these tests verify the
wire contract by reading the page sources and shared lib.

Coverage:
  1. proofhook-packages.ts holds exactly the 7 universal package slugs
     and no niche-locked entries (universal-package rule).
  2. JSON-LD helpers cover every required schema type
     (Organization, WebSite, Service, Product/Offer, FAQPage,
     BreadcrumbList).
  3. Each of the 9 required marketing pages exists, references the
     correct path, includes JSON-LD, never uses banned claim language,
     and uses ProofHook's approved phrasing.
  4. robots.ts whitelists the required crawlers (Googlebot, Bingbot,
     OAI-SearchBot, GPTBot) and points at /sitemap.xml.
  5. sitemap.ts lists every required marketing path.

These are read-only reads of repo files; they do not start a Next.js
build, do not hit network, and do not touch the production site.
"""

from __future__ import annotations

import json
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(relpath: str) -> str:
    full = os.path.join(REPO_ROOT, relpath)
    assert os.path.isfile(full), f"missing file: {relpath}"
    return open(full).read()


# Banned claim language from the package brief — must never appear on the
# public marketing surface in a way that PROMISES the outcome. Single-word
# checks keep this loose so legitimate negation ("we will not promise
# guaranteed rankings") still passes.
BANNED_PROMISES = [
    # exact promise phrases — never legitimate on marketing copy outside
    # of explicitly disclaiming them. We assert each promise phrase appears
    # ONLY in a disclaimer context (followed/preceded by negation).
    "guaranteed rankings",
    "guaranteed AI recommendations",
    "guaranteed ChatGPT placement",
    "guaranteed Google AI Overview placement",
]

UNIVERSAL_PACKAGE_SLUGS = {
    "signal_entry",
    "momentum_engine",
    "conversion_architecture",
    "paid_media_engine",
    "launch_sequence",
    "creative_command",
    "ai_search_authority_sprint",
}

# Niche-locked package names that must NEVER appear as public-facing
# package identities (per the universal-package rule).
FORBIDDEN_NICHE_NAMES = [
    "Beauty Content Pack",
    "Fitness Content Pack",
    "AI Tool Review Pack",
    "Med Spa Content Pack",
    "SaaS Content Pack",
]

REQUIRED_PAGE_PATHS = {
    "/ai-search-authority": "apps/web/src/app/ai-search-authority/page.tsx",
    "/services/ai-search-authority": "apps/web/src/app/services/ai-search-authority/page.tsx",
    "/faq": "apps/web/src/app/faq/page.tsx",
    "/how-it-works": "apps/web/src/app/how-it-works/page.tsx",
    "/compare/proofhook-vs-content-agency": "apps/web/src/app/compare/proofhook-vs-content-agency/page.tsx",
    "/compare/proofhook-vs-ugc-platform": "apps/web/src/app/compare/proofhook-vs-ugc-platform/page.tsx",
    "/industries/ai-startups": "apps/web/src/app/industries/ai-startups/page.tsx",
    "/industries/saas": "apps/web/src/app/industries/saas/page.tsx",
    "/industries/ecommerce": "apps/web/src/app/industries/ecommerce/page.tsx",
}


# ─────────────────────────────────────────────────────────────────────
# 1. Package data — universal-package rule
# ─────────────────────────────────────────────────────────────────────


def test_proofhook_packages_module_has_only_universal_slugs():
    src = _read("apps/web/src/lib/proofhook-packages.ts")
    # Every required universal slug must appear in the package data
    for slug in UNIVERSAL_PACKAGE_SLUGS:
        assert f'slug: "{slug}"' in src, f"universal package slug missing: {slug}"
    # No forbidden niche-locked package names appearing as ACTUAL package
    # data entries. The rule's own documentation comment references these
    # names as examples of what NOT to do — that's allowed; only data
    # entries (`name: "..."`) are forbidden.
    for name in FORBIDDEN_NICHE_NAMES:
        assert f'name: "{name}"' not in src, (
            f"forbidden niche-locked package name found in PACKAGES data: {name}"
        )
    # The universal-package rule must be documented in-file so future edits
    # see the constraint
    assert "Universal-package rule" in src
    # The required metadata fields must be documented
    for field in ("package_slug", "package_name", "vertical", "buyer_type", "source", "fulfillment_type"):
        assert field in src, f"metadata field not documented: {field}"


def test_ai_search_authority_sprint_package_present():
    """The new package must be a universal entry — slug + name + price + timeline."""
    src = _read("apps/web/src/lib/proofhook-packages.ts")
    assert 'slug: "ai_search_authority_sprint"' in src
    assert 'name: "AI Search Authority Sprint"' in src
    assert "price: 4500" in src
    assert "priceFrom: true" in src
    assert '"10–14 days"' in src or "'10–14 days'" in src or "10–14 days" in src


# ─────────────────────────────────────────────────────────────────────
# 2. JSON-LD helpers — every required schema type
# ─────────────────────────────────────────────────────────────────────


def test_jsonld_helpers_cover_required_schema_types():
    src = _read("apps/web/src/components/jsonld.tsx")
    # Required schema types from the package brief
    for schema_type in [
        '"@type": "Organization"',
        '"@type": "WebSite"',
        '"@type": "Service"',
        '"@type": "Offer"',
        '"@type": "Product"',
        '"@type": "FAQPage"',
        '"@type": "BreadcrumbList"',
    ]:
        assert schema_type in src, f"JSON-LD helper missing schema type: {schema_type}"

    # Helper functions exist
    for fn in [
        "OrganizationJsonLd",
        "WebSiteJsonLd",
        "ServiceJsonLd",
        "PackageCatalogOffersJsonLd",
        "FaqJsonLd",
        "BreadcrumbJsonLd",
    ]:
        assert f"function {fn}" in src or f"export function {fn}" in src, (
            f"JSON-LD helper missing: {fn}"
        )


# ─────────────────────────────────────────────────────────────────────
# 3. Required pages — exist, are wired correctly, follow copy rules
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path,relpath", REQUIRED_PAGE_PATHS.items())
def test_required_page_exists(path: str, relpath: str):
    src = _read(relpath)
    assert "export default function" in src, f"page is not a default-exported component: {path}"


@pytest.mark.parametrize("path,relpath", REQUIRED_PAGE_PATHS.items())
def test_page_has_canonical_url(path: str, relpath: str):
    """Every page must declare its own URL in metadata (canonical) so
    duplicate-path concerns (e.g. /ai-search-authority and
    /services/ai-search-authority) don't dilute entity authority."""
    src = _read(relpath)
    # The /services/ai-search-authority redirect page is a special case —
    # it canonical-redirects to /ai-search-authority and has its canonical
    # set on /ai-search-authority itself.
    if path == "/services/ai-search-authority":
        assert "redirect(" in src and '"/ai-search-authority"' in src
        return
    assert "alternates" in src or "canonical" in src, (
        f"page missing canonical metadata: {path}"
    )


@pytest.mark.parametrize("path,relpath", REQUIRED_PAGE_PATHS.items())
def test_page_uses_jsonld_helpers(path: str, relpath: str):
    """Every public marketing page must emit at minimum Organization +
    WebSite JSON-LD so the entity graph is consistent across pages.
    Service/Offer/FAQPage/BreadcrumbList are added where appropriate."""
    if path == "/services/ai-search-authority":
        return  # redirect-only page; canonical lives on /ai-search-authority
    src = _read(relpath)
    assert "OrganizationJsonLd" in src, f"missing OrganizationJsonLd: {path}"
    assert "WebSiteJsonLd" in src, f"missing WebSiteJsonLd: {path}"


@pytest.mark.parametrize("path,relpath", REQUIRED_PAGE_PATHS.items())
def test_page_has_no_unhedged_claim_language(path: str, relpath: str):
    """The page text must not promise rankings, AI placements, or specific
    citations. Banned phrases are allowed only inside an explicit negation
    (e.g. "we will not promise guaranteed rankings")."""
    src = _read(relpath)
    lower = src.lower()
    for phrase in BANNED_PROMISES:
        plower = phrase.lower()
        if plower not in lower:
            continue
        # If it appears, it must be in a negation context. A simple,
        # robust check: the phrase appears within ~80 chars of "not",
        # "won't", "will not", "do not", "no.", "we will not promise", etc.
        idx = 0
        while True:
            idx = lower.find(plower, idx)
            if idx < 0:
                break
            window = lower[max(0, idx - 80) : idx + len(plower)]
            negations = [
                "not promise",
                "won't promise",
                "will not promise",
                "do not promise",
                "no promise",
                "not guaranteed",
                "no.",
                "no, ",
                "never",
                "we will not",
                "we don't",
                "we do not",
                "we won't",
                "no guarantee",
                "no offer",
                "without making promises",
                "not on offer",
            ]
            assert any(n in window for n in negations), (
                f"unhedged banned claim '{phrase}' on {path} — context: ...{window}..."
            )
            idx += len(plower)


def test_ai_search_authority_page_uses_approved_language():
    """The AI Search Authority page must use ProofHook's approved phrasing."""
    src = _read(REQUIRED_PAGE_PATHS["/ai-search-authority"])
    # Approved phrases — must appear at least once
    approved_any_present = [
        "improve machine readability",
        "strengthen entity authority",
        "increase eligibility",
        "easier for search engines and AI systems to understand",
    ]
    for phrase in approved_any_present:
        assert phrase.lower() in src.lower(), (
            f"AI search authority page missing approved phrase: {phrase}"
        )


def test_industry_pages_disclose_universal_packages():
    """Industry pages must explicitly state that ProofHook's packages are
    not locked to any vertical (universal-package rule)."""
    for path in [
        "/industries/ai-startups",
        "/industries/saas",
        "/industries/ecommerce",
    ]:
        src = _read(REQUIRED_PAGE_PATHS[path])
        assert "not locked to any vertical" in src, (
            f"industry page missing universal-package disclaimer: {path}"
        )


# ─────────────────────────────────────────────────────────────────────
# 4. robots.ts — required crawlers allowed, sitemap referenced
# ─────────────────────────────────────────────────────────────────────


def test_robots_allows_required_crawlers():
    src = _read("apps/web/src/app/robots.ts")
    for agent in ["Googlebot", "Bingbot", "OAI-SearchBot", "GPTBot"]:
        assert f'"{agent}"' in src, f"robots.ts must whitelist {agent}"
    # Sitemap reference for crawler discovery
    assert "sitemap" in src.lower() and "/sitemap.xml" in src
    # Operator-internal paths disallowed
    assert "/dashboard/" in src
    assert "/login" in src


# ─────────────────────────────────────────────────────────────────────
# 5. sitemap.ts — every required path included
# ─────────────────────────────────────────────────────────────────────


def test_sitemap_includes_every_required_path():
    src = _read("apps/web/src/app/sitemap.ts")
    for path in REQUIRED_PAGE_PATHS.keys():
        assert f'path: "{path}"' in src, f"sitemap.ts missing required path: {path}"
