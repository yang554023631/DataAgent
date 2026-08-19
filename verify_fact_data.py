from elasticsearch import Elasticsearch
es = Elasticsearch(["http://localhost:9200"])

query1 = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [14]}}
        ]
    }
}
result = es.search(index="ad_stat_data", query=query1, size=10)
print(f"Total with just campaign_id=14: {result['hits']['total']['value']}")

query2 = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [14]}},
            {"terms": {"advertiser_id": [6]}}
        ]
    }
}
result2 = es.search(index="ad_stat_data", query=query2, size=10)
print(f"Total with campaign_id=14 AND advertiser_id=6: {result2['hits']['total']['value']}")
if result2["hits"]["hits"]:
    print(f"First hit: {result2['hits']['hits'][0]['_source']}")
