from elasticsearch import Elasticsearch
es = Elasticsearch(["http://localhost:9200"])

query = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [13]}},
            {"terms": {"advertiser_id": [6]}}
        ]
    }
}
result = es.search(index="ad_stat_data", query=query, size=5)
print(f"Total rows: {result['hits']['total']['value']}")
if result['hits']['hits']:
    print(f"First hit: {result['hits']['hits'][0]['_source']}")
