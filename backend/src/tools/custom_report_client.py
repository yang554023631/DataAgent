import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from src.models import QueryRequest, QueryResult
from src.mcp.config import mcp_config
from src.main import mcp_manager

# 根据配置选择 MCP 或直连
if mcp_config.use_mcp and mcp_manager is not None:
    # 使用 MCP 客户端
    from src.search.elasticsearch_mcp import get_elasticsearch_mcp_client
    _es_mcp_client = get_elasticsearch_mcp_client(mcp_manager)

    class EsClientProxy:
        """MCP 模式下的 ES 客户端代理，接口兼容原 Elasticsearch 客户端"""
        async def search(self, index: str, query: Dict[str, Any], size: int, aggs: Dict[str, Any], timeout: str) -> Dict[str, Any]:
            body = {
                "query": query,
                "size": size,
                "aggs": aggs,
                "timeout": timeout
            }
            return await _es_mcp_client.search(index, body)
else:
    # 原有直连模式
    es_client = Elasticsearch(["http://localhost:9200"])

# data_type 映射
DATA_TYPE_MAP = {
    "impressions": 1,
    "clicks": 2,
    "cost": 3,
    "conversions": 4,
    "reach": 5,
    "frequency": 6,
}

FACT_INDEX = "ad_stat_data"
AUDIENCE_INDEX = "ad_stat_audience"

# 维度中文名映射
DIMENSION_NAME_MAP = {
    "audience_gender": "性别",
    "audience_age": "年龄段",
    "audience_os": "操作系统",
    "audience_os_version": "系统版本",
    "audience_country": "国家",
    "audience_city": "城市",
    "audience_interest": "兴趣标签",
    "data_date": "日期",
    "data_month": "月份",
    "data_week": "周",
    "data_hour": "小时",
    "channel": "渠道",
    "campaign_id": "计划ID",
    "campaign_name": "计划名称",
    "adgroup_id": "广告组ID",
    "adgroup_name": "广告组名称",
    "advertiser_id": "广告主ID",
    "creative_id": "创意ID",
    "creative_name": "创意名称",
    "industry": "行业",
}

# 受众维度值映射（数字 → 中文）
AUDIENCE_VALUE_MAPS = {
    "audience_gender": {
        "1": "男性",
        "2": "女性",
        "1.0": "男性",
        "2.0": "女性",
    },
    "audience_age": {
        "1": "18-24岁",
        "2": "25-34岁",
        "3": "35-44岁",
        "4": "45-54岁",
        "5": "55岁以上",
        "1.0": "18-24岁",
        "2.0": "25-34岁",
        "3.0": "35-44岁",
        "4.0": "18-24岁",
        "5.0": "55岁以上",
    },
    "audience_os": {
        "1": "iOS",
        "2": "Android",
        "1.0": "iOS",
        "2.0": "Android",
    },
    "audience_interest": {
        "1": "游戏",
        "2": "购物",
        "3": "教育",
        "4": "娱乐",
        "5": "金融",
        "6": "生活服务",
        "7": "资讯阅读",
        "8": "旅游出行",
    },
    "audience_os_version": {
        "11": "iOS 15",
        "12": "iOS 16",
        "13": "iOS 17",
        "21": "Android 10",
        "22": "Android 11",
        "23": "Android 12",
        "24": "Android 13",
        "25": "Android 14",
        "11.0": "iOS 15",
        "12.0": "iOS 16",
        "13.0": "iOS 17",
        "21.0": "Android 10",
        "22.0": "Android 11",
        "23.0": "Android 12",
        "24.0": "Android 13",
        "25.0": "Android 14",
    },
    "audience_country": {
        "101": "中国",
        "102": "美国",
        "103": "日本",
        "104": "德国",
        "105": "英国",
        "101.0": "中国",
        "102.0": "美国",
        "103.0": "日本",
        "104.0": "德国",
        "105.0": "英国",
    },
    "audience_city": {
        "2001": "北京",
        "2002": "上海",
        "2003": "广州",
        "2004": "深圳",
        "2005": "杭州",
        "2006": "成都",
        "2007": "武汉",
        "2008": "重庆",
        "2009": "南京",
        "2010": "西安",
        "2011": "天津",
        "2012": "苏州",
        "2013": "长沙",
        "2014": "郑州",
        "2015": "青岛",
        "3001": "纽约",
        "3002": "洛杉矶",
        "3003": "旧金山",
        "3004": "芝加哥",
        "3005": "休斯顿",
    },
}


