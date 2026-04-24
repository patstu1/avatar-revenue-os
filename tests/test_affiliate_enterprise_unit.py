"""Unit tests for enterprise affiliate engine."""
from packages.scoring.affiliate_enterprise_engine import (
    detect_partner_fraud,
    evaluate_governance,
    flag_risk,
    rank_merchants,
    rank_networks,
    score_partner,
)


class TestGovernance:
    def test_banned_merchant(self):
        v = evaluate_governance({"merchant_name": "BadCo", "product_category": "tech", "commission_rate": 10}, [], [{"entity_type": "merchant", "entity_name": "BadCo", "reason": "fraud"}])
        assert any(x["violation_type"] == "banned_merchant" for x in v)

    def test_banned_category(self):
        v = evaluate_governance({"merchant_name": "GoodCo", "product_category": "gambling", "commission_rate": 10}, [], [{"entity_type": "category", "entity_name": "gambling", "reason": "policy"}])
        assert any(x["violation_type"] == "banned_category" for x in v)

    def test_commission_too_high(self):
        v = evaluate_governance({"merchant_name": "X", "product_category": "tech", "commission_rate": 80}, [{"rule_type": "max_commission_rate", "rule_value": {"max": 50}}], [])
        assert any(x["violation_type"] == "commission_too_high" for x in v)

    def test_clean_offer(self):
        v = evaluate_governance({"merchant_name": "Good", "product_category": "tech", "commission_rate": 10, "approved": True}, [], [])
        assert len(v) == 0


class TestRiskFlags:
    def test_low_trust(self):
        f = flag_risk({"trust_score": 0.1, "refund_rate": 0, "epc": 1.0})
        assert any(x["risk_type"] == "low_trust" for x in f)

    def test_high_refund(self):
        f = flag_risk({"trust_score": 0.8, "refund_rate": 0.25, "epc": 2.0})
        assert any(x["risk_type"] == "high_refund" for x in f)

    def test_no_epc(self):
        f = flag_risk({"trust_score": 0.5, "refund_rate": 0, "epc": 0})
        assert any(x["risk_type"] == "no_epc_data" for x in f)

    def test_clean(self):
        f = flag_risk({"trust_score": 0.8, "refund_rate": 0.02, "epc": 3.0})
        assert len(f) == 0


class TestMerchantRanking:
    def test_ranks_by_performance(self):
        merchants = [{"id": "m1", "merchant_name": "A"}, {"id": "m2", "merchant_name": "B"}]
        offers = [{"merchant_id": "m1", "epc": 4.0, "trust_score": 0.8}, {"merchant_id": "m1", "epc": 3.0, "trust_score": 0.7}, {"merchant_id": "m2", "epc": 0.5, "trust_score": 0.3}]
        ranked = rank_merchants(merchants, offers)
        assert ranked[0]["merchant_name"] == "A"


class TestNetworkRanking:
    def test_ranks(self):
        networks = [{"id": "n1", "network_name": "Impact"}, {"id": "n2", "network_name": "CJ"}]
        merchants = [{"network_id": "n1"}, {"network_id": "n1"}, {"network_id": "n2"}]
        offers = [{"network_id": "n1"}, {"network_id": "n1"}, {"network_id": "n1"}]
        ranked = rank_networks(networks, offers, merchants)
        assert ranked[0]["network_name"] == "Impact"


class TestPartnerScoring:
    def test_good_partner(self):
        r = score_partner({"total_conversions": 100, "conversion_quality": 0.8, "fraud_risk": 0.05, "total_revenue_generated": 5000})
        assert r["partner_score"] > 0.5
        assert r["recommended_status"] == "active"

    def test_bad_partner(self):
        r = score_partner({"total_conversions": 2, "conversion_quality": 0.1, "fraud_risk": 0.8, "total_revenue_generated": 10})
        assert r["recommended_status"] in ("warning", "suppressed")


class TestFraudDetection:
    def test_detects_low_quality(self):
        convs = [{"quality_score": 0.1, "fraud_flag": False}] * 10
        flags = detect_partner_fraud(convs)
        assert any(f["fraud_type"] == "low_quality_ratio" for f in flags)

    def test_detects_flagged(self):
        convs = [{"quality_score": 0.8, "fraud_flag": True}]
        flags = detect_partner_fraud(convs)
        assert any(f["fraud_type"] == "flagged_conversions" for f in flags)

    def test_clean(self):
        convs = [{"quality_score": 0.9, "fraud_flag": False}] * 10
        assert detect_partner_fraud(convs) == []
