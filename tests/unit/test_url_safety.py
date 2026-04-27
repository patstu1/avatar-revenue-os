"""URL safety + normalization tests for the AI Buyer Trust Test."""

import pytest

from apps.api.services.url_safety import (
    UrlSafetyError,
    domain_of,
    normalize_website_url,
)


class TestNormalize:
    def test_accepts_https(self):
        assert normalize_website_url("https://acme.io") == "https://acme.io"

    def test_lowercases_scheme_and_host(self):
        assert normalize_website_url("HTTPS://Acme.IO") == "https://acme.io"

    def test_drops_default_https_port(self):
        assert normalize_website_url("https://acme.io:443/x") == "https://acme.io/x"

    def test_keeps_non_default_port(self):
        assert normalize_website_url("https://acme.io:8443/x") == "https://acme.io:8443/x"

    def test_strips_trailing_slash(self):
        assert normalize_website_url("https://acme.io/") == "https://acme.io"

    def test_drops_fragment(self):
        assert normalize_website_url("https://acme.io/foo#bar") == "https://acme.io/foo"

    def test_accepts_bare_domain_and_adds_https(self):
        assert normalize_website_url("acme.io") == "https://acme.io"

    def test_keeps_path_and_query(self):
        assert normalize_website_url("https://acme.io/services?x=1") == "https://acme.io/services?x=1"

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            None,
            "ftp://acme.io",
            "javascript:alert(1)",
            "mailto:a@b.com",
        ],
    )
    def test_rejects_unsupported_schemes_and_empty(self, raw):
        with pytest.raises(UrlSafetyError):
            normalize_website_url(raw)


class TestBlockedHosts:
    @pytest.mark.parametrize(
        "host",
        [
            "http://localhost",
            "http://127.0.0.1",
            "http://10.0.0.1",
            "http://192.168.1.1",
            "http://172.16.0.1",
            "http://169.254.0.1",
            "https://router.local",
            "https://corp.internal",
            "https://something.test",
            "https://acme.example.com",
            "https://example.com",
            "http://[::1]",
        ],
    )
    def test_rejects_internal_and_reserved_hosts(self, host):
        with pytest.raises(UrlSafetyError):
            normalize_website_url(host)

    @pytest.mark.parametrize(
        "host",
        [
            "https://staging.acme.com",
            "https://dev.acme.com",
            "https://qa.acme.com",
            "https://preview.acme.com",
        ],
    )
    def test_rejects_dev_subdomains(self, host):
        with pytest.raises(UrlSafetyError):
            normalize_website_url(host)

    def test_does_not_reject_label_substring(self):
        # 'developers.acme.com' is allowed even though 'dev' appears.
        assert normalize_website_url("https://developers.acme.com") == "https://developers.acme.com"


class TestDomainOf:
    def test_returns_lowercase_host(self):
        assert domain_of("https://Acme.IO/x") == "acme.io"

    def test_strips_www(self):
        assert domain_of("https://www.acme.io") == "acme.io"

    def test_keeps_non_www_subdomain(self):
        assert domain_of("https://blog.acme.io") == "blog.acme.io"
