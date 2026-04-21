"""Operator pages (Batch 5) — minimum server-rendered HTML surfaces so
the operator can run the system without writing code.

Pages:
  GET  /operator/                              home, links to everything
  GET  /operator/settings/providers            list + edit integration providers
  POST /operator/settings/providers/save       form POST → upsert provider row
  GET  /operator/settings/inbound-route        inbound email route config
  POST /operator/settings/inbound-route/save   form POST → upsert route
  GET  /operator/webhooks                      recent webhook_events viewer
  GET  /operator/pipeline                      consolidated revenue-loop state
  GET  /operator/team                          operator list + invite form
  POST /operator/team/invite                   form POST → create User
  GET  /operator/gm                            GM control board (approvals +
                                               escalations + stuck stages)
  POST /operator/gm/approvals/{id}/approve     form approve
  POST /operator/gm/approvals/{id}/reject      form reject
  POST /operator/gm/escalations/{id}/resolve   form resolve

Scope: HTMLResponse + Python f-strings, no JS, no SPA, no templating
library. Every form POST uses the existing JSON-API services under the
hood so state changes are identical across surfaces.
"""
from __future__ import annotations

import html
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, func, select

from apps.api.deps import AdminUser, DBSession, OperatorUser
from apps.api.services.stage_controller import resolve_approval, resolve_escalation
from packages.db.enums import UserRole
from packages.db.models.clients import Client, IntakeRequest
from packages.db.models.core import User
from packages.db.models.delivery import Delivery
from packages.db.models.email_pipeline import EmailReplyDraft
from packages.db.models.fulfillment import ClientProject, ProductionJob
from packages.db.models.gm_control import GMApproval, GMEscalation, StageState
from packages.db.models.integration_registry import IntegrationProvider
from packages.db.models.live_execution_phase2 import WebhookEvent
from packages.db.models.proposals import Payment, Proposal

logger = structlog.get_logger()

router = APIRouter(prefix="/operator", tags=["Operator Console"])


# ═══════════════════════════════════════════════════════════════════════════
#  Layout
# ═══════════════════════════════════════════════════════════════════════════


