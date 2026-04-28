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
    """
    从用户输入中提取广告主（精确匹配模式）

    匹配规则：
    1. 广告主完整名称出现在输入中（如 "mini_6_autumn"）
    2. 广告主 ID 数字精确匹配
    """
    advertisers = get_all_advertisers()
    result = []
    import re

    for adv in advertisers:
        # 1. 完整名称精确匹配（有边界检查）
        if re.search(r'\b' + re.escape(adv["name"]) + r'\b', user_input):
            result.append(adv["id"])
            continue
        # 2. ID 精确匹配（有边界检查，避免 406 中的 4 被当成 ID 4）
        if re.search(r'\b' + re.escape(adv["id"]) + r'\b', user_input):
            result.append(adv["id"])

    return result


def get_similar_advertiser_names(input_text: str, top_n: int = 5) -> List[Dict[str, str]]:
    """
    获取与输入文本相似的广告主名称列表（用于拼写纠错/建议）

    使用多种匹配策略：
    - 前缀匹配
    - 子串包含
    - 共同字符比例
    """
    advertisers = get_all_advertisers()

    # 提取输入中的潜在广告主名称片段（支持中英文）
    import re
    tokens = re.findall(r'[a-zA-Z0-9_一-鿿]+', input_text)

    # 如果没有提取到 token（可能是纯符号或空格），用整个输入作为 fallback
    if not tokens:
        tokens = [input_text.strip()] if input_text.strip() else []

    candidates = []
    for adv in advertisers:
        score = 0
        name = adv["name"]

        # 1. 前缀匹配（输入是名称的前缀）
        for token in tokens:
            if len(token) >= 2 and name.startswith(token):
                score += 15
                break

        # 2. 输入是名称的子串（匹配度高）
        for token in tokens:
            if len(token) >= 2 and token in name:
                score += 8

        # 3. 名称是输入的子串（用户多输入了）
        if name in input_text:
            score += 10

        # 4. 共同字符集合匹配（处理拼写错误）
        input_chars = set(input_text.lower().replace(" ", ""))
        name_chars = set(name.lower())
        if len(input_chars) > 0 and len(name_chars) > 0:
            common_ratio = len(input_chars & name_chars) / max(len(input_chars), len(name_chars))
            # 中文输入时降低阈值到 20%，英文保持 30%
            import re
            has_chinese = bool(re.search(r'[一-鿿]', input_text))
            threshold = 0.2 if has_chinese else 0.3
            if common_ratio >= threshold:
                score += int(common_ratio * 10)

        if score > 0:
            candidates.append({"id": adv["id"], "name": adv["name"], "score": score})

    # 按分数排序并返回前 N 个
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_n]
