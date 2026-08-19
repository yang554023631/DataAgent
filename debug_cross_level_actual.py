#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Manual query for the dimension table to see what matches
must_clauses = []
# advertiser 6 filter
must_clauses.append({"terms": {"advertiser_id": [6]}})
# campaign_name like 'best'
must_clauses.append({"wildcard": {"campaign_name": "*best*"}})
# status = 1
must_clauses.append({"term": {"status": 1}})

dsl_dim = {
    "query": {"bool": {"must": must_clauses}},
    "size": 1000,
}

print("Querying campaign index with:")
print(f"  must_clauses: {must_clauses}")
print()

response = es.search(index="campaign", body=dsl_dim)

print(f"Total hits: {response['hits']['total']['value']}")
print()
for hit in response["hits"]["hits"]:
    print(f"  Hit: _id={hit['_id']}, campaign_id={hit['_source'].get('campaign_id')}, campaign_name={hit['_source'].get('campaign_name')}, status={hit['_source'].get('status')}")
