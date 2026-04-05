"""PDF generation using WeasyPrint — real styled documents, no placeholders.

Generates lead magnet PDFs and media kit PDFs with brand colors, logos,
headers, footers, and page numbers.
"""
from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generate professional PDFs using WeasyPrint with inline HTML/CSS."""

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self._output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="pdf_gen_"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Lead Magnet PDF
    # ------------------------------------------------------------------

    def generate_lead_magnet(
        self,
        title: str,
        sections: list[dict[str, str]],
        brand_name: str,
        brand_colors: Optional[dict[str, str]] = None,
        logo_url: Optional[str] = None,
    ) -> str:
        """Generate a professional lead magnet PDF and return the file path.

        Args:
            title: Document title.
            sections: List of {"heading": str, "body": str} dicts.
            brand_name: Name shown in header/footer.
            brand_colors: Optional dict with keys like "primary", "secondary", "accent".
            logo_url: Optional URL to a logo image for the header.

        Returns:
            Absolute path to the generated PDF file.
        """
        colors = _resolve_colors(brand_colors)
        logo_img = f'<img src="{logo_url}" class="logo" />' if logo_url else ""

        sections_html = ""
        for i, sec in enumerate(sections):
            heading = _esc(sec.get("heading", ""))
            body = _esc(sec.get("body", ""))
            # Convert newlines in body to <br> for readability
            body_html = body.replace("\n", "<br />")
            sections_html += f"""
            <div class="section">
                <h2>{heading}</h2>
                <div class="body">{body_html}</div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8" /></head>
<body>
<style>
    @page {{
        size: A4;
        margin: 2cm 2cm 3cm 2cm;
        @top-center {{
            content: "{_esc(brand_name)}";
            font-family: Helvetica, Arial, sans-serif;
            font-size: 9pt;
            color: {colors['secondary']};
        }}
        @bottom-center {{
            content: "Page " counter(page) " of " counter(pages);
            font-family: Helvetica, Arial, sans-serif;
            font-size: 9pt;
            color: #999;
        }}
        @bottom-right {{
            content: "{_esc(brand_name)}";
            font-family: Helvetica, Arial, sans-serif;
            font-size: 8pt;
            color: #bbb;
        }}
    }}
    body {{
        font-family: Helvetica, Arial, sans-serif;
        color: #222;
        line-height: 1.6;
    }}
    .cover {{
        text-align: center;
        padding-top: 6cm;
        page-break-after: always;
    }}
    .cover .logo {{
        max-width: 180px;
        max-height: 80px;
        margin-bottom: 2cm;
    }}
    .cover h1 {{
        font-size: 28pt;
        color: {colors['primary']};
        margin-bottom: 0.5cm;
    }}
    .cover .brand {{
        font-size: 14pt;
        color: {colors['secondary']};
        margin-top: 1cm;
    }}
    .section {{
        margin-bottom: 1.5cm;
    }}
    .section h2 {{
        font-size: 16pt;
        color: {colors['primary']};
        border-bottom: 2px solid {colors['accent']};
        padding-bottom: 4px;
        margin-bottom: 0.5cm;
    }}
    .section .body {{
        font-size: 11pt;
        color: #333;
    }}
</style>

<div class="cover">
    {logo_img}
    <h1>{_esc(title)}</h1>
    <div class="brand">by {_esc(brand_name)}</div>
</div>

{sections_html}

