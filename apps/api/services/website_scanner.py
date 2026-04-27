"""Public-website scanner for the AI Buyer Trust Test.

Fetches the homepage + a small fixed list of common high-signal subpages
(robots, sitemap, about, services, faq, pricing, case studies, etc.),
parses each with BeautifulSoup, and returns a structured `ScanResult`
that the deterministic scoring engine consumes.

Constraints:
- 30 s connect/read timeout on httpx
- 60 s wall-clock budget across the whole scan
- 1 MB max body per response (stream and discard the rest)
- Fixed user agent identifying ProofHook so site owners can recognize
  the scanner in their access logs
- No JS rendering. We score what's in the HTML the server returns.
- Failures are recorded — they do not raise. The scoring engine treats
  unfetched pages as ``not_assessed``.

Stateless. No DB access.
"""

from __future__ import annotations

import asyncio
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()

USER_AGENT = "ProofHookAuthorityScanner/1.0 (+https://proofhook.com/ai-search-authority)"

_FETCH_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_TOTAL_BUDGET_SECONDS = 60.0
_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB
_MAX_PAGES = 10

# Common high-signal paths we attempt in addition to the homepage.
_CANDIDATE_PATHS = (
    "/about",
    "/about-us",
    "/services",
    "/products",
    "/pricing",
    "/faq",
    "/faqs",
    "/case-studies",
    "/case-study",
    "/testimonials",
    "/proof",
    "/contact",
    "/why-choose-us",
    "/comparison",
    "/compare",
    "/alternatives",
)

# Internal-link patterns that suggest a high-signal page worth fetching.
_LINK_HINT_RE = (
    "about",
    "services",
    "pricing",
    "faq",
    "case",
    "testimonial",
    "proof",
    "vs",
    "compare",
    "alternative",
)


@dataclass
class FetchedPage:
    url: str
    status_code: int | None = None
    title: str | None = None
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    meta_description: str | None = None
    jsonld_blocks: list[dict] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    body_text_snippet: str = ""
    fetch_error: str | None = None
    content_type: str | None = None
    fetched_at_seconds: float = 0.0


@dataclass
class ScanResult:
    """Aggregate signals collected across all fetched pages."""

    homepage_url: str
    pages: list[FetchedPage] = field(default_factory=list)
    robots_txt_present: bool = False
    robots_txt_blocks_ai: bool = False
    sitemap_present: bool = False
    sitemap_url_count: int = 0
    fetch_started_at: float = 0.0
    fetch_completed_at: float = 0.0
    homepage_failed: bool = False

    @property
    def homepage(self) -> FetchedPage | None:
        return next((p for p in self.pages if p.url == self.homepage_url), None)

    def find_path(self, *path_substrings: str) -> FetchedPage | None:
        for p in self.pages:
            path = urlparse(p.url).path.lower()
            for sub in path_substrings:
                if sub in path:
                    return p
        return None

    def all_jsonld(self) -> list[dict]:
        out: list[dict] = []
        for p in self.pages:
            out.extend(p.jsonld_blocks)
        return out

    def jsonld_types(self) -> set[str]:
        out: set[str] = set()
        for block in self.all_jsonld():
            out.update(_extract_jsonld_types(block))
        return out

    def to_scanned_pages_summary(self) -> list[dict]:
        return [
            {
                "url": p.url,
                "status_code": p.status_code,
                "title": p.title,
                "content_type": p.content_type,
                "fetch_error": p.fetch_error,
                "fetched_at_seconds": round(p.fetched_at_seconds, 2),
            }
            for p in self.pages
        ]


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


