"""URL safety + normalization for the AI Buyer Trust Test scanner.

Validates that a submitted website URL is a public http(s) URL, normalizes
its domain, and rejects internal/private/test/example/loopback hosts so the
scanner cannot be coerced into hitting internal infra (SSRF) or wasting a
scan budget on a test domain.

Stateless. No DB access.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

# Hostnames that are never publicly scannable.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "broadcasthost",
    }
)

# Suffixes we refuse — RFC reserved, plus common dev/staging conventions.
_BLOCKED_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".intranet",
    ".lan",
    ".test",
    ".example",
    ".invalid",
)

# Example second-level domains reserved by IANA for documentation.
_EXAMPLE_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
    }
)

# Hostname labels that, if they make up the FULL hostname (including TLD),
# are obvious staging/dev/test deployments. We reject these so prospects
# can't hit a non-production environment by mistake. We do NOT reject a
# label that is part of a longer hostname (e.g. "developers.proofhook.com"
# is allowed because "developers" is not the entire hostname).
_DEV_LABEL_PREFIXES = ("staging.", "dev.", "qa.", "preview.", "uat.")


class UrlSafetyError(ValueError):
    """Raised when a URL fails safety validation. Message is operator-safe."""


def normalize_website_url(raw: str) -> str:
    """Return a normalized canonical form (lowercase scheme + host, no
    trailing slash, no fragment, no default-port suffix). Raises
    UrlSafetyError on any safety violation.
    """
    if not raw or not isinstance(raw, str):
        raise UrlSafetyError("Website URL is required.")

    candidate = raw.strip()
    # Permit bare-domain inputs by prepending https:// — operators expect
    # to type "acme.com" without a scheme.
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:", candidate):
        candidate = "https://" + candidate

    try:
        parsed = urlparse(candidate)
    except Exception as exc:
        raise UrlSafetyError(f"Could not parse URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise UrlSafetyError("Only http and https URLs are supported.")

    host = (parsed.hostname or "").lower()
    if not host:
        raise UrlSafetyError("URL is missing a hostname.")

    _reject_unsafe_host(host)

    # Reconstruct canonical URL: lowercase scheme+host, drop default port,
    # keep path/query, drop fragment.
    port = parsed.port
    netloc = host
    if port and not _is_default_port(scheme, port):
        netloc = f"{host}:{port}"

    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}".rstrip("/")


def domain_of(url: str) -> str:
    """Return the lowercase hostname portion of an already-validated URL.
    Strips a leading ``www.`` so dedup keys aren't fragmented across the
    bare and www variants of the same property.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _is_default_port(scheme: str, port: int) -> bool:
    return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)


def _reject_unsafe_host(host: str) -> None:
    """Raise UrlSafetyError if the hostname is private, loopback, link-local,
    a reserved/example domain, or a clear dev/staging/test target.
    """
    if host in _BLOCKED_HOSTNAMES:
        raise UrlSafetyError(f"'{host}' is not a public hostname.")

    if host.endswith(_BLOCKED_SUFFIXES):
        raise UrlSafetyError(f"'{host}' uses a reserved or non-public suffix.")

    if host in _EXAMPLE_DOMAINS or any(host.endswith("." + d) for d in _EXAMPLE_DOMAINS):
        raise UrlSafetyError(f"'{host}' is an example/reserved domain.")

    # Reject known staging/dev/qa subdomain prefixes when they precede the
    # eTLD+1 (i.e. "staging.acme.com" but allow "stagingfeature.acme.com").
    for prefix in _DEV_LABEL_PREFIXES:
        if host.startswith(prefix):
            raise UrlSafetyError(
                f"'{host}' looks like a non-production environment. "
                f"Submit your live public website."
            )

    # IP literal? Block private / loopback / link-local / reserved ranges.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Not an IP literal — hostnames are allowed past this point.
        return

    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise UrlSafetyError("Internal IP addresses cannot be scanned.")
