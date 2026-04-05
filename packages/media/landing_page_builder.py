"""Landing page builder — generates deployable single-page HTML and ships it.

Deployment targets:
    1. Vercel (if VERCEL_TOKEN env var is set) — creates/updates a project and deploys.
    2. Local fallback — saves HTML to the media directory and returns a local URL.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

LOCAL_DEPLOY_ROOT = Path(os.getenv("LOCAL_MEDIA_ROOT", "/app/media")) / "landing_pages"


class LandingPageBuilder:
    """Build responsive landing page HTML and deploy it."""

    # ------------------------------------------------------------------
    # Build HTML
    # ------------------------------------------------------------------

    async def build_landing_page(
        self,
        title: str,
        headline: str,
        body: str,
        cta_text: str,
        download_url: str,
        email_capture_endpoint: Optional[str] = None,
        brand_colors: Optional[dict[str, str]] = None,
    ) -> str:
        """Return a complete, self-contained, responsive HTML landing page.

        Args:
            title: Page <title>.
            headline: Hero headline.
            body: Description / sales copy (plain text or simple HTML).
            cta_text: Call-to-action button text.
            download_url: URL the CTA button links to (PDF download).
            email_capture_endpoint: If provided, render an email form that POSTs here.
            brand_colors: Optional {"primary", "secondary", "accent"} hex colors.

        Returns:
            Full HTML string ready to be saved or deployed.
        """
        colors = _resolve_colors(brand_colors)
        body_html = body.replace("\n", "<br />") if "<" not in body else body

        email_form_html = ""
        if email_capture_endpoint:
            email_form_html = f"""
            <form class="email-form" method="POST" action="{_esc_attr(email_capture_endpoint)}">
                <input type="email" name="email" placeholder="Enter your email" required />
                <button type="submit" class="btn btn-cta">{_esc(cta_text)}</button>
            </form>"""
            # When there's an email form, the direct download button becomes secondary
            download_btn = f"""
            <a href="{_esc_attr(download_url)}" class="btn btn-secondary">Or download directly</a>"""
        else:
            download_btn = f"""
            <a href="{_esc_attr(download_url)}" class="btn btn-cta">{_esc(cta_text)}</a>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_esc(title)}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
                         Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
            color: #222;
            background: #fafafa;
            line-height: 1.6;
        }}

        .hero {{
            background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']});
            color: #fff;
            padding: 80px 24px 60px;
            text-align: center;
        }}

        .hero h1 {{
            font-size: clamp(1.8rem, 5vw, 3rem);
            font-weight: 800;
            margin-bottom: 16px;
            line-height: 1.2;
        }}

        .hero p {{
            font-size: clamp(1rem, 2.5vw, 1.25rem);
            max-width: 640px;
            margin: 0 auto 32px;
            opacity: 0.92;
        }}

        .content {{
            max-width: 680px;
            margin: -40px auto 0;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            padding: 40px 32px;
            position: relative;
            z-index: 1;
        }}

        .content .body-text {{
            font-size: 1.05rem;
            color: #444;
            margin-bottom: 32px;
        }}

        .btn {{
            display: inline-block;
            padding: 14px 36px;
            border-radius: 8px;
            font-size: 1.1rem;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            transition: transform 0.15s, box-shadow 0.15s;
            border: none;
        }}

        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        }}

        .btn-cta {{
            background: {colors['accent']};
            color: #fff;
        }}

        .btn-secondary {{
            background: transparent;
            color: {colors['primary']};
            border: 2px solid {colors['primary']};
            margin-top: 12px;
            font-size: 0.95rem;
            padding: 10px 24px;
        }}

        .cta-area {{
            text-align: center;
            margin-top: 24px;
        }}

        .email-form {{
            display: flex;
            gap: 12px;
            max-width: 460px;
            margin: 0 auto 16px;
            flex-wrap: wrap;
            justify-content: center;
        }}

        .email-form input[type="email"] {{
            flex: 1;
            min-width: 220px;
            padding: 14px 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .email-form input[type="email"]:focus {{
            border-color: {colors['accent']};
        }}

        .email-form .btn {{
            white-space: nowrap;
        }}

        footer {{
            text-align: center;
            padding: 40px 24px;
            font-size: 0.85rem;
            color: #999;
        }}

        @media (max-width: 600px) {{
            .hero {{ padding: 60px 16px 40px; }}
            .content {{ margin: -24px 12px 0; padding: 28px 20px; }}
            .email-form {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>

<section class="hero">
    <h1>{_esc(headline)}</h1>
    <p>{_esc(title)}</p>
</section>

<div class="content">
    <div class="body-text">{body_html}</div>

    <div class="cta-area">
        {email_form_html}
        {download_btn}
    </div>
</div>

<footer>
    &copy; {_esc(title)} &mdash; All rights reserved.
</footer>

</body>
</html>"""
        return html

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    async def deploy(
        self,
        html_content: str,
        project_name: str,
        deploy_token: Optional[str] = None,
    ) -> dict[str, str]:
        """Deploy an HTML landing page and return its live URL.

        Strategy:
            1. If VERCEL_TOKEN (or *deploy_token*) is set, deploy to Vercel.
            2. Otherwise, save locally under LOCAL_DEPLOY_ROOT and return a local URL.

        Args:
            html_content: The full HTML string to deploy.
            project_name: Slug used for the Vercel project or local filename.
            deploy_token: Explicit Vercel token. Falls back to VERCEL_TOKEN env var.

        Returns:
            {"url": str, "deployment_id": str}
        """
        token = deploy_token or os.getenv("VERCEL_TOKEN")
        slug = _slugify(project_name)

        if token:
            return await self._deploy_vercel(html_content, slug, token)
        return self._deploy_local(html_content, slug)

    # -- Vercel deployment -------------------------------------------------

    async def _deploy_vercel(
        self, html_content: str, slug: str, token: str
    ) -> dict[str, str]:
        """Create a Vercel deployment via the v13 API."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Vercel deployments API — file-based deploy
        payload = {
            "name": slug,
            "files": [
                {
                    "file": "index.html",
                    "data": html_content,
                },
            ],
            "projectSettings": {
                "framework": None,
            },
            "target": "production",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            # Ensure the project exists (idempotent)
            await client.post(
                "https://api.vercel.com/v10/projects",
                headers=headers,
                json={"name": slug},
            )

            # Deploy
            resp = await client.post(
                "https://api.vercel.com/v13/deployments",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        url = data.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://{url}"

        deployment_id = data.get("id", "")
        logger.info("Vercel deploy OK: project=%s url=%s id=%s", slug, url, deployment_id)
        return {"url": url, "deployment_id": deployment_id}

    # -- Local fallback ----------------------------------------------------

    def _deploy_local(self, html_content: str, slug: str) -> dict[str, str]:
        """Save HTML locally and return a local-serve URL."""
        LOCAL_DEPLOY_ROOT.mkdir(parents=True, exist_ok=True)
        filename = f"{slug}.html"
        dest = LOCAL_DEPLOY_ROOT / filename
        dest.write_text(html_content, encoding="utf-8")

        local_url = f"/media/landing_pages/{filename}"
        deployment_id = f"local-{uuid.uuid4().hex[:8]}"
        logger.info("Local deploy OK: %s -> %s", slug, dest)
        return {"url": local_url, "deployment_id": deployment_id}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_DEFAULT_COLORS = {
    "primary": "#1a1a2e",
    "secondary": "#16213e",
    "accent": "#e94560",
}


def _resolve_colors(brand_colors: Optional[dict[str, str]]) -> dict[str, str]:
    if not brand_colors:
        return dict(_DEFAULT_COLORS)
    merged = dict(_DEFAULT_COLORS)
    merged.update({k: v for k, v in brand_colors.items() if v})
    return merged


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _esc_attr(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _slugify(name: str) -> str:
    """Turn a project name into a URL-safe slug."""
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return slug[:63] if slug else f"landing-{uuid.uuid4().hex[:8]}"
