#!/usr/bin/env python3
"""检查双十一_90、母婴_3 是否真实存在于ES中"""

import os
import sys
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

ES_URL = os.getenv("ES_URL")
if not ES_URL:
    print("❌ 缺少 ES_URL 环境变量")
    sys.exit(1)

# 连接ES
es = Elasticsearch(ES_URL)
if not es.ping():
    print("❌ 无法连接到ES")
    sys.exit(1)

INDEX_NAME = "ad_stat_data"

# 要检查的广告主名称
advertiser_names_to_check = ["双十一_90", "母婴_3"]

for name in advertiser_names_to_check:
    print(f"\n🔍 检查广告主名称: {name}")

    # 搜索匹配
    query = {
        "query": {
            "term": {
                "advertiser_name.keyword": name
            }
        },
        "size": 1
    }

    try:
        result = es.search(index=INDEX_NAME, body=query)
        total = result["hits"]["total"]["value"]
        print(f"   匹配文档数: {total}")
        if total > 0:
            first_hit = result["hits"]["hits"][0]["_source"]
            print(f"   找到广告主ID: {first_hit.get('advertiser_id')}")
        else:
            # 尝试模糊匹配
            fuzzy_query = {
                "query": {
                    "match": {
                        "advertiser_name": name
                    }
                },
                "size": 5
            }
            fuzzy_result = es.search(index=INDEX_NAME, body=fuzzy_query)
            fuzzy_total = fuzzy_result["hits"]["total"]["value"]
            print(f"   模糊匹配找到 {fuzzy_total} 个文档")
            if fuzzy_total > 0:
                for hit in fuzzy_result["hits"]["hits"][:3]:
                    src = hit["_source"]
                    print(f"     - {src.get('advertiser_name')} (ID: {src.get('advertiser_id')})")
    except Exception as e:
        print(f"   查询错误: {e}")

print("\n✅ 检查完成")
