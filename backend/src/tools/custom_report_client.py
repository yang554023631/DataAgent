import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from src.models import QueryRequest, QueryResult

# ES 客户端
es_client = Elasticsearch(["http://localhost:9200"])

# data_type 映射
DATA_TYPE_MAP = {
    "impressions": 1,
    "clicks": 2,
    "cost": 3,
    "conversions": 4,
}

FACT_INDEX = "ad_stat_data"
AUDIENCE_INDEX = "ad_stat_audience"

# 维度中文名映射
DIMENSION_NAME_MAP = {
    "audience_gender": "性别",
    "audience_age": "年龄段",
    "audience_os": "操作系统",
    "audience_interest": "兴趣标签",
    "data_date": "日期",
    "data_month": "月份",
    "data_week": "周",
    "data_hour": "小时",
    "channel": "渠道",
    "campaign_id": "计划ID",
    "advertiser_id": "广告主ID",
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
        "4.0": "45-54岁",
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

    # 其他过滤条件
    for f in filters:
        field = f.get("field") if isinstance(f, dict) else getattr(f, "field", None)
        op = f.get("op", "eq") if isinstance(f, dict) else getattr(f, "op", "eq")
        value = f.get("value") if isinstance(f, dict) else getattr(f, "value", None)

        if field and value is not None:
            if op == "eq":
                bool_must.append({"term": {field: value}})
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

    query = {"bool": {"must": bool_must}} if bool_must else {"match_all": {}}

    # 构建聚合
    aggs = {}

    # 如果有分组，做嵌套聚合
    if group_by and len(group_by) > 0:
        current = aggs

        for i, gb in enumerate(group_by):
            field = gb.get("field", "") if isinstance(gb, dict) else str(gb)
            agg_name = f"group_{i}"

            actual_field = field
            if field == "data_month" or field == "data_week":
                actual_field = "data_date"
            # 受众维度（性别、年龄、OS、兴趣）都存储在 audience_tag_value 字段中
            elif field.startswith("audience_"):
                actual_field = "audience_tag_value"

            current[agg_name] = {
                "terms": {
                    "field": actual_field,
                    "size": 1000,
                },
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
                        # 月份维度：timestamp 毫秒转 YYYY-MM 格式
                        try:
                            ts = int(val) / 1000 if isinstance(val, (int, float, str)) and len(str(val)) > 10 else val
                            dt = datetime.fromtimestamp(float(ts))
                            mapped_path.append(dt.strftime("%Y年%m月"))
                        except (ValueError, TypeError):
                            mapped_path.append(val_str)
                    elif dim == "data_week":
                        # 周维度：timestamp 毫秒转 第X周 格式
                        try:
                            ts = int(val) / 1000 if isinstance(val, (int, float, str)) and len(str(val)) > 10 else val
                            dt = datetime.fromtimestamp(float(ts))
                            mapped_path.append(f"{dt.year}年第{dt.isocalendar()[1]}周")
                        except (ValueError, TypeError):
                            mapped_path.append(val_str)
                    elif dim == "data_date":
                        # 日期维度：timestamp 毫秒转 YYYY-MM-DD 格式
                        try:
                            ts = int(val) / 1000 if isinstance(val, (int, float, str)) and len(str(val)) > 10 else val
                            dt = datetime.fromtimestamp(float(ts))
                            mapped_path.append(dt.strftime("%Y-%m-%d"))
                        except (ValueError, TypeError):
                            mapped_path.append(val_str)
                    else:
                        mapped_path.append(val_str)

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
                    row[metric] = int(value) if metric != "ctr" else float(value)
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
            row[metric] = int(value) if metric != "ctr" else float(value)
        result.append(row)

    # 计算衍生指标 CTR (点击率) = clicks / impressions
    if result and "clicks" in metrics and "impressions" in metrics:
        for row in result:
            impressions = row.get("impressions", 0)
            clicks = row.get("clicks", 0)
            row["ctr"] = clicks / impressions if impressions > 0 else 0

    return result


class CustomReportClient:
    """CustomReport 服务客户端（直接 ES 查询）"""

    def __init__(self):
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