def build_es_query(query_request) -> tuple[str, Dict[str, Any]]:
    """构建 ES 查询"""
    # 兼容 QueryRequest 对象和 dict
    if hasattr(query_request, 'model_dump'):
        model_dict = query_request.model_dump()
    else:
        model_dict = query_request
    metrics = model_dict.get("metrics", ["impressions", "clicks"])
    group_by = model_dict.get("group_by", [])
    filters = model_dict.get("filters", [])
    time_range = model_dict.get("time_range", {})
    advertiser_ids = model_dict.get("advertiser_ids", [])

    # 字段 -> 维度索引映射：哪些字段只存在于维度表
    FIELD_TO_DIM_INDEX = {
        "campaign_name": "campaign",
        "adgroup_name": "adgroup",
        "creative_name": "creative",
        "status": "campaign",          # 计划状态只在维度表
        "campaign_status": "campaign",
        "adgroup_status": "adgroup",
        "creative_status": "creative",
    }

    # ID字段名映射：每个维度表对应的ID字段名
    DIM_ID_FIELD = {
        "campaign": "campaign_id",
        "adgroup": "adgroup_id",
        "creative": "creative_id",
    }

    # 事实表对应的ID字段名和DIM_ID_FIELD一致

    # 选择索引
    use_audience_index = False
    if group_by:
        for gb in group_by:
            if isinstance(gb, dict):
                field = gb.get("field", "") if isinstance(gb, dict) else str(gb)
            else:
                field = str(gb)
            if field.startswith("audience_"):
                use_audience_index = True
                break

    index = AUDIENCE_INDEX if use_audience_index else FACT_INDEX

    # 构建 bool 查询
    bool_must = []

    # 时间范围过滤
    if time_range:
        start_date = time_range.get("start_date")
        end_date = time_range.get("end_date")
        if start_date and end_date:
            bool_must.append({
                "range": {
                    "data_date": {
                        "gte": str(start_date),
                        "lte": str(end_date)
                    }
                }
            })

    # 广告主ID过滤（转换为整数，因为 NLU 返回的是字符串）
    if advertiser_ids:
        bool_must.append({"terms": {"advertiser_id": [int(adv_id) for adv_id in advertiser_ids]}})

    # 预处理筛选：维度表字段筛选需要先去维度表查ID
    from elasticsearch import Elasticsearch
    # 其他过滤条件
    for f in filters:
        field = f.get("field") if isinstance(f, dict) else getattr(f, "field", None)
        # 兼容: prompt输出 operator，旧格式是 op
        op = f.get("operator", f.get("op", "eq")) if isinstance(f, dict) else getattr(f, "operator", getattr(f, "op", "eq"))
        value = f.get("value") if isinstance(f, dict) else getattr(f, "value", None)

        if field and value is not None:
            # 处理只存在维度表的字段筛选：需要先去维度表查出匹配的ID，再用ID过滤事实表
            if field in FIELD_TO_DIM_INDEX:
                dim_index = FIELD_TO_DIM_INDEX[field]
                dim_id_field = DIM_ID_FIELD[dim_index]
                # 在维度表搜索满足条件的实体
                must_clauses = []
                # Try to convert to number if possible for numeric fields
                try:
                    if isinstance(value, str):
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                except (ValueError, TypeError):
                    pass

                if op == "like":
                    # 模糊匹配，名称包含子串：使用 wildcard
                    must_clauses.append({"wildcard": {field: f"*{value}*"}})
                elif op == "eq" or op == "=":
                    must_clauses.append({"term": {field: value}})
                elif op == "gt":
                    must_clauses.append({"range": {field: {"gt": value}}})
                elif op == "gte":
                    must_clauses.append({"range": {field: {"gte": value}}})
                elif op == "lt":
                    must_clauses.append({"range": {field: {"lt": value}}})
                elif op == "lte":
                    must_clauses.append({"range": {field: {"lte": value}}})
                elif op == "in" and isinstance(value, list):
                    # Convert each item in the list to number if possible
                    converted_values = []
                    for v in value:
                        try:
                            if isinstance(v, str):
                                if '.' in v:
                                    converted_values.append(float(v))
                                else:
                                    converted_values.append(int(v))
                            else:
                                converted_values.append(v)
                        except (ValueError, TypeError):
                            converted_values.append(v)
                    must_clauses.append({"terms": {field: converted_values}})

                # 如果已经有广告主过滤，维度表也要加上，减少结果
                if advertiser_ids:
                    must_clauses.append({"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}})

                search_result = es_client.search(
                    index=dim_index,
                    query={"bool": {"must": must_clauses}},
                    size=1000
                )
                # 提取匹配到的ID
                matched_ids = []
                for hit in search_result["hits"]["hits"]:
                    eid = hit["_source"].get(dim_id_field)
                    if eid is not None:
                        matched_ids.append(int(eid))
                # 如果有匹配到ID，添加ID筛选到事实表
                if matched_ids:
                    bool_must.append({"terms": {dim_id_field: matched_ids}})
                # 如果没有匹配到，结果肯定是空，不用继续
                continue
            # 普通字段（存在事实表）直接筛选
            if op == "eq":
                bool_must.append({"term": {field: value}})
            elif op == "like":
                # 模糊匹配，名称包含子串
                # 使用 match 而不是 wildcard，因为名称字段是 text 类型已经分词
                # match 分词后匹配，可以找到包含关键词的文档
                bool_must.append({
                    "match": {
                        field: value
                    }
                })
            elif op == "in" and isinstance(value, list):
                bool_must.append({"terms": {field: value}})
            elif op == "gt":
                bool_must.append({"range": {field: {"gt": value}}})
            elif op == "gte":
                bool_must.append({"range": {field: {"gte": value}}})
            elif op == "lt":
                bool_must.append({"range": {field: {"lt": value}}})
            elif op == "lte":
                bool_must.append({"range": {field: {"lte": value}}})
            elif op == "between" and isinstance(value, list) and len(value) == 2:
                # 区间查询，转换为 gt + lt
                min_val, max_val = value
                bool_must.append({"range": {field: {"gt": min_val}}})
                bool_must.append({"range": {field: {"lt": max_val}}})

    # 受众维度需要额外过滤 audience_type
    if use_audience_index and group_by:
        for gb in group_by:
            field = gb.get("field", "") if isinstance(gb, dict) else str(gb)
            if field == "audience_gender":
                bool_must.append({"term": {"audience_type": 1}})
            elif field == "audience_age":
                bool_must.append({"term": {"audience_type": 2}})
            elif field == "audience_os":
                bool_must.append({"term": {"audience_type": 3}})
            elif field == "audience_interest":
                bool_must.append({"term": {"audience_type": 4}})
            elif field == "audience_os_version":
                bool_must.append({"term": {"audience_type": 5}})
            elif field == "audience_country":
                bool_must.append({"term": {"audience_type": 6}})
            elif field == "audience_city":
                bool_must.append({"term": {"audience_type": 7}})

    query = {"bool": {"must": bool_must}} if bool_must else {"match_all": {}}

    # 构建聚合
    aggs = {}

    # 如果有分组，做嵌套聚合
    if group_by and len(group_by) > 0:
        current = aggs

        # 获取 top_n 和 sort 配置
        top_n = model_dict.get("top_n")
        sort_info = model_dict.get("sort")

        # 存储名称字段映射，最后需要查询维度表补充名称
        name_fields_to_lookup = []  # [(id_field, name_field), ...]

        for i, gb in enumerate(group_by):
            field = gb.get("field", "") if isinstance(gb, dict) else str(gb)
            agg_name = f"group_{i}"

            actual_field = field
            if field == "data_month" or field == "data_week":
                actual_field = "data_date"
            # 受众维度（性别、年龄、OS、兴趣）都存储在 audience_tag_value 字段中
            elif field.startswith("audience_"):
                actual_field = "audience_tag_value"
            # 对于 *_name 名称字段，事实表不存在，我们只按 *_id 聚合，最后查询维度表补充名称
            elif field == "campaign_name":
                actual_field = "campaign_id"
                name_fields_to_lookup.append(("campaign_id", "campaign_name"))
            elif field == "adgroup_name":
                actual_field = "adgroup_id"
                name_fields_to_lookup.append(("adgroup_id", "adgroup_name"))
            elif field == "creative_name":
                actual_field = "creative_id"
                name_fields_to_lookup.append(("creative_id", "creative_name"))

            # 构建 terms 聚合配置
            terms_config = {
                "field": actual_field,
                "size": top_n if (top_n and isinstance(top_n, int)) else 1000,
            }

            # 如果是最后一层分组且有排序要求，按指定指标排序
            if sort_info and i == len(group_by) - 1:
                sort_field = sort_info.get("field")
                sort_order = sort_info.get("order", "desc")
                # ES terms 聚合按聚合后的指标值排序
                # 基础指标: sum_{sort_field}.value
                # 衍生指标 (ctr/cvr/cpc/cpm): {sort_field}.value
                from src.nl_dsl.dsl_templates.common import is_derived_metric
                if is_derived_metric(sort_field):
                    terms_config["order"] = {
                        f"{sort_field}.value": sort_order
                    }
                else:
                    terms_config["order"] = {
                        f"sum_{sort_field}.value": sort_order
                    }

            current[agg_name] = {
                "terms": terms_config,
                "aggs": {}
            }
            current = current[agg_name]["aggs"]

        # 添加指标聚合
        for metric in metrics:
            if metric in DATA_TYPE_MAP:
                dt = DATA_TYPE_MAP[metric]
                current[f"sum_{metric}"] = {
                    "filter": {"term": {"data_type": dt}},
                    "aggs": {
                        "value": {"sum": {"field": "data_value"}}
                    }
                }
    else:
        # 无分组，直接用过滤聚合
        for metric in metrics:
            if metric in DATA_TYPE_MAP:
                dt = DATA_TYPE_MAP[metric]
                aggs[f"sum_{metric}"] = {
                    "filter": {"term": {"data_type": dt}},
                    "aggs": {
                        "value": {"sum": {"field": "data_value"}}
                    }
                }

    es_query = {
        "query": query,
        "size": 0,
        "aggs": aggs,
        "timeout": "10s"
    }

    return index, es_query


def parse_es_result(response: Dict[str, Any], query_request, group_by: list) -> List[Dict[str, Any]]:
    """解析 ES 查询结果"""
    result = []

    # 兼容 QueryRequest 对象和 dict
    if hasattr(query_request, 'metrics'):
        metrics = query_request.metrics
    else:
        metrics = query_request.get('metrics', [])

    if group_by and len(group_by) > 0:
        # 有分组的情况，递归展开聚合桶
        def recurse(current_agg: Dict[str, Any], path: List[Any], depth: int):
            if depth >= len(group_by):
                # 对路径中的受众维度值做中文映射
                mapped_path = []
                for i, val in enumerate(path):
                    dim = group_by[i] if isinstance(group_by[i], str) else group_by[i].get("field", "")
                    val_str = str(val)
                    # 检查是否是受众维度，如果是则映射
                    if dim in AUDIENCE_VALUE_MAPS and val_str in AUDIENCE_VALUE_MAPS[dim]:
                        mapped_path.append(AUDIENCE_VALUE_MAPS[dim][val_str])
                    elif dim == "data_hour":
                        # 小时维度显示为 "X点"
                        mapped_path.append(f"{val_str}点")
                    elif dim == "data_month":
                        # 月份维度：支持 timestamp 毫秒 或 YYYY-MM-DD 字符串
                        try:
                            val_str = str(val)
                            if len(val_str) > 10:  # 毫秒时间戳
                                ts = int(val) / 1000
                                dt = datetime.fromtimestamp(float(ts))
                            else:  # YYYY-MM-DD 字符串
                                dt = datetime.strptime(val_str, "%Y-%m-%d")
                            mapped_path.append(dt.strftime("%Y年%m月"))
                        except (ValueError, TypeError):
                            mapped_path.append(val_str)
                    elif dim == "data_week":
                        # 周维度：支持 timestamp 毫秒 或 YYYY-MM-DD 字符串
                        try:
                            val_str = str(val)
                            if len(val_str) > 10:  # 毫秒时间戳
                                ts = int(val) / 1000
                                dt = datetime.fromtimestamp(float(ts))
                            else:  # YYYY-MM-DD 字符串
                                dt = datetime.strptime(val_str, "%Y-%m-%d")
                            mapped_path.append(f"{dt.year}年第{dt.isocalendar()[1]}周")
                        except (ValueError, TypeError):
                            mapped_path.append(val_str)
                    elif dim == "data_date":
                        # 日期维度：支持 timestamp 毫秒 或 YYYY-MM-DD 字符串
                        try:
                            val_str = str(val)
                            if len(val_str) > 10:  # 毫秒时间戳
                                ts = int(val) / 1000
                                dt = datetime.fromtimestamp(float(ts))
                            else:  # YYYY-MM-DD 字符串
                                dt = datetime.strptime(val_str, "%Y-%m-%d")
                            mapped_path.append(dt.strftime("%Y-%m-%d"))
                        except (ValueError, TypeError):
                            mapped_path.append(val_str)
                    else:
                        mapped_path.append(val)

                row = {}
                # 每个维度拆成独立列
                for i, val in enumerate(mapped_path):
                    dim = group_by[i] if isinstance(group_by[i], str) else group_by[i].get("field", "")
                    col_name = DIMENSION_NAME_MAP.get(dim, dim)
                    row[col_name] = val

                # name 列保留兼容（用于图表展示）
                row["name"] = " / ".join(str(p) for p in mapped_path) if mapped_path else "总计"

                for metric in metrics:
                    agg_key = f"sum_{metric}"
                    value = current_agg.get(agg_key, {}).get("value", {}).get("value", 0) or 0
                    if metric == "frequency":
                        # 频次存储值 = 实际值 × 100，需要还原
                        row[metric] = round(value / 100.0, 2) if value else 0
                    elif metric == "ctr":
                        row[metric] = float(value)
                    else:
                        row[metric] = int(value)
                result.append(row)
                return

            agg_name = f"group_{depth}"
            buckets = current_agg.get(agg_name, {}).get("buckets", [])
            for bucket in buckets:
                recurse(bucket, path + [bucket["key"]], depth + 1)

        recurse(response.get("aggregations", {}), [], 0)
    else:
        # 无分组的情况，直接取汇总结果
        row = {"name": "总计", "id": 0}
        aggregations = response.get("aggregations", {})
        for metric in metrics:
            agg_key = f"sum_{metric}"
            value = aggregations.get(agg_key, {}).get("value", {}).get("value", 0) or 0
            if metric == "frequency":
                row[metric] = round(value / 100.0, 2) if value else 0
            elif metric == "ctr":
                row[metric] = float(value)
            else:
                row[metric] = int(value)
        result.append(row)

    # 按分组维度做二次聚合（ES实际按天返回，需要合并相同维度值的数据）
    if group_by and len(result) > 1:
        # 获取所有维度列名（用于聚合key）
        dim_columns = []
        for gb in group_by:
            dim = gb if isinstance(gb, str) else gb.get("field", "")
            col_name = DIMENSION_NAME_MAP.get(dim, dim)
            dim_columns.append(col_name)

        # 按维度列值进行聚合（不论维度类型，只要值相同就合并）
        aggregated = {}
        for row in result:
            # 构建聚合key：所有维度列的值组合
            key_values = [str(row.get(col, "")) for col in dim_columns]
            key = tuple(key_values)

            if key not in aggregated:
                aggregated[key] = row.copy()
            else:
                # 累加所有数值指标
                for metric in metrics:
                    if metric in row:
                        aggregated[key][metric] = aggregated[key].get(metric, 0) + row[metric]

        result = list(aggregated.values())

    # 查询维度表补充名称（当聚合按ID，但分组包含名称字段时）
    from src.tools.hierarchy_utils import get_entity_names
    if group_by:
        # 检查哪些分组字段需要查询名称
        for gb in group_by:
            field = gb.get("field", "") if isinstance(gb, dict) else str(gb)
            # 如果分组按campaign_name，实际聚合是campaign_id，需要补充名称
            if field == "campaign_name":
                # 收集所有需要查询的ID
                entity_ids = []
                for row in result:
                    # 实际聚合结果中存储的是 campaign_id
                    if "计划ID" in row and row["计划ID"] is not None:
                        try:
                            entity_ids.append(int(row["计划ID"]))
                        except (ValueError, TypeError):
                            pass
                if entity_ids:
                    # 查询名称
                    names_map = get_entity_names("campaign", entity_ids)
                    # 补充名称列
                    name_col_name = DIMENSION_NAME_MAP.get("campaign_name", "campaign_name")
                    for row in result:
                        if "计划ID" in row:
                            eid = int(row["计划ID"])
                            row[name_col_name] = names_map.get(eid, f"ID:{eid}")
            elif field == "adgroup_name":
                # 收集所有需要查询的ID
                entity_ids = []
                for row in result:
                    if "广告组ID" in row and row["广告组ID"] is not None:
                        try:
                            entity_ids.append(int(row["广告组ID"]))
                        except (ValueError, TypeError):
                            pass
                if entity_ids:
                    names_map = get_entity_names("adgroup", entity_ids)
                    name_col_name = DIMENSION_NAME_MAP.get("adgroup_name", "adgroup_name")
                    for row in result:
                        if "广告组ID" in row:
                            eid = int(row["广告组ID"])
                            row[name_col_name] = names_map.get(eid, f"ID:{eid}")
            elif field == "creative_name":
                # 收集所有需要查询的ID
                entity_ids = []
                for row in result:
                    if "创意ID" in row and row["创意ID"] is not None:
                        try:
                            entity_ids.append(int(row["创意ID"]))
                        except (ValueError, TypeError):
                            pass
                if entity_ids:
                    names_map = get_entity_names("creative", entity_ids)
                    name_col_name = DIMENSION_NAME_MAP.get("creative_name", "creative_name")
                    for row in result:
                        if "创意ID" in row:
                            eid = int(row["创意ID"])
                            row[name_col_name] = names_map.get(eid, f"ID:{eid}")

    # 计算衍生指标 CTR (点击率) = clicks / impressions
    if result and "clicks" in metrics and "impressions" in metrics:
        for row in result:
            impressions = row.get("impressions", 0)
            clicks = row.get("clicks", 0)
            row["ctr"] = clicks / impressions if impressions > 0 else 0

    # 计算衍生指标 CVR (转化率) = conversions / clicks
    if result and "conversions" in metrics and "clicks" in metrics:
        for row in result:
            clicks = row.get("clicks", 0)
            conversions = row.get("conversions", 0)
            row["cvr"] = conversions / clicks if clicks > 0 else 0

    # 按维度进行自然排序（小时按数字排序，而非字符串排序）
    if group_by and len(result) > 1:
        def sort_key(row):
            keys = []
            for gb in group_by:
                dim = gb if isinstance(gb, str) else gb.get("field", "")
                col_name = DIMENSION_NAME_MAP.get(dim, dim)
                val = row.get(col_name, "")

                if dim == "data_hour":
                    # 小时维度：提取数字进行排序
                    try:
                        if isinstance(val, str):
                            hour_num = int(val.replace("点", ""))
                        else:
                            hour_num = int(val)
                        keys.append(hour_num)
                    except (ValueError, TypeError):
                        keys.append(val)
                elif dim in ["data_date", "data_month", "data_week"]:
                    # 时间维度保持原顺序（ES已按时间排序）
                    keys.append(val)
                else:
                    # 其他维度按字符串排序
                    keys.append(str(val))
            return tuple(keys)

        result = sorted(result, key=sort_key)

    return result


class CustomReportClient:
    """CustomReport 服务客户端

    根据配置自动选择：MCP 模式 / 直连模式
    """

    def __init__(self):
        if mcp_config.use_mcp and mcp_manager is not None:
            self.es_client = EsClientProxy()
        else:
            self.es_client = es_client

    async def execute_query(self, query_request: QueryRequest) -> QueryResult:
        """执行报表查询（直接查 ES）"""
        start_time = time.time()

        try:
            model_dict = query_request.model_dump()
            group_by = model_dict.get("group_by", [])

            # 构建 ES 查询
            index, es_query = build_es_query(query_request)

            response = self.es_client.search(
                index=index,
                query=es_query["query"],
                size=es_query["size"],
                aggs=es_query["aggs"],
                timeout=es_query["timeout"]
            )

            # 解析结果
            data = parse_es_result(response.body, query_request, group_by)

            execution_time = int((time.time() - start_time) * 1000)

            return QueryResult(
                success=True,
                total_rows=len(data),
                data=data,
                execution_time_ms=execution_time
            )

        except Exception as e:
            return QueryResult(
                success=False,
                error_type="unknown",
                message=f"ES 查询失败: {str(e)}"
            )


# 单例
custom_report_client = CustomReportClient()
