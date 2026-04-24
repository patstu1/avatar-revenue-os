"""Revenue Ceiling Phase A engines — pure functions for ladders, audience, sequences, funnel."""

from __future__ import annotations

import hashlib
from typing import Any


def _stable_hash(s: str) -> int:
    """Deterministic hash bucket, stable across processes."""
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


RC_PHASE_A = "revenue_ceiling_phase_a"


FUNNEL_STAGES = [
    "click",
    "landing",
    "opt_in",
    "lead_confirmation",
    "email_open",
    "email_click",
    "sales_page_view",
    "checkout_start",
    "purchase",
    "upsell",
    "retention_event",
    "repeat_purchase",
]

SEQUENCE_TYPES = [
    "welcome",
    "nurture",
    "objection_handling",
    "conversion",
    "upsell",
    "reactivation",
    "sponsor_safe",
]

OWNED_ASSET_TYPES = [
    "newsletter",
    "lead_magnet",
    "waitlist",
    "sms_opt_in",
    "community",
    "remarketing",
]

LEAK_TYPES = [
    "weak_landing_headline",
    "weak_above_fold_clarity",
    "cta_mismatch",
    "weak_offer_positioning",
    "weak_trust_proof",
    "too_much_friction",
    "poor_form_conversion",
    "checkout_abandonment",
    "weak_upsell_order",
    "low_repeat_conversion",
    "wrong_audience_wrong_funnel",
]


def build_offer_ladder_for_opportunity(
    opportunity_key: str,
    offer_name: str,
    content_title: str,
    epc: float,
    cvr: float,
    aov: float,
    content_item_id: str | None = None,
    offer_id: str | None = None,
) -> dict[str, Any]:
    """One offer ladder row from opportunity + economics."""
    first_val = round(epc * cvr * 100, 2)
    downstream = round(first_val * 2.2, 2)
    ltv = round(first_val * 3.5 + aov * cvr * 0.15, 2)
    friction = "low" if cvr > 0.02 else ("high" if cvr < 0.008 else "medium")
    conf = min(0.95, 0.45 + cvr * 15 + min(0.3, epc / 50))

    return {
        "opportunity_key": opportunity_key,
        "content_item_id": content_item_id,
        "offer_id": offer_id,
        "top_of_funnel_asset": f"Short-form video / post: {content_title[:80]}",
        "first_monetization_step": f"Primary CTA → {offer_name} (affiliate / lead)",
        "second_monetization_step": "Email nurture → tripwire or core offer",
        "upsell_path": {"steps": ["order bump", "core product", "coaching upsell"]},
        "retention_path": {"steps": ["onboarding email", "community", "newsletter value loop"]},
        "fallback_path": {"steps": ["lead magnet", "waitlist", "remarketing"]}
        if cvr < 0.015
        else {"steps": ["direct checkout retarget"]},
        "ladder_recommendation": f"Prioritize {offer_name} with {'capture-first' if cvr < 0.012 else 'direct-sale'} emphasis.",
        "expected_first_conversion_value": first_val,
        "expected_downstream_value": downstream,
        "expected_ltv_contribution": ltv,
        "friction_level": friction,
        "confidence": round(conf, 3),
        "explanation": f"EPC {epc:.2f}, CVR {cvr:.4f}, AOV {aov:.2f} — ladder balances immediate and LTV.",
        RC_PHASE_A: True,
    }


def generate_offer_ladders(brand_niche: str, offers: list[dict], content_items: list[dict]) -> list[dict]:
    """Produce one ladder per offer × content pairing (capped)."""
    out: list[dict] = []
    for i, o in enumerate(offers[:8]):
        if not content_items:
            key = f"offer:{o.get('id', i)}|no_content"
            out.append(
                build_offer_ladder_for_opportunity(
                    key,
                    o.get("name", "Offer"),
                    "Flagship slot",
                    float(o.get("epc", 1)),
                    float(o.get("conversion_rate", 0.02)),
                    float(o.get("average_order_value", 40)),
                    offer_id=str(o.get("id")),
                )
            )
            continue
        for j, ci in enumerate(content_items[:15]):
            key = f"offer:{o.get('id', i)}|content:{ci.get('id', j)}"
            out.append(
                build_offer_ladder_for_opportunity(
                    key,
                    o.get("name", "Offer"),
                    ci.get("title", "Content"),
                    float(o.get("epc", 1)),
                    float(o.get("conversion_rate", 0.02)),
                    float(o.get("average_order_value", 40)),
                    content_item_id=str(ci.get("id")),
                    offer_id=str(o.get("id")),
                )
            )
    if not out and offers:
        o = offers[0]
        out.append(
            build_offer_ladder_for_opportunity(
                f"default|{brand_niche}",
                o.get("name", "Primary"),
                "Flagship content",
                float(o.get("epc", 1)),
                float(o.get("conversion_rate", 0.02)),
                float(o.get("average_order_value", 40)),
            )
        )
    return out


