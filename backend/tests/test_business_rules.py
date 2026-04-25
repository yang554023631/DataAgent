from src.tools.business_rules import apply_business_rules

def test_apply_business_rules_no_audience():
    intent = {
        "group_by": ["campaign_id"],
        "filters": []
    }
    result = apply_business_rules.func(intent)
    assert result["index_type"] == "general"
    assert len(result["filters"]) == 0

def test_apply_business_rules_audience_os():
    intent = {
        "group_by": ["audience_os"],
        "filters": []
    }
    result = apply_business_rules.func(intent)
    assert result["index_type"] == "audience"
    assert len(result["filters"]) == 1
    assert result["filters"][0]["field"] == "audience_type"
    assert result["filters"][0]["value"] == 3

def test_apply_business_rules_audience_gender():
    intent = {
        "group_by": ["audience_gender"],
        "filters": []
    }
    result = apply_business_rules.func(intent)
    assert result["filters"][0]["value"] == 1
