import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import date
from models import QueryIntent, TimeRange, Filter

def test_query_intent_creation():
    intent = QueryIntent(
        time_range=TimeRange(
            start_date=date(2024, 4, 15),
            end_date=date(2024, 4, 21)
        ),
        metrics=["impressions", "clicks", "ctr"],
        group_by=["campaign_id"],
        filters=[Filter(field="audience_os", op="=", value=2)]
    )
    assert intent.metrics == ["impressions", "clicks", "ctr"]
    assert intent.filters[0].value == 2

def test_ambiguity_default():
    intent = QueryIntent(
        time_range=TimeRange(start_date=date(2024, 4, 15), end_date=date(2024, 4, 21)),
        metrics=["impressions"]
    )
    assert intent.ambiguity.has_ambiguity is False
