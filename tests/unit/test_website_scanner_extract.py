"""Pure-parse tests for the website scanner — no network."""

from apps.api.services.website_scanner import parse_html_into_page

CLEAN_HTML = """
<!doctype html>
<html><head>
  <title>Acme — fraud detection for B2B SaaS</title>
  <meta name="description" content="We help B2B SaaS finance teams reduce fraud loss without burning conversions.">
  <script type="application/ld+json">{"@type":"Organization","name":"Acme","url":"https://acme.io","sameAs":["https://x.com/acmehq"]}</script>
  <script type="application/ld+json">[
    {"@type":"WebSite","name":"Acme"},
    {"@type":"FAQPage"}
  ]</script>
</head><body>
  <h1>Stop payment fraud before checkout.</h1>
  <h2>How Acme works</h2>
  <h2>Pricing</h2>
  <p>For B2B SaaS finance teams. Trusted by 200+ companies. 1234 Market Street, Suite 200. (415) 555-0100. hello@acme.io.</p>
  <a href="/about">About</a>
  <a href="https://acme.io/services">Services</a>
  <a href="/faq">FAQ</a>
  <a href="https://other.example/blog">External</a>
  <a href="#anchor">Anchor</a>
  <a href="mailto:x@acme.io">Mail</a>
</body></html>
""".encode("utf-8")


def test_parses_title_h1_h2_and_meta():
    page = parse_html_into_page(CLEAN_HTML, "https://acme.io")
    assert page.title == "Acme — fraud detection for B2B SaaS"
    assert page.h1 == ["Stop payment fraud before checkout."]
    assert "How Acme works" in page.h2
    assert "Pricing" in page.h2
    assert page.meta_description and "B2B SaaS finance" in page.meta_description


def test_extracts_jsonld_blocks_including_lists():
    page = parse_html_into_page(CLEAN_HTML, "https://acme.io")
    types = sorted(
        {
            t
            for block in page.jsonld_blocks
            for t in (
                [block.get("@type")] if isinstance(block.get("@type"), str) else (block.get("@type") or [])
            )
            if isinstance(t, str)
        }
    )
    # Both list and dict-shaped JSON-LD blocks expanded
    assert "Organization" in types
    assert "WebSite" in types
    assert "FAQPage" in types


def test_internal_links_filter_external_and_anchors():
    page = parse_html_into_page(CLEAN_HTML, "https://acme.io")
    # Same host only, anchors and mailto stripped
    assert "https://acme.io/about" in page.internal_links
    assert "https://acme.io/services" in page.internal_links
    assert "https://acme.io/faq" in page.internal_links
    assert all(not link.startswith("https://other.example") for link in page.internal_links)
    assert all("mailto:" not in link for link in page.internal_links)


def test_visible_body_text_snippet_truncated():
    page = parse_html_into_page(CLEAN_HTML, "https://acme.io")
    assert "B2B SaaS" in page.body_text_snippet
    assert len(page.body_text_snippet) <= 2000