async def scan_website(homepage_url: str) -> ScanResult:
    """Run the full scan budget against ``homepage_url`` and return signals.

    Always returns a ScanResult — failures live on the per-page records and
    the ``homepage_failed`` flag.
    """
    started = time.monotonic()
    result = ScanResult(homepage_url=homepage_url, fetch_started_at=started)

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, headers=headers, follow_redirects=True) as client:
        # 1. Homepage first — its body drives subpage discovery.
        homepage = await _fetch_and_parse(client, homepage_url, started)
        result.pages.append(homepage)
        if homepage.fetch_error or (homepage.status_code or 0) >= 400:
            result.homepage_failed = True

        # 2. robots.txt + sitemap.xml in parallel
        robots_url = _join(homepage_url, "/robots.txt")
        sitemap_url = _join(homepage_url, "/sitemap.xml")
        robots_task = _fetch_text(client, robots_url, started)
        sitemap_task = _fetch_text(client, sitemap_url, started)
        robots_text, sitemap_text = await asyncio.gather(robots_task, sitemap_task)

        if robots_text is not None:
            result.robots_txt_present = True
            result.robots_txt_blocks_ai = _robots_blocks_ai(robots_text)
        if sitemap_text is not None:
            result.sitemap_present = True
            result.sitemap_url_count = _sitemap_url_count(sitemap_text)

        # 3. Subpage discovery — common paths + internal links
        candidates = _build_candidate_urls(homepage)
        # Cap total pages including the homepage already fetched.
        budget_remaining = _MAX_PAGES - len(result.pages)
        candidates = candidates[: max(budget_remaining, 0)]

        # Fetch remaining pages in parallel, but respect the wall-clock budget.
        async def _bounded(url: str) -> FetchedPage:
            if time.monotonic() - started > _TOTAL_BUDGET_SECONDS:
                return FetchedPage(url=url, fetch_error="scan_budget_exceeded")
            return await _fetch_and_parse(client, url, started)

        fetched = await asyncio.gather(*[_bounded(u) for u in candidates])
        for page in fetched:
            # Skip duplicates of homepage if site re-routes to /
            if page.url == result.homepage_url:
                continue
            result.pages.append(page)

    result.fetch_completed_at = time.monotonic()
    return result


# ─────────────────────────────────────────────────────────────────────
# Per-page fetch + parse
# ─────────────────────────────────────────────────────────────────────


async def _fetch_and_parse(client: httpx.AsyncClient, url: str, started: float) -> FetchedPage:
    page = FetchedPage(url=url)
    try:
        async with client.stream("GET", url) as resp:
            page.status_code = resp.status_code
            page.content_type = resp.headers.get("content-type", "").split(";")[0].strip() or None
            if resp.status_code >= 400:
                page.fetch_error = f"http_{resp.status_code}"
                page.fetched_at_seconds = time.monotonic() - started
                return page

            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                if total + len(chunk) > _MAX_BODY_BYTES:
                    chunks.append(chunk[: _MAX_BODY_BYTES - total])
                    break
                chunks.append(chunk)
                total += len(chunk)
            body = b"".join(chunks)

        # Only parse HTML bodies; non-html content yields no signals.
        if not page.content_type or "html" not in page.content_type:
            page.fetched_at_seconds = time.monotonic() - started
            return page

        _parse_html_into_page(body, page, base_url=url)
    except httpx.TimeoutException:
        page.fetch_error = "timeout"
    except httpx.RequestError as exc:
        page.fetch_error = f"request_error:{type(exc).__name__}"
    except Exception as exc:
        page.fetch_error = f"unexpected:{type(exc).__name__}"
        logger.warning("scanner.fetch_unexpected_error", url=url, error=str(exc))
    finally:
        page.fetched_at_seconds = time.monotonic() - started
    return page


def _parse_html_into_page(body: bytes, page: FetchedPage, base_url: str) -> None:
    soup = BeautifulSoup(body, "html.parser")

    if soup.title and soup.title.string:
        page.title = soup.title.string.strip()[:300]

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        page.meta_description = meta_desc["content"].strip()[:500]

    page.h1 = [t.get_text(strip=True)[:300] for t in soup.find_all("h1") if t.get_text(strip=True)][:5]
    page.h2 = [t.get_text(strip=True)[:300] for t in soup.find_all("h2") if t.get_text(strip=True)][:20]

    page.jsonld_blocks = _extract_jsonld_blocks(soup)
    page.internal_links = _extract_internal_links(soup, base_url)

    visible_text = soup.get_text(" ", strip=True)
    page.body_text_snippet = visible_text[:2000]


def _extract_jsonld_blocks(soup: BeautifulSoup) -> list[dict]:
    out: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (ValueError, TypeError):
            continue
        # JSON-LD allows either a single dict or a list of dicts (or @graph).
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    out.append(item)
    return out


def _extract_jsonld_types(block: dict) -> list[str]:
    types: list[str] = []
    if "@graph" in block and isinstance(block["@graph"], list):
        for child in block["@graph"]:
            if isinstance(child, dict):
                types.extend(_extract_jsonld_types(child))
    raw_type = block.get("@type")
    if isinstance(raw_type, str):
        types.append(raw_type)
    elif isinstance(raw_type, list):
        types.extend(t for t in raw_type if isinstance(t, str))
    return types


