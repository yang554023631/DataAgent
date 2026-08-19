#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Get all creative_ids from creative dimension table for advertiser 6
must = [{"terms": {"advertiser_id": [6]}}]
dsl = {
    "query": {"bool": {"must": must}},
    "size": 200,
}

response = es.search(index="creative", body=dsl)
creative_ids = []
for hit in response["hits"]["hits"]:
    cid = hit["_source"]["creative_id"]
    creative_ids.append(cid)

print(f"Total creatives for advertiser 6: {len(creative_ids)}")

# Now check doc count in fact table with these creative_ids
filters = [
    {"terms": {"advertiser_id": [6]}},
    {"terms": {"creative_id": creative_ids}},
    {"range": {"data_date": {"gte": "2000-01-01", "lte": "2026-08-17"}}}
]

dsl_count = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
}

response_count = es.search(index="ad_stat_data", body=dsl_count)
count = response_count["hits"]["total"]["value"]
print(f"Total docs in fact table: {count}")
