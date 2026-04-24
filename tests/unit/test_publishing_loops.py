"""Unit tests for publishing loop + measured-data loop closure."""


def test_auto_publish_task_registered():
    from workers.celery_app import app

    assert "workers.publishing_worker.tasks.auto_publish_approved_content" in app.tasks


def test_measured_data_cascade_task_registered():
    from workers.celery_app import app

    assert "workers.publishing_worker.tasks.run_measured_data_cascade" in app.tasks


def test_offer_learning_engine_exists():
    from packages.scoring.offer_learning_engine import compute_learned_offer_params

    r = compute_learned_offer_params("o1", 1.0, 0.02, 50.0, 100, 5, 200.0)
    assert r["updated"] is True
    assert r["learned_cvr"] != 0.02


def test_offer_learning_insufficient_sample():
    from packages.scoring.offer_learning_engine import compute_learned_offer_params

    r = compute_learned_offer_params("o1", 1.0, 0.02, 50.0, 10, 1, 20.0)
    assert r["updated"] is False
    assert "insufficient" in r["reason"].lower()


def test_tiered_routing_respects_platform_tier():
    from packages.scoring.tiered_routing_engine import classify_task_tier, route_to_provider

    tier = classify_task_tier("x")
    assert tier == "bulk"
    provider = route_to_provider("text", tier)
    assert provider == "deepseek"


def test_hero_routes_to_premium():
    from packages.scoring.tiered_routing_engine import classify_task_tier, route_to_provider

    tier = classify_task_tier("blog")
    assert tier == "hero"
    assert route_to_provider("text", tier) == "claude"
    assert route_to_provider("image", tier) == "gpt_image"