def owned_audience_objective_for_family(content_family: str, direct_sale_score: float) -> str:
    """direct_sale_score 0..1; higher = better for direct sale."""
    if direct_sale_score > 0.62:
        return "direct_sale"
    if direct_sale_score < 0.38:
        return "owned_capture"
    return "hybrid"


def generate_owned_audience_assets(brand_niche: str, content_families: list[str]) -> list[dict]:
    """CTA variants and objectives per asset type."""
    families = content_families or ["general", "how_to", "story", "review"]
    out: list[dict] = []
    for atype in OWNED_ASSET_TYPES:
        for fam in families[:4]:
            dvc = 0.45 + (_stable_hash(f"{atype}{fam}") % 40) / 100.0
            obj = {fam: owned_audience_objective_for_family(fam, dvc)}
            ctas = [
                f"Get the free {brand_niche} checklist — {fam.replace('_', ' ')}",
                f"Join the waitlist for our {fam} playbook",
                "SMS 'SCALE' for the bonus module",
            ]
            out.append(
                {
                    "asset_type": atype,
                    "channel_name": f"{atype.replace('_', ' ').title()} — {fam}",
                    "content_family": fam,
                    "objective_per_family": obj,
                    "cta_variants": ctas,
                    "estimated_channel_value": round(1200 + dvc * 4000, 2),
                    "direct_vs_capture_score": round(dvc, 3),
                    RC_PHASE_A: True,
                }
            )
    return out


def synthesize_owned_audience_events(content_items: list[dict], asset_ids: list[str]) -> list[dict]:
    """Link content to opt-in events for tracking (synthetic from engine)."""
    events: list[dict] = []
    for i, ci in enumerate(content_items[:20]):
        aid = asset_ids[i % len(asset_ids)] if asset_ids else None
        events.append(
            {
                "content_item_id": str(ci.get("id")),
                "asset_id": aid,
                "event_type": "lead_magnet_signup" if i % 3 else "newsletter_capture",
                "value_contribution": round(15 + (i % 5) * 3.2, 2),
                "source_metadata": {"content_title": ci.get("title", ""), "engine": RC_PHASE_A},
            }
        )
    return events


def build_sequence(
    sequence_type: str,
    channel: str,
    brand_voice: str,
    sponsor_safe: bool = False,
) -> tuple[dict, list[dict]]:
    """Returns (sequence_meta, steps)."""
    title = f"{sequence_type.replace('_', ' ').title()} — {channel}"
    steps: list[dict] = []
    templates = {
        "welcome": [
            ("Thanks for joining — here's what to expect", "Day 0 value: quick win in {{niche}}."),
            ("Proof + story", "Why we built this and who it's for."),
            ("Soft CTA", "Explore the resource library."),
        ],
        "nurture": [
            ("Education 1", "Framework overview."),
            ("Education 2", "Common mistakes."),
            ("Case study", "Results snapshot."),
        ],
        "objection_handling": [
            ("Objection: time", "15-min implementation path."),
            ("Objection: trust", "Guarantee + social proof."),
            ("Objection: price", "ROI math."),
        ],
        "conversion": [
            ("Offer reveal", "Full stack and bonuses."),
            ("Urgency (ethical)", "Deadline or capacity."),
            ("FAQ", "Last questions."),
        ],
        "upsell": [
            ("Congrats", "You're in — next step."),
            ("Upsell A", "Complement product."),
            ("Upsell B", "Community / coaching."),
        ],
        "reactivation": [
            ("We miss you", "What's changed."),
            ("Win back offer", "Limited incentive."),
            ("Sunset or pause", "Preference center."),
        ],
        "sponsor_safe": [
            ("Sponsor mention", "Partner message per disclosure guidelines."),
            ("Value first", "Editorial then sponsor."),
            ("Opt-out", "Manage preferences."),
        ],
    }
    body_sets = templates.get(sequence_type, templates["nurture"])
    for idx, (subj, body) in enumerate(body_sets):
        if channel == "hybrid":
            step_ch = "sms" if idx % 2 else "email"
        elif channel == "sms":
            step_ch = "sms"
        else:
            step_ch = "email"
        steps.append(
            {
                "step_order": idx + 1,
                "channel": step_ch,
                "subject_or_title": subj + (" *Sponsor" if sponsor_safe and sequence_type == "sponsor_safe" else ""),
                "body_template": body + f" [{brand_voice}]",
                "delay_hours_after_previous": 0 if idx == 0 else 24 + idx * 12,
            }
        )
    meta = {
        "sequence_type": sequence_type,
        "channel": channel,
        "title": title,
        "sponsor_safe": sponsor_safe or sequence_type == "sponsor_safe",
    }
    return meta, steps


