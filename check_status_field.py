#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check what status values exist for campaign_id=13
query = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [13]}},
            {"terms": {"advertiser_id": [6]}}
        ]
    }
}
result = es.search(index="ad_stat_data", query=query, size=10)
print(f"Total hits: {result['hits']['total']['value']}")
print()

# Check what status values are present
status_values = {}
for hit in result['hits']['hits']:
    source = hit['_source']
    status = source.get('status')
    if status not in status_values:
        status_values[status] = 0
    status_values[status] += 1

print(f"Unique status values found: {status_values}")
print()

# Now check if any documents have status=1 with term query
query2 = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [13]}},
            {"terms": {"advertiser_id": [6]}},
            {"term": {"status": 1}}
        ]
    }
}
result2 = es.search(index="ad_stat_data", query=query2, size=5)
print(f"With term query status=1: {result2['hits']['total']['value']} hits")

# Also check with match query
query3 = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [13]}},
            {"terms": {"advertiser_id": [6]}},
            {"match": {"status": 1}}
        ]
    }
}
result3 = es.search(index="ad_stat_data", query=query3, size=5)
print(f"With match query status=1: {result3['hits']['total']['value']} hits")

# Check if status is stored as string instead of integer
query4 = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [13]}},
            {"terms": {"advertiser_id": [6]}},
            {"term": {"status": "1"}}
        ]
    }
}
result4 = es.search(index="ad_stat_data", query=query4, size=5)
print(f"With term query status='1' (string): {result4['hits']['total']['value']} hits")