_BASE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       margin: 0; padding: 0; background: #f5f5f5; color: #111; }
nav { background: #111; color: #fff; padding: 10px 20px; }
nav a { color: #fff; margin-right: 16px; text-decoration: none; font-size: 13px; }
nav a:hover { text-decoration: underline; }
nav .you { float: right; font-size: 12px; color: #aaa; }
.container { max-width: 1180px; margin: 0 auto; padding: 20px 24px; }
h1 { font-size: 20px; margin: 0 0 4px 0; }
h2 { font-size: 15px; margin: 20px 0 8px 0; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
.sub { color: #666; font-size: 12px; margin-bottom: 18px; }
.flash { background: #fff4c2; border: 1px solid #e5c100; padding: 10px 14px;
         border-radius: 4px; margin-bottom: 20px; font-size: 13px; }
.flash.err { background: #fdd; border-color: #b00; }
.empty { color: #888; font-style: italic; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px;
        padding: 14px; margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; font-size: 12px;
        background: #fff; margin-top: 8px; }
th, td { padding: 6px 8px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }
th { background: #f5f5f5; font-weight: 600; }
form { display: inline; }
button, input[type=submit] { padding: 5px 12px; border: 1px solid #111;
        background: #fff; cursor: pointer; border-radius: 3px; font-size: 12px; }
button.primary, input.primary { background: #0a56a0; color: #fff; border-color: #0a56a0; }
button.ok { background: #0a7f2e; color: #fff; border-color: #0a7f2e; }
button.danger { background: #fff; color: #b00; border-color: #b00; }
input[type=text], input[type=email], input[type=password], textarea, select {
  padding: 5px 8px; font-size: 12px; border: 1px solid #ccc;
  border-radius: 3px; width: 100%; box-sizing: border-box; max-width: 420px;
}
label { display: block; font-size: 11px; font-weight: 600; color: #444;
        margin: 8px 0 3px 0; }
fieldset { border: 1px solid #ddd; border-radius: 4px; padding: 10px 14px;
           margin-bottom: 12px; background: #fafafa; }
legend { font-weight: 600; font-size: 12px; color: #333; padding: 0 6px; }
.pill { display: inline-block; padding: 1px 7px; border-radius: 10px;
        font-size: 10px; background: #eef; color: #335; }
.pill.sev-warning { background: #fff2d6; color: #b37300; }
.pill.sev-error { background: #fdd; color: #900; }
.pill.sev-info { background: #dfe; color: #050; }
.pill.st-pending { background: #fff2d6; color: #b37300; }
.pill.st-open { background: #fdd; color: #900; }
.pill.st-resolved, .pill.st-approved, .pill.st-sent, .pill.st-completed { background: #dfd; color: #060; }
.pill.st-rejected, .pill.st-failed { background: #fdd; color: #900; }
.kv { font-family: Menlo, Monaco, monospace; font-size: 11px; color: #333; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
"""


def _nav(user: User, flash: Optional[str] = None) -> str:
    flash_html = (
        f'<div class="flash">{html.escape(flash)}</div>' if flash else ""
    )
    return (
        "<nav>"
        "  <a href='/api/v1/operator/'>Home</a>"
        "  <a href='/api/v1/operator/pipeline'>Pipeline</a>"
        "  <a href='/api/v1/operator/gm'>GM board</a>"
        "  <a href='/api/v1/operator/pending-drafts'>Drafts</a>"
        "  <a href='/api/v1/operator/settings/providers'>Providers</a>"
        "  <a href='/api/v1/operator/settings/inbound-route'>Inbound route</a>"
        "  <a href='/api/v1/operator/webhooks'>Webhooks</a>"
        "  <a href='/api/v1/operator/team'>Team</a>"
        f"  <span class='you'>you: {html.escape(user.email or '')}</span>"
        "</nav>"
        f"<div class='container'>{flash_html}"
    )


def _close() -> str:
    return "</div>"


def _page(user: User, title: str, body: str, flash: Optional[str] = None) -> str:
    return (
        "<!doctype html><html lang='en'><head>"
        "<meta charset='utf-8'>"
        f"<title>{html.escape(title)} — Operator</title>"
        f"<style>{_BASE_CSS}</style>"
        "</head><body>"
        f"{_nav(user, flash)}"
        f"<h1>{html.escape(title)}</h1>"
        f"{body}"
        f"{_close()}</body></html>"
    )


def _pill(label: str, kind: str = "") -> str:
    cls = f"pill {kind}" if kind else "pill"
    return f'<span class="{cls}">{html.escape(label)}</span>'


# ═══════════════════════════════════════════════════════════════════════════
#  Home
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/", response_class=HTMLResponse)
async def home(current_user: OperatorUser, db: DBSession, flash: Optional[str] = None):
    org = current_user.organization_id
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    counts = {}
    counts["pending_drafts"] = (await db.execute(
        select(func.count()).select_from(EmailReplyDraft).where(
            EmailReplyDraft.org_id == org,
            EmailReplyDraft.status == "pending",
        )
    )).scalar() or 0
    counts["pending_approvals"] = (await db.execute(
        select(func.count()).select_from(GMApproval).where(
            GMApproval.org_id == org, GMApproval.status == "pending",
        )
    )).scalar() or 0
    counts["open_escalations"] = (await db.execute(
        select(func.count()).select_from(GMEscalation).where(
            GMEscalation.org_id == org,
            GMEscalation.status.in_(("open", "acknowledged")),
        )
    )).scalar() or 0
    counts["clients_active"] = (await db.execute(
        select(func.count()).select_from(Client).where(
            Client.org_id == org, Client.status == "active",
        )
    )).scalar() or 0
    counts["projects_active"] = (await db.execute(
        select(func.count()).select_from(ClientProject).where(
            ClientProject.org_id == org, ClientProject.status == "active",
        )
    )).scalar() or 0
    counts["payments_24h"] = (await db.execute(
        select(func.count()).select_from(Payment).where(
            Payment.org_id == org,
            Payment.status == "succeeded",
            Payment.created_at >= since,
        )
    )).scalar() or 0

    body = (
        "<div class='card'>"
        "<h2>Queue</h2>"
        f"<div>Pending drafts: <b>{counts['pending_drafts']}</b></div>"
        f"<div>Pending approvals: <b>{counts['pending_approvals']}</b></div>"
        f"<div>Open escalations: <b>{counts['open_escalations']}</b></div>"
        "</div>"
        "<div class='card'>"
        "<h2>State (last 24h)</h2>"
        f"<div>Active clients: <b>{counts['clients_active']}</b></div>"
        f"<div>Active projects: <b>{counts['projects_active']}</b></div>"
        f"<div>Payments captured: <b>{counts['payments_24h']}</b></div>"
        "</div>"
    )
    return HTMLResponse(_page(current_user, "Operator home", body, flash))


# ═══════════════════════════════════════════════════════════════════════════
#  Providers
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/settings/providers", response_class=HTMLResponse)
async def providers_page(current_user: AdminUser, db: DBSession, flash: Optional[str] = None):
    rows = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == current_user.organization_id,
            ).order_by(IntegrationProvider.provider_key)
        )
    ).scalars().all()

    rows_html = "".join(
        "<tr>"
        f"<td><b>{html.escape(p.provider_key)}</b></td>"
        f"<td>{html.escape(p.provider_name or '')}</td>"
        f"<td>{html.escape(p.provider_category or '')}</td>"
        f"<td>{_pill('enabled' if p.is_enabled else 'disabled', 'st-approved' if p.is_enabled else 'st-rejected')}</td>"
        f"<td class='kv'>{'✓' if p.api_key_encrypted else '—'}</td>"
        f"<td class='kv'>{html.escape(str(p.extra_config or {}))[:120]}</td>"
        "</tr>"
        for p in rows
    ) or "<tr><td class='empty' colspan='6'>No providers configured.</td></tr>"

    body = (
        "<p class='sub'>Credentials are stored encrypted; the raw value is never returned.</p>"
        "<table><thead><tr>"
        "<th>Key</th><th>Name</th><th>Category</th><th>Status</th>"
        "<th>Has API key</th><th>Extra config</th>"
        "</tr></thead><tbody>"
        f"{rows_html}"
        "</tbody></table>"
        "<h2>Add / update provider</h2>"
        "<form method='post' action='/api/v1/operator/settings/providers/save'>"
        "<fieldset><legend>Identity</legend>"
        "<label>Provider key</label><input type='text' name='provider_key' placeholder='smtp, stripe, stripe_webhook, shopify_webhook, inbound_email_route, anthropic ...' required>"
        "<label>Provider name</label><input type='text' name='provider_name' placeholder='Display name'>"
        "<label>Provider category</label>"
        "<select name='provider_category'>"
        "<option value='llm'>llm</option>"
        "<option value='email'>email</option>"
        "<option value='inbox'>inbox</option>"
        "<option value='payment'>payment</option>"
        "<option value='publishing'>publishing</option>"
        "<option value='analytics'>analytics</option>"
        "<option value='image'>image</option>"
        "<option value='video'>video</option>"
        "<option value='voice'>voice</option>"
        "</select>"
        "</fieldset>"
        "<fieldset><legend>Credentials</legend>"
        "<label>API key (sent encrypted)</label><input type='password' name='api_key' autocomplete='new-password'>"
        "<label>Extra config (JSON, optional)</label><textarea name='extra_config_json' rows='3' placeholder='{\"to_address\":\"reply@...\"}'></textarea>"
        "</fieldset>"
        "<label><input type='checkbox' name='is_enabled' value='on' checked> Enabled</label>"
        "<p><input class='primary' type='submit' value='Save'></p>"
        "</form>"
    )
    return HTMLResponse(_page(current_user, "Provider settings", body, flash))


@router.post("/settings/providers/save")
async def providers_save(
    current_user: AdminUser,
    db: DBSession,
    provider_key: str = Form(...),
    provider_name: str = Form(""),
    provider_category: str = Form("llm"),
    api_key: str = Form(""),
    extra_config_json: str = Form(""),
    is_enabled: Optional[str] = Form(None),
):
    import json
    from apps.api.services.integration_manager import _encrypt

    try:
        extra = json.loads(extra_config_json) if extra_config_json.strip() else {}
        if not isinstance(extra, dict):
            raise ValueError("extra_config must be a JSON object")
    except json.JSONDecodeError as exc:
        return RedirectResponse(
            f"/api/v1/operator/settings/providers?flash=Invalid JSON in extra_config: {html.escape(str(exc))}",
            status_code=303,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/api/v1/operator/settings/providers?flash={html.escape(str(exc))}",
            status_code=303,
        )

    existing = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == current_user.organization_id,
                IntegrationProvider.provider_key == provider_key,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        row = IntegrationProvider(
            organization_id=current_user.organization_id,
            provider_key=provider_key[:60],
            provider_name=provider_name[:120] or provider_key,
            provider_category=provider_category[:40] or "llm",
            is_enabled=(is_enabled == "on"),
            extra_config=extra or {},
            api_key_encrypted=_encrypt(api_key) if api_key else None,
        )
        db.add(row)
        msg = f"Provider {provider_key} created"
    else:
        existing.provider_name = provider_name[:120] or existing.provider_name
        existing.provider_category = provider_category[:40] or existing.provider_category
        existing.is_enabled = (is_enabled == "on")
        if extra:
            existing.extra_config = extra
        if api_key:
            existing.api_key_encrypted = _encrypt(api_key)
        msg = f"Provider {provider_key} updated"

    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/settings/providers?flash={html.escape(msg)}",
        status_code=303,
    )


# ── Inbound route (special case of provider) ────────────────────────────────


@router.get("/settings/inbound-route", response_class=HTMLResponse)
async def inbound_route_page(current_user: AdminUser, db: DBSession, flash: Optional[str] = None):
    rows = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == current_user.organization_id,
                IntegrationProvider.provider_key == "inbound_email_route",
            )
        )
    ).scalars().all()

    rows_html = "".join(
        "<tr>"
        f"<td class='kv'>{html.escape((p.extra_config or {}).get('to_address','') or '')}</td>"
        f"<td class='kv'>{html.escape((p.extra_config or {}).get('to_domain','') or '')}</td>"
        f"<td class='kv'>{html.escape((p.extra_config or {}).get('plus_token','') or '')}</td>"
        f"<td>{_pill('enabled' if p.is_enabled else 'disabled', 'st-approved' if p.is_enabled else 'st-rejected')}</td>"
        "</tr>"
        for p in rows
    ) or "<tr><td class='empty' colspan='4'>No inbound routes.</td></tr>"

    body = (
        "<p class='sub'>Routes determine which organization owns an inbound email. "
        "Match priority: exact to_address → plus_token → to_domain.</p>"
        "<table><thead><tr><th>To address</th><th>To domain</th><th>Plus token</th><th>Status</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
        "<h2>Add inbound route</h2>"
        "<form method='post' action='/api/v1/operator/settings/inbound-route/save'>"
        "<label>Match mode</label>"
        "<select name='match_mode'>"
        "<option value='to_address'>to_address (exact match)</option>"
        "<option value='to_domain'>to_domain (anything @domain)</option>"
        "<option value='plus_token'>plus_token (local+token@)</option>"
        "</select>"
        "<label>Match value</label><input type='text' name='match_value' placeholder='reply@reply.proofhook.com' required>"
        "<label><input type='checkbox' name='is_enabled' value='on' checked> Enabled</label>"
        "<p><input class='primary' type='submit' value='Save route'></p>"
        "</form>"
    )
    return HTMLResponse(_page(current_user, "Inbound email route", body, flash))


@router.post("/settings/inbound-route/save")
async def inbound_route_save(
    current_user: AdminUser,
    db: DBSession,
    match_mode: str = Form(...),
    match_value: str = Form(...),
    is_enabled: Optional[str] = Form(None),
):
    if match_mode not in ("to_address", "to_domain", "plus_token"):
        return RedirectResponse(
            "/api/v1/operator/settings/inbound-route?flash=Invalid match mode",
            status_code=303,
        )
    existing = (
        await db.execute(
            select(IntegrationProvider).where(
                IntegrationProvider.organization_id == current_user.organization_id,
                IntegrationProvider.provider_key == "inbound_email_route",
            ).limit(1)
        )
    ).scalar_one_or_none()
    extra = {match_mode: match_value.strip().lower()}
    if existing is None:
        row = IntegrationProvider(
            organization_id=current_user.organization_id,
            provider_key="inbound_email_route",
            provider_name="Inbound email route",
            provider_category="inbox",
            is_enabled=(is_enabled == "on"),
            extra_config=extra,
        )
        db.add(row)
    else:
        existing.extra_config = extra
        existing.is_enabled = (is_enabled == "on")
    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/settings/inbound-route?flash=Inbound route saved ({html.escape(match_mode)} = {html.escape(match_value)})",
        status_code=303,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Webhooks
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/webhooks", response_class=HTMLResponse)
async def webhooks_page(current_user: OperatorUser, db: DBSession, flash: Optional[str] = None):
    rows = (
        await db.execute(
            select(WebhookEvent)
            .order_by(desc(WebhookEvent.created_at))
            .limit(100)
        )
    ).scalars().all()

    rows_html = "".join(
        "<tr>"
        f"<td class='kv'>{html.escape(w.created_at.isoformat()[:19])}</td>"
        f"<td>{html.escape(w.source or '')}</td>"
        f"<td>{html.escape(w.event_type or '')}</td>"
        f"<td class='kv'>{html.escape((w.external_event_id or '')[:32])}</td>"
        f"<td>{_pill('processed' if w.processed else 'pending', 'st-approved' if w.processed else 'st-pending')}</td>"
        "</tr>"
        for w in rows
    ) or "<tr><td class='empty' colspan='5'>No webhook deliveries yet.</td></tr>"

    body = (
        "<p class='sub'>Last 100 deliveries across all sources.</p>"
        "<table><thead><tr>"
        "<th>At</th><th>Source</th><th>Event type</th><th>External id</th><th>Status</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )
    return HTMLResponse(_page(current_user, "Webhooks", body, flash))


# ═══════════════════════════════════════════════════════════════════════════
#  Pipeline status
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(current_user: OperatorUser, db: DBSession, flash: Optional[str] = None):
    org = current_user.organization_id
    limit = 25

    drafts = (await db.execute(
        select(EmailReplyDraft).where(
            EmailReplyDraft.org_id == org,
            EmailReplyDraft.status.in_(("pending", "approved", "sent")),
            EmailReplyDraft.is_active.is_(True),
        ).order_by(desc(EmailReplyDraft.created_at)).limit(limit)
    )).scalars().all()

    proposals = (await db.execute(
        select(Proposal).where(
            Proposal.org_id == org, Proposal.is_active.is_(True),
        ).order_by(desc(Proposal.created_at)).limit(limit)
    )).scalars().all()

    payments = (await db.execute(
        select(Payment).where(Payment.org_id == org)
        .order_by(desc(Payment.created_at)).limit(limit)
    )).scalars().all()

    clients = (await db.execute(
        select(Client).where(Client.org_id == org, Client.is_active.is_(True))
        .order_by(desc(Client.created_at)).limit(limit)
    )).scalars().all()

    intakes = (await db.execute(
        select(IntakeRequest).where(IntakeRequest.org_id == org)
        .order_by(desc(IntakeRequest.created_at)).limit(limit)
    )).scalars().all()

    projects = (await db.execute(
        select(ClientProject).where(ClientProject.org_id == org)
        .order_by(desc(ClientProject.created_at)).limit(limit)
    )).scalars().all()

    prod_jobs = (await db.execute(
        select(ProductionJob).where(ProductionJob.org_id == org)
        .order_by(desc(ProductionJob.created_at)).limit(limit)
    )).scalars().all()

    deliveries = (await db.execute(
        select(Delivery).where(Delivery.org_id == org)
        .order_by(desc(Delivery.created_at)).limit(limit)
    )).scalars().all()

    def _tbl(title, rows, headers, row_fn):
        body_rows = "".join(row_fn(r) for r in rows) or \
            f"<tr><td class='empty' colspan='{len(headers)}'>No rows.</td></tr>"
        ths = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        return (
            f"<h2>{html.escape(title)} ({len(rows)})</h2>"
            f"<table><thead><tr>{ths}</tr></thead><tbody>{body_rows}</tbody></table>"
        )

    body = (
        _tbl(
            "Reply drafts",
            drafts,
            ["Created", "To", "Subject", "Mode", "Status"],
            lambda d: (
                "<tr>"
                f"<td class='kv'>{html.escape(d.created_at.isoformat()[:19])}</td>"
                f"<td>{html.escape(d.to_email or '')}</td>"
                f"<td>{html.escape((d.subject or '')[:60])}</td>"
                f"<td>{_pill(d.reply_mode or '-', 'sev-info')}</td>"
                f"<td>{_pill(d.status or '', 'st-' + (d.status or ''))}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Proposals",
            proposals,
            ["Created", "Recipient", "Title", "Total", "Status"],
            lambda p: (
                "<tr>"
                f"<td class='kv'>{html.escape(p.created_at.isoformat()[:19])}</td>"
                f"<td>{html.escape(p.recipient_email or '')}</td>"
                f"<td>{html.escape((p.title or '')[:60])}</td>"
                f"<td class='kv'>${p.total_amount_cents/100:.2f}</td>"
                f"<td>{_pill(p.status or '', 'st-' + (p.status or ''))}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Payments",
            payments,
            ["Created", "Amount", "Event", "Proposal", "Status"],
            lambda pmt: (
                "<tr>"
                f"<td class='kv'>{html.escape(pmt.created_at.isoformat()[:19])}</td>"
                f"<td class='kv'>${pmt.amount_cents/100:.2f}</td>"
                f"<td class='kv'>{html.escape((pmt.provider_event_id or '')[:24])}</td>"
                f"<td class='kv'>{html.escape(str(pmt.proposal_id or '')[:8])}</td>"
                f"<td>{_pill(pmt.status or '', 'st-' + (pmt.status or ''))}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Clients",
            clients,
            ["Created", "Email", "Name", "Total paid", "Status"],
            lambda c: (
                "<tr>"
                f"<td class='kv'>{html.escape(c.created_at.isoformat()[:19])}</td>"
                f"<td>{html.escape(c.primary_email)}</td>"
                f"<td>{html.escape(c.display_name)}</td>"
                f"<td class='kv'>${c.total_paid_cents/100:.2f}</td>"
                f"<td>{_pill(c.status or '', 'st-' + (c.status or ''))}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Intakes",
            intakes,
            ["Created", "Token", "Title", "Status", "Sent at"],
            lambda i: (
                "<tr>"
                f"<td class='kv'>{html.escape(i.created_at.isoformat()[:19])}</td>"
                f"<td class='kv'>{html.escape(i.token[:12])}</td>"
                f"<td>{html.escape((i.title or '')[:60])}</td>"
                f"<td>{_pill(i.status or '', 'st-' + (i.status or ''))}</td>"
                f"<td class='kv'>{html.escape(i.sent_at.isoformat()[:19]) if i.sent_at else ''}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Projects",
            projects,
            ["Created", "Title", "Package", "Status", "Completed"],
            lambda p: (
                "<tr>"
                f"<td class='kv'>{html.escape(p.created_at.isoformat()[:19])}</td>"
                f"<td>{html.escape((p.title or '')[:60])}</td>"
                f"<td>{html.escape(p.package_slug or '')}</td>"
                f"<td>{_pill(p.status or '', 'st-' + (p.status or ''))}</td>"
                f"<td class='kv'>{html.escape(p.completed_at.isoformat()[:19]) if p.completed_at else ''}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Production jobs",
            prod_jobs,
            ["Created", "Type", "Title", "Attempt/Limit", "Status"],
            lambda j: (
                "<tr>"
                f"<td class='kv'>{html.escape(j.created_at.isoformat()[:19])}</td>"
                f"<td>{html.escape(j.job_type or '')}</td>"
                f"<td>{html.escape((j.title or '')[:60])}</td>"
                f"<td class='kv'>{j.attempt_count}/{j.retry_limit}</td>"
                f"<td>{_pill(j.status or '', 'st-' + (j.status or ''))}</td>"
                "</tr>"
            ),
        ) +
        _tbl(
            "Deliveries",
            deliveries,
            ["Created", "Recipient", "Title", "Status", "Follow-up"],
            lambda d: (
                "<tr>"
                f"<td class='kv'>{html.escape(d.created_at.isoformat()[:19])}</td>"
                f"<td>{html.escape(d.recipient_email or '')}</td>"
                f"<td>{html.escape((d.title or '')[:60])}</td>"
                f"<td>{_pill(d.status or '', 'st-' + (d.status or ''))}</td>"
                f"<td class='kv'>{html.escape(d.followup_scheduled_at.isoformat()[:19]) if d.followup_scheduled_at else ''}</td>"
                "</tr>"
            ),
        )
    )
    return HTMLResponse(_page(current_user, "Pipeline", body, flash))


# ═══════════════════════════════════════════════════════════════════════════
#  Team / operator provisioning
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/team", response_class=HTMLResponse)
async def team_page(current_user: AdminUser, db: DBSession, flash: Optional[str] = None):
    users = (
        await db.execute(
            select(User).where(
                User.organization_id == current_user.organization_id,
            ).order_by(desc(User.created_at))
        )
    ).scalars().all()

    rows_html = "".join(
        "<tr>"
        f"<td>{html.escape(u.email or '')}</td>"
        f"<td>{html.escape(u.full_name or '')}</td>"
        f"<td>{_pill(u.role.value if hasattr(u.role, 'value') else str(u.role), 'sev-info')}</td>"
        f"<td>{_pill('active' if u.is_active else 'inactive', 'st-approved' if u.is_active else 'st-rejected')}</td>"
        f"<td class='kv'>{html.escape(u.created_at.isoformat()[:19])}</td>"
        "</tr>"
        for u in users
    ) or "<tr><td class='empty' colspan='5'>No users yet.</td></tr>"

    body = (
        "<table><thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Status</th><th>Created</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
        "<h2>Invite new operator</h2>"
        "<form method='post' action='/api/v1/operator/team/invite'>"
        "<label>Email</label><input type='email' name='email' required>"
        "<label>Full name</label><input type='text' name='full_name' required>"
        "<label>Temporary password</label><input type='password' name='password' required minlength='8'>"
        "<label>Role</label>"
        "<select name='role'>"
        "<option value='operator'>operator</option>"
        "<option value='admin'>admin</option>"
        "<option value='viewer'>viewer</option>"
        "</select>"
        "<p><input class='primary' type='submit' value='Invite operator'></p>"
        "</form>"
    )
    return HTMLResponse(_page(current_user, "Team", body, flash))


@router.post("/team/invite")
async def team_invite(
    current_user: AdminUser,
    db: DBSession,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("operator"),
):
    from apps.api.services.auth_service import hash_password

    role_map = {
        "admin": UserRole.ADMIN,
        "operator": UserRole.OPERATOR,
        "viewer": UserRole.VIEWER,
    }
    user_role = role_map.get(role, UserRole.OPERATOR)

    existing = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse(
            f"/api/v1/operator/team?flash={html.escape('User already exists: ' + email)}",
            status_code=303,
        )

    user = User(
        organization_id=current_user.organization_id,
        email=email,
        full_name=full_name,
        role=user_role,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/team?flash={html.escape('Invited ' + email + ' as ' + role)}",
        status_code=303,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  GM board UI
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/gm", response_class=HTMLResponse)
async def gm_page(current_user: OperatorUser, db: DBSession, flash: Optional[str] = None):
    org = current_user.organization_id

    approvals = (await db.execute(
        select(GMApproval).where(
            GMApproval.org_id == org, GMApproval.is_active.is_(True),
            GMApproval.status == "pending",
        ).order_by(desc(GMApproval.created_at)).limit(50)
    )).scalars().all()

    escalations = (await db.execute(
        select(GMEscalation).where(
            GMEscalation.org_id == org, GMEscalation.is_active.is_(True),
            GMEscalation.status.in_(("open", "acknowledged")),
        ).order_by(desc(GMEscalation.last_seen_at)).limit(50)
    )).scalars().all()

    stuck = (await db.execute(
        select(StageState).where(
            StageState.org_id == org,
            StageState.is_active.is_(True),
            StageState.is_stuck.is_(True),
        ).order_by(StageState.sla_deadline.asc()).limit(50)
    )).scalars().all()

    app_rows = "".join(
        "<tr>"
        f"<td>{html.escape(a.action_type)}</td>"
        f"<td>{html.escape(a.entity_type)}</td>"
        f"<td class='kv'>{html.escape(str(a.entity_id)[:12])}</td>"
        f"<td>{html.escape((a.title or '')[:60])}</td>"
        f"<td>{_pill(a.risk_level, 'sev-warning' if a.risk_level in ('high','critical') else 'sev-info')}</td>"
        "<td>"
        f"<form method='post' action='/api/v1/operator/gm/approvals/{a.id}/approve'>"
        "<button class='ok' type='submit'>Approve</button></form> "
        f"<form method='post' action='/api/v1/operator/gm/approvals/{a.id}/reject'>"
        "<button class='danger' type='submit'>Reject</button></form>"
        "</td></tr>"
        for a in approvals
    ) or "<tr><td class='empty' colspan='6'>No approvals pending.</td></tr>"

    esc_rows = "".join(
        "<tr>"
        f"<td>{html.escape(e.reason_code)}</td>"
        f"<td>{html.escape(e.entity_type)}</td>"
        f"<td class='kv'>{html.escape(str(e.entity_id)[:12])}</td>"
        f"<td>{html.escape((e.title or '')[:60])}</td>"
        f"<td>{_pill(e.severity, 'sev-' + e.severity)}</td>"
        f"<td class='kv'>{e.occurrence_count}</td>"
        "<td>"
        f"<form method='post' action='/api/v1/operator/gm/escalations/{e.id}/resolve'>"
        "<button class='ok' type='submit'>Resolve</button></form>"
        "</td></tr>"
        for e in escalations
    ) or "<tr><td class='empty' colspan='7'>No open escalations.</td></tr>"

    stuck_rows = "".join(
        "<tr>"
        f"<td>{html.escape(s.entity_type)}/{html.escape(s.stage)}</td>"
        f"<td class='kv'>{html.escape(str(s.entity_id)[:12])}</td>"
        f"<td class='kv'>{html.escape(s.sla_deadline.isoformat()[:19]) if s.sla_deadline else ''}</td>"
        f"<td>{html.escape(s.stuck_reason or '')}</td>"
        "</tr>"
        for s in stuck
    ) or "<tr><td class='empty' colspan='4'>Nothing stuck.</td></tr>"

    body = (
        "<h2>Awaiting approval</h2>"
        "<table><thead><tr>"
        "<th>Action</th><th>Entity</th><th>Id</th><th>Title</th><th>Risk</th><th></th>"
        "</tr></thead>"
        f"<tbody>{app_rows}</tbody></table>"
        "<h2>Escalations</h2>"
        "<table><thead><tr>"
        "<th>Reason</th><th>Entity</th><th>Id</th><th>Title</th><th>Severity</th><th>Occ</th><th></th>"
        "</tr></thead>"
        f"<tbody>{esc_rows}</tbody></table>"
        "<h2>Stuck stages</h2>"
        "<table><thead><tr><th>Stage</th><th>Entity id</th><th>SLA was</th><th>Reason</th></tr></thead>"
        f"<tbody>{stuck_rows}</tbody></table>"
        "<h2>Run watcher</h2>"
        "<form method='post' action='/api/v1/operator/gm/watcher/run-now'>"
        "<button class='primary' type='submit'>Scan stuck stages now</button>"
        "</form>"
    )
    return HTMLResponse(_page(current_user, "GM control board", body, flash))


@router.post("/gm/approvals/{approval_id}/approve")
async def gm_approve_form(
    approval_id: str, current_user: OperatorUser, db: DBSession,
):
    approval = await _require_owned(db, GMApproval, approval_id, current_user.organization_id, "Approval")
    try:
        await resolve_approval(
            db, approval=approval, decision="approved",
            decided_by=current_user.email, notes=None,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/api/v1/operator/gm?flash={html.escape(str(exc))}", status_code=303,
        )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/gm?flash={html.escape('Approved ' + approval.action_type)}",
        status_code=303,
    )


@router.post("/gm/approvals/{approval_id}/reject")
async def gm_reject_form(
    approval_id: str, current_user: OperatorUser, db: DBSession,
):
    approval = await _require_owned(db, GMApproval, approval_id, current_user.organization_id, "Approval")
    try:
        await resolve_approval(
            db, approval=approval, decision="rejected",
            decided_by=current_user.email, notes=None,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/api/v1/operator/gm?flash={html.escape(str(exc))}", status_code=303,
        )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/gm?flash={html.escape('Rejected ' + approval.action_type)}",
        status_code=303,
    )


@router.post("/gm/escalations/{escalation_id}/resolve")
async def gm_resolve_escalation_form(
    escalation_id: str, current_user: OperatorUser, db: DBSession,
):
    escalation = await _require_owned(db, GMEscalation, escalation_id, current_user.organization_id, "Escalation")
    await resolve_escalation(
        db, escalation=escalation, resolved_by=current_user.email, notes=None,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/gm?flash={html.escape('Resolved ' + escalation.reason_code)}",
        status_code=303,
    )


@router.post("/gm/watcher/run-now")
async def gm_watcher_run_form(current_user: OperatorUser, db: DBSession):
    from apps.api.services.stage_controller import run_stuck_stage_watcher
    result = await run_stuck_stage_watcher(db, org_id=current_user.organization_id)
    await db.commit()
    msg = (
        f"Watcher complete: checked={result.get('checked')} "
        f"stuck={result.get('stuck')} opened={result.get('escalations_opened')}"
    )
    return RedirectResponse(
        f"/api/v1/operator/gm?flash={html.escape(msg)}", status_code=303,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


async def _require_owned(db, model, row_id: str, org_id: uuid.UUID, label: str):
    try:
        rid = uuid.UUID(row_id)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Invalid {label} id")
    row = (
        await db.execute(select(model).where(model.id == rid))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"{label} not found")
    if row.org_id != org_id:
        raise HTTPException(403, f"{label} belongs to another organization")
    return row
