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

# full mapping
mapping = es.indices.get_mapping(index="campaign")
props = mapping["campaign"]["mappings"]["properties"]
print("campaign 索引完整mapping:")
for field, mapping in props.items():
    if "type" in mapping:
        print(f"  {field}: {mapping['type']}")