def _extract_internal_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    parsed_base = urlparse(base_url)
    base_host = parsed_base.netloc.lower()
    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != base_host:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
    return out[:200]


# ─────────────────────────────────────────────────────────────────────
# robots.txt / sitemap helpers
# ─────────────────────────────────────────────────────────────────────


async def _fetch_text(client: httpx.AsyncClient, url: str, started: float) -> str | None:
    if time.monotonic() - started > _TOTAL_BUDGET_SECONDS:
        return None
    try:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return None
        return resp.text[:_MAX_BODY_BYTES]
    except (httpx.TimeoutException, httpx.RequestError):
        return None


def _robots_blocks_ai(text: str) -> bool:
    """Return True if robots.txt explicitly disallows GPTBot / OAI-SearchBot
    / PerplexityBot / ClaudeBot / CCBot from /."""
    blocked = False
    current_agents: set[str] = set()
    blocked_agents = {
        "gptbot",
        "oai-searchbot",
        "perplexitybot",
        "claudebot",
        "ccbot",
        "anthropic-ai",
    }
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()
        if directive == "user-agent":
            current_agents = {value.lower()}
        elif directive == "disallow" and current_agents & blocked_agents:
            if value in ("/", "*"):
                blocked = True
                break
    return blocked


def _sitemap_url_count(text: str) -> int:
    try:
        # Sitemap XML may be a urlset or a sitemapindex.
        root = ET.fromstring(text)
    except ET.ParseError:
        return 0
    return sum(1 for _ in root.iter() if _.tag.endswith("loc"))


# ─────────────────────────────────────────────────────────────────────
# URL helpers
# ─────────────────────────────────────────────────────────────────────


def _join(base: str, path: str) -> str:
    parsed = urlparse(base)
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _build_candidate_urls(homepage: FetchedPage) -> list[str]:
    """Return up to N high-signal subpage URLs to fetch. Order:
    1. Common candidate paths derived from the homepage origin.
    2. Internal links matching link-hint substrings.
    """
    parsed = urlparse(homepage.url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    seen: set[str] = {homepage.url.rstrip("/"), homepage.url}
    out: list[str] = []
    for path in _CANDIDATE_PATHS:
        url = origin + path
        if url not in seen:
            out.append(url)
            seen.add(url)

    # Augment with any internal links from the homepage that match a hint.
    for link in homepage.internal_links:
        path_lower = urlparse(link).path.lower()
        if any(h in path_lower for h in _LINK_HINT_RE):
            normalized = link.rstrip("/")
            if normalized not in seen:
                out.append(link)
                seen.add(normalized)
                seen.add(link)

    return out


# Keep these importable so tests can monkey-patch.
__all__ = [
    "FetchedPage",
    "ScanResult",
    "scan_website",
    "USER_AGENT",
]


def parse_html_into_page(body: bytes, url: str) -> FetchedPage:
    """Test seam — parse a saved HTML fixture as if it had been fetched."""
    page = FetchedPage(url=url, status_code=200, content_type="text/html")
    _parse_html_into_page(body, page, base_url=url)
    return page


def _make_signals_dict(scan: ScanResult) -> dict[str, Any]:
    """Convert a ScanResult into the input dict the scoring engine consumes.
    Lives here so the scanner owns the transcript shape and the engine
    stays a pure function over a dict.
    """
    homepage = scan.homepage
    return {
        "homepage": _page_to_dict(homepage) if homepage else None,
        "homepage_failed": scan.homepage_failed,
        "robots_txt_present": scan.robots_txt_present,
        "robots_txt_blocks_ai": scan.robots_txt_blocks_ai,
        "sitemap_present": scan.sitemap_present,
        "sitemap_url_count": scan.sitemap_url_count,
        "subpages": [_page_to_dict(p) for p in scan.pages if p is not homepage],
        "all_jsonld_types": sorted(scan.jsonld_types()),
        "all_jsonld_blocks": scan.all_jsonld(),
    }


def _page_to_dict(page: FetchedPage | None) -> dict[str, Any]:
    if page is None:
        return {}
    return {
        "url": page.url,
        "status_code": page.status_code,
        "title": page.title,
        "h1": page.h1,
        "h2": page.h2,
        "meta_description": page.meta_description,
        "jsonld_blocks": page.jsonld_blocks,
        "body_text_snippet": page.body_text_snippet,
        "fetch_error": page.fetch_error,
        "content_type": page.content_type,
    }
