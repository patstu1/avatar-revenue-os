"""Minimum operator console — server-rendered HTML for pending-draft review.

Scope: one page, no SPA, no JS framework, no external templating lib.
Renders the operator's pending EmailReplyDraft rows with Approve and
Reject form buttons that POST back into this router. Every state change
goes through ``reply_draft_actions`` so events + audit writes are
identical to the JSON API.

This is a deliberately minimal surface — it exists so the revenue
send-loop can close without waiting for the broader operator UI batch.
"""

from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.reply_draft_actions import (
    DraftActionError,
    approve_draft,
    reject_draft,
)
from packages.db.models.email_pipeline import EmailClassification, EmailReplyDraft

router = APIRouter(prefix="/operator", tags=["Operator Console"])


@router.get("/pending-drafts", response_class=HTMLResponse)
async def pending_drafts_page(
    current_user: OperatorUser,
    db: DBSession,
    flash: str | None = None,
):
    """Render the operator's pending reply drafts as server-side HTML.

    Org-scoped: only pending drafts owned by the operator's organization
    are shown. Approved + rejected drafts are listed in separate compact
    sections for context.
    """
    pending_rows = (
        await db.execute(
            select(EmailReplyDraft, EmailClassification)
            .outerjoin(
                EmailClassification,
                EmailClassification.id == EmailReplyDraft.classification_id,
            )
            .where(
                EmailReplyDraft.org_id == current_user.organization_id,
                EmailReplyDraft.status == "pending",
                EmailReplyDraft.is_active.is_(True),
            )
            .order_by(desc(EmailReplyDraft.created_at))
            .limit(100)
        )
    ).all()

    recent_rows = (
        (
            await db.execute(
                select(EmailReplyDraft)
                .where(
                    EmailReplyDraft.org_id == current_user.organization_id,
                    EmailReplyDraft.status.in_(("approved", "sent", "rejected")),
                    EmailReplyDraft.is_active.is_(True),
                )
                .order_by(desc(EmailReplyDraft.created_at))
                .limit(25)
            )
        )
        .scalars()
        .all()
    )

    cards = "\n".join(_render_draft_card(draft, classification) for draft, classification in pending_rows)
    recent_rows_html = "\n".join(_render_recent_row(draft) for draft in recent_rows)

    flash_banner = f'<div class="flash">{html.escape(flash)}</div>' if flash else ""

    page = _PAGE_TEMPLATE.format(
        operator_email=html.escape(current_user.email or ""),
        pending_count=len(pending_rows),
        flash_banner=flash_banner,
        pending_cards=cards or '<p class="empty">No pending drafts. Send loop is clear.</p>',
        recent_rows=recent_rows_html or '<tr><td colspan="5" class="empty">No recent drafts.</td></tr>',
    )
    return HTMLResponse(content=page)


@router.post("/drafts/{draft_id}/approve")
async def approve_draft_form(
    draft_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    """HTML-form approve action. Redirects back to the pending-drafts page."""
    try:
        draft = await approve_draft(db, draft_id=uuid.UUID(draft_id), actor=current_user)
    except ValueError:
        raise HTTPException(400, "Invalid draft id")
    except DraftActionError as exc:
        msg = str(exc)
        if exc.current_status == "missing":
            return RedirectResponse(
                f"/api/v1/operator/pending-drafts?flash={html.escape('Draft not found')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/api/v1/operator/pending-drafts?flash={html.escape(msg)}",
            status_code=303,
        )

    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/pending-drafts?flash={html.escape(f'Approved draft {draft.id}')}",
        status_code=303,
    )


@router.post("/drafts/{draft_id}/reject")
async def reject_draft_form(
    draft_id: str,
    current_user: OperatorUser,
    db: DBSession,
    reason: str | None = Form(default=None),
):
    """HTML-form reject action. Redirects back to the pending-drafts page."""
    try:
        draft = await reject_draft(
            db,
            draft_id=uuid.UUID(draft_id),
            actor=current_user,
            reason=reason,
        )
    except ValueError:
        raise HTTPException(400, "Invalid draft id")
    except DraftActionError as exc:
        msg = str(exc)
        if exc.current_status == "missing":
            return RedirectResponse(
                f"/api/v1/operator/pending-drafts?flash={html.escape('Draft not found')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/api/v1/operator/pending-drafts?flash={html.escape(msg)}",
            status_code=303,
        )

    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    await db.commit()
    return RedirectResponse(
        f"/api/v1/operator/pending-drafts?flash={html.escape(f'Rejected draft {draft.id}')}",
        status_code=303,
    )


