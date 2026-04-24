import uuid
from datetime import datetime, timedelta

from packages.scoring.expansion_pack2_phase_b_engines import (
    recommend_pricing,
    recommend_bundle,
    recommend_retention,
    recommend_reactivation_campaign,
)

def test_recommend_pricing():
    offer_id = uuid.uuid4()
    current_price = 100.0
    historical_sales_data = [
        {"price": 90.0, "quantity_sold": 100, "date": "2023-01-01"},
        {"price": 100.0, "quantity_sold": 90, "date": "2023-01-02"},
    ]
    market_data = [
        {"competitor_price": 105.0, "competitor_features": "A,B", "demand_level": 0.8},
        {"competitor_price": 95.0, "competitor_features": "C,D", "demand_level": 0.7},
    ]
    customer_segment_data = [
        {"segment_name": "early_adopters", "price_sensitivity": 0.7, "willingness_to_pay": 120.0},
        {"segment_name": "budget_buyers", "price_sensitivity": 0.9, "willingness_to_pay": 80.0},
    ]

    recommendation = recommend_pricing(
        offer_id,
        current_price,
        historical_sales_data,
        market_data,
        customer_segment_data,
    )

    assert "recommended_price" in recommendation
    assert isinstance(recommendation["recommended_price"], float)
    assert recommendation["recommended_price"] > 0
    assert "price_elasticity" in recommendation
    assert "estimated_revenue_impact" in recommendation
    assert "confidence" in recommendation
    assert "explanation" in recommendation
    assert recommendation["offer_id"] == str(offer_id)
    assert recommendation["recommendation_type"] in ("price_increase", "price_decrease", "anchor_reprice", "hold")
    assert recommendation["current_price"] == current_price

def test_recommend_bundle():
    offer1_id = uuid.uuid4()
    offer2_id = uuid.uuid4()
    offer3_id = uuid.uuid4()
    available_offers = [
        {"id": str(offer1_id), "name": "Offer A", "price": 50.0, "features": ["X"]},
        {"id": str(offer2_id), "name": "Offer B", "price": 70.0, "features": ["Y"]},
        {"id": str(offer3_id), "name": "Offer C", "price": 30.0, "features": ["Z"]},
    ]
    customer_purchase_history = [
        {"customer_id": "cust1", "purchased_offer_ids": [str(offer1_id)]},
    ]
    market_trends = [
        {"trend_name": "popular_combos", "popular_bundles": [[str(offer1_id), str(offer2_id)]]},
    ]

    recommendation = recommend_bundle(
        available_offers,
        customer_purchase_history,
        market_trends,
    )

    assert "bundle_name" in recommendation
    assert "offer_ids" in recommendation
    assert isinstance(recommendation["offer_ids"], list)
    assert len(recommendation["offer_ids"]) > 0
    assert "recommended_bundle_price" in recommendation
    assert isinstance(recommendation["recommended_bundle_price"], float)
    assert recommendation["recommended_bundle_price"] > 0
    assert "estimated_upsell_rate" in recommendation
    assert "estimated_revenue_impact" in recommendation
    assert "confidence" in recommendation
    assert "explanation" in recommendation

def test_recommend_bundle_no_offers():
    recommendation = recommend_bundle([], [], [])
    assert recommendation["bundle_name"] == "No Bundle Recommended"
    assert recommendation["offer_ids"] == []
    assert recommendation["recommended_bundle_price"] == 0.0

def test_recommend_retention():
    customer_id = uuid.uuid4()
    customer_behavior_data = [
        {"activity_level": "high", "last_purchase_date": "2024-01-01"},
    ]
    churn_risk_score = 0.85
    available_retention_offers = [
        {"offer_id": str(uuid.uuid4()), "type": "discount", "discount": 0.1},
    ]

    recommendation = recommend_retention(
        customer_id,
        customer_behavior_data,
        churn_risk_score,
        available_retention_offers,
    )

    assert "customer_segment" in recommendation
    assert "recommendation_type" in recommendation
    assert "action_details" in recommendation
    assert "estimated_retention_lift" in recommendation
    assert isinstance(recommendation["estimated_retention_lift"], float)
    assert "confidence" in recommendation
    assert "explanation" in recommendation
    assert recommendation["customer_segment"] == "critical_churn_risk"

def test_recommend_reactivation_campaign():
    lapsed_customer_segment = [
        {"segment_name": "lapsed_customers", "last_activity_days_ago": 90},
    ]
    historical_campaign_performance = [
        {"campaign_type": "email_series", "reactivation_rate": 0.03},
    ]
    available_campaign_types = ["email_series", "discount_offer"]

    campaign = recommend_reactivation_campaign(
        lapsed_customer_segment,
        historical_campaign_performance,
        available_campaign_types,
    )

    assert "campaign_name" in campaign
    assert "target_segment" in campaign
    assert "campaign_type" in campaign
    assert "start_date" in campaign
    assert "end_date" in campaign
    assert "estimated_reactivation_rate" in campaign
    assert isinstance(campaign["estimated_reactivation_rate"], float)
    assert "estimated_revenue_impact" in campaign
    assert "confidence" in campaign
    assert "explanation" in campaign
    assert campaign["target_segment"] == "lapsed_customers"
    assert campaign["campaign_type"] == "email_series"
