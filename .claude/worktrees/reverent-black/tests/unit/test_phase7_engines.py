"""Unit tests for Phase 7 engines: sponsor, comment-cash, knowledge graph, roadmap, capital."""

from packages.scoring.phase7_engines import (
    is_sponsor_safe,
    recommend_sponsor_packages,
    classify_comment_intent,
    extract_comment_cash_signals,
    build_knowledge_graph_entries,
    generate_roadmap,
    compute_capital_allocation,
)


def test_sponsor_safe_finance():
    safe, reason = is_sponsor_safe("personal finance")
    assert safe is True


def test_sponsor_unsafe_gambling():
    safe, reason = is_sponsor_safe("online gambling tips")
    assert safe is False
    assert "gambling" in reason.lower()


def test_sponsor_packages_with_audience():
    accts = [{"platform": "youtube", "follower_count": 15000}, {"platform": "tiktok", "follower_count": 30000}]
    pkgs = recommend_sponsor_packages("finance", accts, 5000.0, 100000)
    assert len(pkgs) >= 2
    names = {p["package"] for p in pkgs}
    assert "sponsored_integration" in names
    assert "multi_platform_bundle" in names


def test_sponsor_packages_cold_start():
    pkgs = recommend_sponsor_packages("finance", [{"platform": "youtube", "follower_count": 500}], 0, 0)
    assert len(pkgs) >= 1
    assert pkgs[0]["package"] == "growth_milestone"


def test_comment_intent_purchase():
    r = classify_comment_intent("Where can I buy this? Drop the link please!")
    assert r["is_purchase_intent"] is True
    assert r["intent"] == "purchase_intent"


def test_comment_intent_objection():
    r = classify_comment_intent("This is too expensive and not worth it")
    assert r["is_objection"] is True
    assert r["intent"] == "objection"


def test_comment_intent_question():
    r = classify_comment_intent("Does this work for beginners?")
    assert r["is_question"] is True
    assert r["intent"] == "question"


def test_comment_intent_neutral():
    r = classify_comment_intent("Great video, thanks for sharing")
    assert r["intent"] == "neutral"


def test_comment_cash_signals_purchase_cluster():
    comments = [
        {"comment_text": "where can i buy this", "is_purchase_intent": True, "is_question": False},
        {"comment_text": "link please", "is_purchase_intent": True, "is_question": False},
        {"comment_text": "nice video", "is_purchase_intent": False, "is_question": False},
    ]
    offers = [{"id": "o1", "epc": 3.0, "payout_amount": 40.0}]
    signals = extract_comment_cash_signals(comments, offers)
    assert any(s["signal_type"] == "purchase_intent_cluster" for s in signals)


def test_knowledge_graph_builds_nodes_and_edges():
    nodes, edges = build_knowledge_graph_entries(
        "finance",
        [{"platform": "youtube", "geography": "US"}],
        [{"id": "o1", "name": "Offer 1", "epc": 2.0}],
        [{"content_id": "c1", "title": "Best video", "win_score": 0.8, "platform": "youtube", "rpm": 12.0}],
        [{"name": "Core segment"}],
        [],
    )
    assert len(nodes) >= 3
    assert len(edges) >= 2
    types = {n["node_type"] for n in nodes}
    assert "niche" in types
    assert "platform" in types
    assert "offer" in types


def test_knowledge_graph_no_duplicate_nodes():
    nodes, edges = build_knowledge_graph_entries(
        "finance",
        [{"platform": "youtube", "geography": "US"}, {"platform": "youtube", "geography": "US"}],
        [], [], [], [],
    )
    platform_nodes = [n for n in nodes if n["node_type"] == "platform" and n["label"] == "youtube"]
    assert len(platform_nodes) == 1


def test_roadmap_includes_winner_clones():
    items = generate_roadmap(
        "finance",
        [{"platform": "youtube"}],
        [{"id": "o1"}],
        [{"content_id": "c1", "title": "Top video", "win_score": 0.9, "revenue": 500}],
        [], [], [], None, 70.0,
    )
    assert any("clone winner" in i["title"].lower() for i in items)


def test_roadmap_includes_leak_fix():
    items = generate_roadmap(
        "finance", [], [], [],
        [{"leak_type": "high_views_low_clicks", "estimated_leaked_revenue": 200, "estimated_recoverable": 100, "recommended_fix": "Fix hooks", "root_cause": "CTR low"}],
        [], [], None, 70.0,
    )
    assert any("fix leak" in i["title"].lower() for i in items)


def test_roadmap_capped_at_10():
    items = generate_roadmap(
        "finance",
        [{"platform": "youtube"}] * 5,
        [{"id": f"o{i}"} for i in range(5)],
        [{"content_id": f"c{i}", "title": f"Win {i}", "win_score": 0.8, "revenue": 300} for i in range(10)],
        [{"leak_type": "leak", "estimated_leaked_revenue": 50, "estimated_recoverable": 20, "recommended_fix": "Fix", "root_cause": "Bug"} for _ in range(5)],
        [], [{"target_geography": "EU", "target_language": "en", "estimated_revenue_potential": 1000, "rationale": "Expand"}],
        "add_experimental_account", 40.0,
    )
    assert len(items) <= 10


def test_capital_allocation_9_targets():
    allocs = compute_capital_allocation(
        total_budget=1000, total_revenue=5000, total_profit=2000,
        accounts=[{"platform": "youtube"}], offers=[{"id": "o1"}],
        leak_count=2, paid_candidate_count=1, geo_rec_count=1,
        trust_avg=60, scale_rec_key="add_experimental_account",
    )
    assert len(allocs) == 9
    types = {a["allocation_target_type"] for a in allocs}
    assert "content_volume" in types
    assert "paid_amplification" in types
    assert "funnel_optimization" in types
    assert "new_accounts" in types
    assert "sponsor_outreach" in types
    assert "geo_language_expansion" in types
    assert "productization" in types
    assert "owned_audience_nurture" in types
    assert "reserve" in types
    total_pct = sum(a["recommended_allocation_pct"] for a in allocs)
    assert 99.0 <= total_pct <= 101.0


def test_capital_allocation_leak_heavy_shifts_to_funnel():
    base = compute_capital_allocation(1000, 5000, 2000, [{"platform": "yt"}], [{"id": "o1"}], 0, 0, 0, 70, None)
    heavy = compute_capital_allocation(1000, 5000, 2000, [{"platform": "yt"}], [{"id": "o1"}], 10, 0, 0, 70, None)
    base_funnel = next(a["recommended_allocation_pct"] for a in base if a["allocation_target_type"] == "funnel_optimization")
    heavy_funnel = next(a["recommended_allocation_pct"] for a in heavy if a["allocation_target_type"] == "funnel_optimization")
    assert heavy_funnel > base_funnel
