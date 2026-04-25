from typing import List, Dict, Any
from elasticsearch import Elasticsearch

# ES 客户端
es_client = Elasticsearch(["http://localhost:9200"])


def get_all_advertisers() -> List[Dict[str, str]]:
    """获取所有可用的广告主列表（从 ES）"""
    try:
        response = es_client.search(
            index="advertiser",
            query={"term": {"is_deleted": 0}},
            size=100,
            sort=[{"advertiser_id": "asc"}]
        )
        return [
            {
                "id": str(hit["_source"]["advertiser_id"]),
                "name": hit["_source"]["advertiser_name"]
            }
            for hit in response["hits"]["hits"]
        ]
    except Exception as e:
        print(f"Error fetching advertisers: {e}")
        return []


def get_advertiser_by_id(advertiser_id: str) -> Dict[str, str]:
    """根据 ID 获取广告主信息"""
    try:
        adv_id = int(advertiser_id) if isinstance(advertiser_id, str) else advertiser_id
        response = es_client.search(
            index="advertiser",
            query={"bool": {"must": [
                {"term": {"advertiser_id": adv_id}},
                {"term": {"is_deleted": 0}}
            ]}}
        )
        if response["hits"]["total"]["value"] > 0:
            source = response["hits"]["hits"][0]["_source"]
            return {
                "id": str(source["advertiser_id"]),
                "name": source["advertiser_name"]
            }
    except Exception as e:
        print(f"Error fetching advertiser by id: {e}")
    return None


def get_advertiser_by_name(name_keyword: str) -> List[Dict[str, str]]:
    """根据名称关键词搜索广告主"""
    try:
        response = es_client.search(
            index="advertiser",
            query={"bool": {"must": [
                {"match": {"advertiser_name": name_keyword}},
                {"term": {"is_deleted": 0}}
            ]}}
        )
        return [
            {
                "id": str(hit["_source"]["advertiser_id"]),
                "name": hit["_source"]["advertiser_name"]
            }
            for hit in response["hits"]["hits"]
        ]
    except Exception as e:
        print(f"Error searching advertiser: {e}")
        return []


def is_advertiser_list_query(user_input: str) -> bool:
    """判断用户是否在询问广告主列表"""
    # 先检查是否已指定具体广告主，如果是则不触发列表
    if extract_advertiser_from_input(user_input):
        return False

    list_keywords = ["有哪些", "列表", "选哪个", "选哪些", "哪些可", "可用的", "都有什么"]
    # 只有当没有具体广告主，且有列表查询关键词时才认为是列表查询
    return any(keyword in user_input for keyword in list_keywords)


def extract_advertiser_from_input(user_input: str) -> List[str]:
    """从用户输入中提取广告主 ID 或名称"""
    advertisers = get_all_advertisers()
    result = []

    for adv in advertisers:
        # 1. 完整名称出现在输入中
        if adv["name"] in user_input:
            result.append(adv["id"])
            continue
        # 2. 输入中的关键词是广告主名的前缀（支持模糊匹配）
        # 例如：输入"六一八智能"匹配"六一八智能_406"
        adv_name_parts = adv["name"].split("_")
        if any(part and part in user_input and len(part) >= 4 for part in adv_name_parts):
            result.append(adv["id"])
            continue
        # 3. ID 需要边界检查（避免 406 中的 4 被当成 ID 4）
        import re
        if re.search(r'\b' + re.escape(adv["id"]) + r'\b', user_input):
            result.append(adv["id"])

    return result