</body>
</html>"""

        return self._render_pdf(html, f"lead_magnet_{uuid.uuid4().hex[:12]}.pdf")

    # ------------------------------------------------------------------
    # Media Kit PDF
    # ------------------------------------------------------------------

    def generate_media_kit(
        self,
        brand_name: str,
        stats: dict[str, Any],
        offerings: list[dict[str, str]],
        contact: dict[str, str],
        brand_colors: Optional[dict[str, str]] = None,
    ) -> str:
        """Generate a professional media kit PDF and return the file path.

        Args:
            brand_name: Name of the brand / creator.
            stats: Dict of metric name -> value (e.g. {"Instagram Followers": "125K"}).
            offerings: List of {"name": str, "description": str, "price": str}.
            contact: Dict with keys like "email", "website", "phone".
            brand_colors: Optional color overrides.

        Returns:
            Absolute path to the generated PDF file.
        """
        colors = _resolve_colors(brand_colors)

        # Stats grid
        stats_cells = ""
        for metric, value in stats.items():
            stats_cells += f"""
            <div class="stat-card">
                <div class="stat-value">{_esc(str(value))}</div>
                <div class="stat-label">{_esc(metric)}</div>
            </div>"""

        # Offerings table
        offering_rows = ""
        for off in offerings:
            offering_rows += f"""
            <tr>
                <td class="off-name">{_esc(off.get('name', ''))}</td>
                <td class="off-desc">{_esc(off.get('description', ''))}</td>
                <td class="off-price">{_esc(off.get('price', ''))}</td>
            </tr>"""

        # Contact block
        contact_lines = ""
        for key, val in contact.items():
            contact_lines += f"<div><strong>{_esc(key.title())}:</strong> {_esc(str(val))}</div>"

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8" /></head>
<body>
<style>
    @page {{
        size: A4;
        margin: 2cm;
        @bottom-center {{
            content: "Page " counter(page) " of " counter(pages);
            font-family: Helvetica, Arial, sans-serif;
            font-size: 9pt;
            color: #999;
        }}
    }}
    body {{
        font-family: Helvetica, Arial, sans-serif;
        color: #222;
        line-height: 1.5;
    }}
    .cover {{
        text-align: center;
        padding-top: 5cm;
        page-break-after: always;
    }}
    .cover h1 {{
        font-size: 32pt;
        color: {colors['primary']};
    }}
    .cover .subtitle {{
        font-size: 16pt;
        color: {colors['secondary']};
        margin-top: 0.5cm;
    }}
    h2 {{
        font-size: 18pt;
        color: {colors['primary']};
        border-bottom: 3px solid {colors['accent']};
        padding-bottom: 4px;
        margin-top: 1.5cm;
        margin-bottom: 0.8cm;
    }}
    .stats-grid {{
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        justify-content: center;
    }}
    .stat-card {{
        background: {colors['accent']}22;
        border: 1px solid {colors['accent']};
        border-radius: 8px;
        padding: 16px 24px;
        text-align: center;
        width: 140px;
    }}
    .stat-value {{
        font-size: 22pt;
        font-weight: bold;
        color: {colors['primary']};
    }}
    .stat-label {{
        font-size: 10pt;
        color: #555;
        margin-top: 4px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.5cm;
    }}
    th {{
        background: {colors['primary']};
        color: white;
        padding: 10px 12px;
        text-align: left;
        font-size: 11pt;
    }}
    td {{
        padding: 10px 12px;
        border-bottom: 1px solid #ddd;
        font-size: 10.5pt;
    }}
    .off-name {{
        font-weight: bold;
        width: 25%;
    }}
    .off-price {{
        font-weight: bold;
        color: {colors['primary']};
        white-space: nowrap;
    }}
    .contact-block {{
        background: #f7f7f7;
        padding: 20px;
        border-radius: 8px;
        margin-top: 1cm;
        font-size: 11pt;
        line-height: 2;
    }}
</style>

<div class="cover">
    <h1>{_esc(brand_name)}</h1>
    <div class="subtitle">Media Kit</div>
</div>

<h2>Audience &amp; Reach</h2>
<div class="stats-grid">
    {stats_cells}
</div>

<h2>Collaboration Offerings</h2>
<table>
    <thead>
        <tr><th>Offering</th><th>Description</th><th>Investment</th></tr>
    </thead>
    <tbody>
        {offering_rows}
    </tbody>
</table>

<h2>Contact</h2>
<div class="contact-block">
    {contact_lines}
</div>

</body>
</html>"""

        return self._render_pdf(html, f"media_kit_{uuid.uuid4().hex[:12]}.pdf")

    # ------------------------------------------------------------------
    # Internal renderer
    # ------------------------------------------------------------------

    def _render_pdf(self, html: str, filename: str) -> str:
        """Render HTML to PDF via WeasyPrint and return the output path."""
        from weasyprint import HTML as WeasyprintHTML

        out_path = self._output_dir / filename
        WeasyprintHTML(string=html).write_pdf(str(out_path))
        logger.info("PDF generated: %s (%d bytes)", out_path, out_path.stat().st_size)
        return str(out_path)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_DEFAULT_COLORS = {
    "primary": "#1a1a2e",
    "secondary": "#16213e",
    "accent": "#0f3460",
}


def _resolve_colors(brand_colors: Optional[dict[str, str]]) -> dict[str, str]:
    """Merge user-provided brand colors with defaults."""
    if not brand_colors:
        return dict(_DEFAULT_COLORS)
    merged = dict(_DEFAULT_COLORS)
    merged.update({k: v for k, v in brand_colors.items() if v})
    return merged


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
