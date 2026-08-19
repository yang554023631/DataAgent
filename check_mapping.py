#!/usr/bin/env python3
import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_URL = os.getenv("ES_URL")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")

if ES_USER and ES_PASSWORD:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASSWORD))
else:
    es = Elasticsearch(ES_URL)

# 获取mapping
mapping = es.indices.get_mapping(index="campaign")
advertiser_id_mapping = mapping["campaign"]["mappings"]["properties"].get("advertiser_id")
print(f"campaign 索引 advertiser_id 字段mapping:")
print(advertiser_id_mapping)
