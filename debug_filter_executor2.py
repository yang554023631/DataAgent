#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor, FIELD_TO_DIM_INDEX, DIM_ID_FIELD

es = Elasticsearch(["http://localhost:9200"])

# Test directly: search for status=1, name like 'best', advertiser_id=6
# This is what filter executor should do
dim_index = "campaign"
field = "status"
value = 1
advertiser_ids = ["6"]

dim_id_field = "campaign_id"
must_clauses = []
must_clauses.append({"term": {"status": 1}})
must_clauses.append({"wildcard": {"campaign_name": "*best*"}})
must_clauses.append({"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}})

dsl_dim = {
    "query": {"bool": {"must": must_clauses}},
    "size": 1000,
}

response = es.search(index=dim_index, body=dsl_dim)
print(f"Got {response['hits']['total']['value']} hits:")
for hit in response['hits']['hits']:
    print(f"  campaign_id: {hit['_source']['campaign_id']}, name: {hit['_source']['campaign_name']}, status: {hit['_source']['status']}")
