"""Autonomous Phase C — funnel, paid operator, sponsor, retention, recovery, self-healing (pure functions)."""
from __future__ import annotations

from typing import Any

APCE = "autonomous_phase_c_engine"


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Funnel runner
# ---------------------------------------------------------------------------

def compute_funnel_executions(brand_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Plan funnel actions from funnel health, traffic, and intent signals.

    brand_context keys:
      funnel_leak_score (0-1), high_intent_share (0-1), owned_list_growth (float),
      email_sequence_health (0-1), sms_enabled (bool), default_execution_mode (str)
    """
    leak = _clamp(float(brand_context.get("funnel_leak_score", 0.3)))
    intent = _clamp(float(brand_context.get("high_intent_share", 0.2)))
    list_growth = float(brand_context.get("owned_list_growth", 0.0))
    seq_health = _clamp(float(brand_context.get("email_sequence_health", 0.6)))
    sms = bool(brand_context.get("sms_enabled", False))
    default_mode = str(brand_context.get("default_execution_mode", "guarded"))

    actions: list[dict[str, Any]] = []

    if leak > 0.55:
        mode = "manual" if leak > 0.75 else default_mode
        actions.append({
            "funnel_action": "diagnose_and_patch_leak",
            "target_funnel_path": "landing → opt_in → nurture → offer",
            "cta_path": "primary_cta_variant_test",
            "capture_mode": "owned_audience" if intent < 0.45 else "direct_conversion",
            "execution_mode": mode,
            "expected_upside": round((leak - 0.3) * 12000, 2),
            "confidence": round(_clamp(0.5 + leak * 0.35), 4),
            "explanation": f"Elevated leak score {leak:.2f}: run variant test and sequence repair.",
            "diagnostics_json": {"leak_focus": "mid_funnel_drop", "recommended_fixes": ["headline", "social_proof", "form_fields"]},
            APCE: True,
        })

    if intent >= 0.35 and leak <= 0.5:
        actions.append({
            "funnel_action": "route_high_intent_concierge",
            "target_funnel_path": "content → application → concierge_call → close",
            "cta_path": "book_call_high_ticket",
            "capture_mode": "direct_conversion",
            "execution_mode": "guarded" if default_mode == "manual" else default_mode,
            "expected_upside": round(intent * 25000, 2),
            "confidence": round(_clamp(0.55 + intent * 0.3), 4),
            "explanation": f"High-intent share {intent:.2f}: eligible for concierge / high-ticket path.",
            "diagnostics_json": {"segment": "high_intent_clickers"},
            APCE: True,
        })

    if list_growth < 0.02 and leak < 0.5:
        actions.append({
            "funnel_action": "switch_to_owned_capture",
            "target_funnel_path": "content → lead_magnet → email_sequence → core_offer",
            "cta_path": "soft_cta_subscribe",
            "capture_mode": "owned_audience",
            "execution_mode": default_mode,
            "expected_upside": round(5000 + (0.02 - max(list_growth, 0)) * 200000, 2),
            "confidence": 0.62,
            "explanation": "List growth below target — prioritize owned-audience capture over hard sell.",
            "diagnostics_json": {"list_growth_weekly": list_growth},
            APCE: True,
        })

    if seq_health < 0.45:
        actions.append({
            "funnel_action": "trigger_sequence_repair",
            "target_funnel_path": "opt_in → welcome → value_nurture → pitch",
            "cta_path": "sequence_reactivation",
            "capture_mode": "owned_audience",
            "execution_mode": "guarded",
            "expected_upside": round((0.5 - seq_health) * 8000, 2),
            "confidence": round(_clamp(0.6 + (0.5 - seq_health)), 4),
            "explanation": f"Email/SMS sequence health {seq_health:.2f} — refresh copy and timing.",
            "diagnostics_json": {"channels": ["email"] + (["sms"] if sms else [])},
            APCE: True,
        })

    if not actions:
        actions.append({
            "funnel_action": "maintain_funnel",
            "target_funnel_path": "steady_state_conversion",
            "cta_path": "control",
            "capture_mode": "owned_audience",
            "execution_mode": default_mode,
            "expected_upside": 0.0,
            "confidence": 0.55,
            "explanation": "No critical funnel intervention required; monitor weekly.",
            "diagnostics_json": {},
            APCE: True,
        })

    return actions


# ---------------------------------------------------------------------------
# Paid operator (winners only)
# ---------------------------------------------------------------------------

def compute_paid_operator_runs(winners: list[dict[str, Any]], brand_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Create paid test packages for organic winners.

    winner dict: content_item_id (str|None), autonomous_run_id (str|None), engagement_score (float),
    revenue_proxy (float), days_since_publish (int)
    """
    default_mode = str(brand_context.get("default_execution_mode", "guarded"))
    budget_ceiling = float(brand_context.get("paid_budget_ceiling_daily", 500.0))

    runs: list[dict[str, Any]] = []
    for w in winners:
        eng = _clamp(float(w.get("engagement_score", 0)))
        rev = float(w.get("revenue_proxy", 0))
        days = int(w.get("days_since_publish", 7))

        if eng < 0.65 or rev < 50 or days > 21:
            continue

        if eng >= 0.85 and rev >= 200:
            band = "scale_band" if budget_ceiling >= 300 else "test_band"
            paid_action = "scale_paid_test"
            roi_est = round(1.2 + eng * 0.8, 2)
        elif eng >= 0.65:
            band = "safe_test_band"
            paid_action = "start_paid_test"
            roi_est = round(0.9 + eng * 0.5, 2)
        else:
            continue

        cac_est = round(max(15, 80 - eng * 60), 2)
        mode = "autonomous" if default_mode == "autonomous" and eng >= 0.82 else "guarded"

        runs.append({
            "paid_action": paid_action,
            "budget_band": band,
            "expected_cac": cac_est,
            "expected_roi": roi_est,
            "execution_mode": mode,
            "confidence": round(_clamp(0.5 + eng * 0.45), 4),
            "explanation": f"Winner eng={eng:.2f}, rev_proxy={rev:.0f}: packaged for {paid_action} ({band}).",
            "winner_score": round(eng * 0.6 + min(rev / 500, 1) * 0.4, 4),
            "content_item_id": w.get("content_item_id"),
            "autonomous_run_id": w.get("autonomous_run_id"),
            APCE: True,
        })

    return runs


def compute_paid_operator_decision(run_context: dict[str, Any], paid_performance: dict[str, Any]) -> dict[str, Any]:
    """Decide scale / stop / hold / budget_adjust from paid test metrics."""
    cpa = float(paid_performance.get("cpa_actual", 999))
    cpa_target = float(paid_performance.get("cpa_target", 50))
    spend = float(paid_performance.get("spend_7d", 0))
    conv = int(paid_performance.get("conversions_7d", 0))
    roi_actual = float(paid_performance.get("roi_actual", 0))

    if cpa > cpa_target * 1.4 or (spend > 200 and conv == 0):
        dtype = "stop"
        band = "paused"
        mode = "autonomous"
        expl = "Weak paid efficiency — auto-stop to protect budget."
    elif roi_actual >= 1.1 and cpa <= cpa_target:
        dtype = "scale"
        band = "scale_band"
        mode = "guarded"
        expl = "Strong ROI within CAC guardrails — scale with operator ceiling."
    elif spend > 400 and roi_actual < 0.8:
        dtype = "budget_adjust"
        band = "reduced_test_band"
        mode = "guarded"
        expl = "Trim budget pending creative refresh."
    else:
        dtype = "hold"
        band = "test_band"
        mode = "guarded"
        expl = "Hold for more signal before scale or stop."

    return {
        "decision_type": dtype,
        "budget_band": band,
        "expected_cac": round(min(cpa, cpa_target * 1.2), 2),
        "expected_roi": round(max(roi_actual, 0.5), 2),
        "execution_mode": mode,
        "confidence": 0.72 if dtype != "hold" else 0.55,
        "explanation": expl,
        APCE: True,
    }


# ---------------------------------------------------------------------------
# Sponsor autonomy
# ---------------------------------------------------------------------------

def compute_sponsor_autonomous_actions(brand_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Inventory build, packages, targets, sequences, renewals."""
    inv_score = _clamp(float(brand_context.get("sponsor_inventory_completeness", 0.4)))
    pipeline_depth = int(brand_context.get("sponsor_pipeline_count", 0))
    renewal_due = int(brand_context.get("sponsor_renewals_due_30d", 0))

    actions: list[dict[str, Any]] = []

    if inv_score < 0.7:
        actions.append({
            "sponsor_action": "build_inventory_slots",
            "package_json": {"tier": "standard", "slots": 6, "formats": ["integrated", "dedicated", "bundle"]},
            "target_category": "saas_b2b",
            "target_list_json": {"segments": ["martech", "creator_tools"], "min_followers": 10000},
            "pipeline_stage": "inventory",
            "expected_deal_value": round((0.7 - inv_score) * 50000, 2),
            "confidence": 0.68,
            "explanation": "Complete sponsor inventory matrix for outbound packaging.",
            APCE: True,
        })

    actions.append({
        "sponsor_action": "rank_categories",
        "package_json": {"method": "audience_overlap_x_margin"},
        "target_category": "priority_verticals",
        "target_list_json": {"ranked": ["productivity", "health", "finance"]},
        "pipeline_stage": "strategy",
        "expected_deal_value": 12000.0,
        "confidence": 0.61,
        "explanation": "Rank sponsor categories by audience fit and margin potential.",
        APCE: True,
    })

    actions.append({
        "sponsor_action": "generate_outreach_sequence",
        "package_json": {"steps": 4, "tone": "value_first"},
        "target_category": "cold_outreach",
        "target_list_json": {"template_id": "sponsor_v1", "personalization_fields": ["brand", "vertical"]},
        "pipeline_stage": "outreach",
        "expected_deal_value": 8000.0,
        "confidence": 0.58,
        "explanation": "Sequence for net-new sponsor prospects.",
        APCE: True,
    })

    if renewal_due > 0:
        actions.append({
            "sponsor_action": "surface_renewal_expansion",
            "package_json": {"upsell": "bundle_plus", "discount_cap_pct": 10},
            "target_category": "renewals",
            "target_list_json": {"renewals_due": renewal_due},
            "pipeline_stage": "renewal",
            "expected_deal_value": round(renewal_due * 3500, 2),
            "confidence": 0.74,
            "explanation": f"{renewal_due} renewals in window — auto-surface upsell pricing.",
            APCE: True,
        })

    if pipeline_depth < 5:
        actions.append({
            "sponsor_action": "expand_target_list",
            "package_json": {},
            "target_category": "pipeline_fill",
            "target_list_json": {"min_targets": 25},
            "pipeline_stage": "prospect",
            "expected_deal_value": 15000.0,
            "confidence": 0.55,
            "explanation": "Shallow pipeline — expand lookalike sponsor list.",
            APCE: True,
        })

    return actions


# ---------------------------------------------------------------------------
# Retention / LTV
# ---------------------------------------------------------------------------

def compute_retention_actions(cohort_signals: dict[str, Any]) -> list[dict[str, Any]]:
    """Churn risk, upsell, repeat buy, reactivation, referral, community."""
    churn_risk = _clamp(float(cohort_signals.get("churn_risk_score", 0.2)))
    upsell_window = _clamp(float(cohort_signals.get("upsell_window_score", 0)))
    repeat_window = _clamp(float(cohort_signals.get("repeat_purchase_window_score", 0)))
    ltv_tier = str(cohort_signals.get("ltv_tier", "mid"))

    out: list[dict[str, Any]] = []

    if churn_risk > 0.55:
        out.append({
            "retention_action": "reactivation_flow",
            "target_segment": "at_risk_active",
            "cohort_key": "churn_risk_high",
            "expected_incremental_value": round(churn_risk * 8000, 2),
            "confidence": round(0.5 + churn_risk * 0.35, 4),
            "explanation": "Trigger win-back sequence and offer adjustment.",
            APCE: True,
        })

    if upsell_window > 0.5:
        out.append({
            "retention_action": "upsell_next_tier",
            "target_segment": "good_fit_expandable",
            "cohort_key": "upsell_ready",
            "expected_incremental_value": round(upsell_window * 12000, 2),
            "confidence": round(0.55 + upsell_window * 0.3, 4),
            "explanation": "Upsell window open — move to higher-LTV SKU or bundle.",
            APCE: True,
        })

    if repeat_window > 0.45:
        out.append({
            "retention_action": "repeat_purchase_nudge",
            "target_segment": "repeat_buyers",
            "cohort_key": "replenish",
            "expected_incremental_value": round(repeat_window * 6000, 2),
            "confidence": 0.64,
            "explanation": "Replenish / consumable timing — nudge repurchase.",
            APCE: True,
        })

    if ltv_tier == "high" and churn_risk < 0.35:
        out.append({
            "retention_action": "referral_ask",
            "target_segment": "high_ltv_loyal",
            "cohort_key": "advocates",
            "expected_incremental_value": 4000.0,
            "confidence": 0.6,
            "explanation": "High-LTV stable cohort — referral and community invite.",
            APCE: True,
        })

    if not out:
        out.append({
            "retention_action": "monitor_only",
            "target_segment": "general",
            "cohort_key": None,
            "expected_incremental_value": 0.0,
            "confidence": 0.5,
            "explanation": "No strong retention trigger this cycle.",
            APCE: True,
        })

    return out


# ---------------------------------------------------------------------------
# Recovery + self-healing
# ---------------------------------------------------------------------------

def detect_recovery_incidents(signals: dict[str, Any]) -> list[dict[str, Any]]:
    """Map system signals to incident types and escalation needs."""
    incidents: list[dict[str, Any]] = []

    def add(itype: str, severity: str, esc: str, expl: str):
        incidents.append({
            "incident_type": itype,
            "severity": severity,
            "escalation_requirement": esc,
            "explanation": expl,
            APCE: True,
        })

    if signals.get("provider_failure"):
        add("provider_failure", "high", "operator_review", "Primary generation/publish provider failing.")
    if signals.get("publishing_failure_rate", 0) > 0.15:
        add("publishing_failures", "high", "operator_review", "Elevated publish failure rate.")
    if signals.get("conversion_drop_pct", 0) > 0.2:
        add("conversion_drop", "medium", "none", "Conversion dropped >20% vs baseline.")
    if signals.get("fatigue_spike", 0) > 0.25:
        add("fatigue_spike", "medium", "none", "Creative fatigue spike detected.")
    if signals.get("queue_congestion_score", 0) > 0.7:
        add("queue_congestion", "medium", "none", "Queue depth exceeds safe throughput.")
    if signals.get("budget_overspend_pct", 0) > 0.1:
        add("budget_overspend", "high", "immediate_operator", "Paid spend over plan >10%.")
    if signals.get("sponsor_underperformance"):
        add("sponsor_underperformance", "low", "none", "Sponsor delivery under benchmark.")
    if signals.get("account_stagnation"):
        add("account_stagnation", "low", "none", "Account growth flat vs peers.")
    if signals.get("weak_offer_economics"):
        add("weak_offer_economics", "medium", "operator_review", "Offer unit economics below floor.")

    return incidents


def compute_self_healing_action(incident: dict[str, Any]) -> dict[str, Any]:
    """Map incident to concrete self-healing response."""
    itype = str(incident.get("incident_type", "unknown"))
    severity = str(incident.get("severity", "medium"))

    routing: dict[str, tuple[str, str, str, str, float]] = {
        "provider_failure": ("reroute_provider", "guarded", "operator_review", "Restore throughput via backup provider", 0.75),
        "publishing_failures": ("retry_with_backoff", "guarded", "operator_review", "Reduce failure rate within 24h", 0.7),
        "conversion_drop": ("throttle_paid_and_test_funnel", "guarded", "none", "Stabilize CAC while patching funnel", 0.62),
        "fatigue_spike": ("suppress_output_rotate_creative", "autonomous", "none", "Refresh creative mix and cadence", 0.68),
        "queue_congestion": ("throttle_enqueue_split_queue", "autonomous", "none", "Relieve congestion via fair scheduling", 0.72),
        "budget_overspend": ("pause_spend_cap", "autonomous", "immediate_operator", "Halt spend until operator confirms", 0.85),
        "sponsor_underperformance": ("adjust_package_pitch", "guarded", "none", "Repackage inventory and targets", 0.55),
        "account_stagnation": ("shift_allocation_test_lane", "guarded", "none", "Reallocate to warmer account mix", 0.58),
        "weak_offer_economics": ("suppress_offer_queue_review", "guarded", "operator_review", "Pause scale until economics fixed", 0.65),
    }

    action, mode, esc, mit, conf = routing.get(
        itype,
        ("escalate_generic", "guarded", "operator_review", "Manual triage required", 0.5),
    )

    if severity == "high" and esc == "none":
        esc = "operator_review"

    return {
        "incident_type": itype,
        "action_taken": action,
        "action_mode": mode,
        "escalation_requirement": esc,
        "expected_mitigation": mit,
        "confidence": conf,
        "explanation": f"Self-healing for {itype}: {action} ({mode}).",
        APCE: True,
    }