def _render_draft_card(draft: EmailReplyDraft, classification) -> str:
    intent = classification.intent if classification is not None else "unknown"
    confidence = f"{float(classification.confidence):.2f}" if classification is not None else "n/a"
    mode_source = draft.decision_trace.get("mode_source") if isinstance(draft.decision_trace, dict) else "n/a"
    package = draft.package_offered or "n/a"
    created = draft.created_at.isoformat() if draft.created_at else ""

    return _CARD_TEMPLATE.format(
        draft_id=html.escape(str(draft.id)),
        to_email=html.escape(draft.to_email or ""),
        subject=html.escape(draft.subject or "(no subject)"),
        reply_mode=html.escape(draft.reply_mode or "draft"),
        mode_source=html.escape(str(mode_source or "n/a")),
        intent=html.escape(intent),
        confidence=html.escape(confidence),
        package=html.escape(package),
        created=html.escape(created),
        body_text=html.escape(draft.body_text or "(empty)"),
    )


def _render_recent_row(draft: EmailReplyDraft) -> str:
    return (
        "<tr>"
        f"<td class='status-{html.escape(draft.status or '')}'>{html.escape(draft.status or '')}</td>"
        f"<td>{html.escape(draft.to_email or '')}</td>"
        f"<td>{html.escape((draft.subject or '')[:80])}</td>"
        f"<td>{html.escape(draft.reply_mode or '')}</td>"
        f"<td>{html.escape(draft.created_at.isoformat() if draft.created_at else '')}</td>"
        "</tr>"
    )


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Operator Console — Pending Drafts</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 0; padding: 24px 32px; background: #fafafa; color: #111; }}
  h1 {{ font-size: 20px; margin: 0 0 4px 0; }}
  .sub {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .flash {{ background: #fff4c2; border: 1px solid #e5c100; padding: 10px 14px;
            border-radius: 4px; margin-bottom: 20px; font-size: 13px; }}
  .empty {{ color: #888; font-style: italic; }}
  .card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px;
           padding: 16px; margin-bottom: 14px; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: baseline;
                margin-bottom: 8px; }}
  .card-head .to {{ font-weight: 600; font-size: 14px; }}
  .card-head .meta {{ font-size: 11px; color: #777; }}
  .subject {{ font-size: 13px; color: #333; margin-bottom: 10px; }}
  .body {{ white-space: pre-wrap; font-family: Menlo, Monaco, monospace;
           font-size: 12px; background: #f5f5f5; border-left: 3px solid #d0d0d0;
           padding: 8px 10px; margin: 8px 0; max-height: 240px; overflow-y: auto; }}
  .actions {{ margin-top: 10px; display: flex; gap: 8px; }}
  .actions form {{ display: inline; }}
  button {{ padding: 6px 14px; border: 1px solid #111; background: #fff;
            cursor: pointer; border-radius: 3px; font-size: 12px; }}
  button.approve {{ background: #0a7f2e; color: #fff; border-color: #0a7f2e; }}
  button.reject {{ background: #fff; color: #b00; border-color: #b00; }}
  input[type=text] {{ padding: 5px 8px; font-size: 12px; border: 1px solid #ccc;
                      border-radius: 3px; }}
  .tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px;
          font-size: 11px; margin-right: 4px; background: #eef; color: #335; }}
  .tag.mode-auto_send {{ background: #dfd; color: #060; }}
  .tag.mode-draft {{ background: #ffd; color: #740; }}
  .tag.mode-escalate {{ background: #fdd; color: #900; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px;
           background: #fff; margin-top: 8px; }}
  th, td {{ padding: 6px 8px; border-bottom: 1px solid #eee; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  td.status-sent {{ color: #0a7f2e; font-weight: 600; }}
  td.status-approved {{ color: #0a56a0; font-weight: 600; }}
  td.status-rejected {{ color: #b00; font-weight: 600; }}
  h2 {{ font-size: 14px; margin: 28px 0 6px 0; color: #444; }}
</style>
</head>
<body>

<h1>Pending reply drafts</h1>
<div class="sub">operator: {operator_email} · {pending_count} pending</div>

{flash_banner}

{pending_cards}

<h2>Recent drafts (approved / sent / rejected)</h2>
<table>
  <thead>
    <tr><th>Status</th><th>To</th><th>Subject</th><th>Mode</th><th>Created</th></tr>
  </thead>
  <tbody>
    {recent_rows}
  </tbody>
</table>

</body>
</html>
"""


_CARD_TEMPLATE = """
<div class="card">
  <div class="card-head">
    <div class="to">To: {to_email}</div>
    <div class="meta">{created}</div>
  </div>
  <div class="subject">Subject: {subject}</div>
  <div>
    <span class="tag mode-{reply_mode}">mode: {reply_mode}</span>
    <span class="tag">source: {mode_source}</span>
    <span class="tag">intent: {intent}</span>
    <span class="tag">conf: {confidence}</span>
    <span class="tag">package: {package}</span>
  </div>
  <div class="body">{body_text}</div>
  <div class="actions">
    <form method="post" action="/api/v1/operator/drafts/{draft_id}/approve">
      <button class="approve" type="submit">Approve &amp; send</button>
    </form>
    <form method="post" action="/api/v1/operator/drafts/{draft_id}/reject">
      <input type="text" name="reason" placeholder="Reject reason (optional)" size="40">
      <button class="reject" type="submit">Reject</button>
    </form>
  </div>
</div>
"""