def generate_all_message_sequences(brand_voice: str = "helpful expert") -> list[tuple[dict, list[dict]]]:
    out: list[tuple[dict, list[dict]]] = []
    channels = ["email", "sms", "hybrid"]
    for st in SEQUENCE_TYPES:
        ch = channels[_stable_hash(st) % 3]
        sponsor = st == "sponsor_safe"
        out.append(build_sequence(st, ch, brand_voice, sponsor_safe=sponsor))
    return out


def compute_funnel_stage_metrics(
    content_family: str,
    base_rates: dict[str, float] | None = None,
) -> list[dict]:
    """Synthetic stage conversion chain 0..1."""
    br = base_rates or {}
    stages = FUNNEL_STAGES
    prev = 1.0
    metrics: list[dict] = []
    multipliers = {
        "click": 1.0,
        "landing": 0.85,
        "opt_in": 0.25,
        "lead_confirmation": 0.9,
        "email_open": 0.35,
        "email_click": 0.12,
        "sales_page_view": 0.55,
        "checkout_start": 0.18,
        "purchase": 0.45,
        "upsell": 0.22,
        "retention_event": 0.4,
        "repeat_purchase": 0.15,
    }
    for st in stages:
        m = multipliers.get(st, 0.5) * prev * (0.9 + br.get(st, 0.05))
        prev = m
        metrics.append(
            {
                "content_family": content_family,
                "stage": st,
                "metric_value": round(min(1.0, m), 6),
                "sample_size": 100 + _stable_hash(st + content_family) % 500,
            }
        )
    return metrics


def detect_funnel_leaks(
    stage_metrics: list[dict],
    content_family: str,
) -> list[dict]:
    """Heuristic leaks from stage drop-offs."""
    by_stage = {m["stage"]: m["metric_value"] for m in stage_metrics}
    leaks: list[dict] = []

    def add(leak_type: str, stage: str, cause: str, fix: str, upside: float, sev: str, urg: float, conf: float):
        leaks.append(
            {
                "leak_type": leak_type,
                "severity": sev,
                "affected_funnel_stage": stage,
                "affected_content_family": content_family,
                "suspected_cause": cause,
                "recommended_fix": fix,
                "expected_upside": upside,
                "confidence": conf,
                "urgency": urg,
            }
        )

    if by_stage.get("landing", 1) < 0.5:
        add(
            "weak_above_fold_clarity",
            "landing",
            "Low engagement after click",
            "Rewrite headline + subhead for one promise",
            800,
            "high",
            78,
            0.72,
        )
    if by_stage.get("opt_in", 1) < 0.2:
        add(
            "poor_form_conversion",
            "opt_in",
            "Friction or mismatch vs ad",
            "Reduce fields; align CTA to creative",
            1200,
            "high",
            82,
            0.68,
        )
    if (
        by_stage.get("checkout_start", 0) > 0.1
        and by_stage.get("purchase", 0) / max(0.001, by_stage.get("checkout_start", 1)) < 0.35
    ):
        add(
            "checkout_abandonment",
            "purchase",
            "Trust or price shock",
            "Add trust badges, payment options, guarantee near CTA",
            1500,
            "high",
            75,
            0.65,
        )
    if by_stage.get("email_open", 1) < 0.25:
        add(
            "weak_trust_proof",
            "email_open",
            "Subject line fatigue",
            "Test curiosity + specificity; segment list",
            400,
            "medium",
            55,
            0.55,
        )
    if by_stage.get("repeat_purchase", 1) < 0.08:
        add(
            "low_repeat_conversion",
            "repeat_purchase",
            "No retention loop",
            "Post-purchase sequence + community",
            600,
            "medium",
            60,
            0.58,
        )
    if not leaks:
        add(
            "weak_offer_positioning",
            "sales_page_view",
            "Generic value prop",
            "Tie offer to one outcome metric",
            500,
            "low",
            40,
            0.5,
        )
    return leaks
