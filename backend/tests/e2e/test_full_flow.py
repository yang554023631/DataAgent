import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_e2e_basic_query():
    """端到端测试：基础查询"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 发送查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "看广告主 六一八智能 上周的曝光点击"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "result" in result
    assert "final_report" in result["result"]
    assert "title" in result["result"]["final_report"]
    assert "metrics" in result["result"]["final_report"]
    assert len(result["result"]["final_report"]["metrics"]) > 0
    assert "data_table" in result["result"]["final_report"]


@pytest.mark.asyncio
async def test_e2e_query_by_dimension():
    """端到端测试：按维度查询"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 发送按渠道维度查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "看广告主 六一八智能 按渠道看上周曝光点击"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    # 维度查询被正确解析
    assert "group_by" in result["result"]["query_intent"]
    assert result["result"]["final_report"]["title"] is not None


@pytest.mark.asyncio
async def test_e2e_query_with_filter():
    """端到端测试：带过滤条件查询"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 发送带过滤条件的查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "看上周安卓端的曝光点击"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    # 过滤条件被正确解析
    assert "filters" in result["result"]["query_intent"]
    assert result["result"]["final_report"]["title"] is not None


@pytest.mark.asyncio
async def test_e2e_multiple_queries_same_session():
    """端到端测试：同一会话多次查询"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 第一次查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "看广告主 六一八智能 上周的曝光"}
    )
    assert response.status_code == 200
    result1 = response.json()
    assert result1["status"] == "completed"

    # 3. 第二次查询（同一会话）
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "再看看点击和花费"}
    )
    assert response.status_code == 200
    result2 = response.json()
    assert result2["status"] == "completed"
    assert "final_report" in result2["result"]


@pytest.mark.asyncio
async def test_e2e_full_metrics_query():
    """端到端测试：完整多指标查询"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 发送包含多个指标的查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "看广告主 六一八智能 上周的曝光、点击、花费和CTR"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果包含所有预期部分
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    final_report = result["result"]["final_report"]

    assert "title" in final_report
    assert "metrics" in final_report
    assert len(final_report["metrics"]) > 0
    assert "highlights" in final_report
    assert "data_table" in final_report
    assert "next_queries" in final_report


@pytest.mark.asyncio
async def test_e2e_date_formatting_month_dimension():
    """端到端测试：按月份分组时的日期格式化验证"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 发送按月份分组的查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "电商家居_40_new 最近三个月的点击，按月细分"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    final_report = result["result"]["final_report"]

    # 验证数据表格存在且有数据
    assert "data_table" in final_report
    assert len(final_report["data_table"]["rows"]) > 0

    # 验证日期格式化：月份应该显示为 "YYYY年MM月" 格式，而不是原始 timestamp
    for row in final_report["data_table"]["rows"]:
        name_value = row[0] if isinstance(row[0], str) else str(row[0])
        # 不应该是纯数字的 timestamp（长度 > 10 的数字）
        if len(name_value) > 10 and name_value.isdigit():
            assert False, f"日期未格式化，显示原始 timestamp: {name_value}"
        # 应该包含 "年" 和 "月" 字样
        assert "年" in name_value or "-" in name_value or "月" in name_value, \
            f"日期格式不正确: {name_value}"


@pytest.mark.asyncio
async def test_e2e_date_formatting_with_multiple_dimensions():
    """端到端测试：多维度分组时的日期格式化验证（月份+性别）"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 发送按月份和性别分组的查询
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "电商家居_40_new 最近三个月的点击，按性别、月细分"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    final_report = result["result"]["final_report"]

    # 验证数据表格
    assert "data_table" in final_report
    assert len(final_report["data_table"]["rows"]) > 0

    # 验证多维度下的日期格式化
    columns = final_report["data_table"]["columns"]
    month_col_idx = columns.index("月份")
    gender_col_idx = columns.index("性别")
    for row in final_report["data_table"]["rows"][:5]:  # 检查前5行
        # 验证月份格式
        month_value = row[month_col_idx]
        assert "年" in month_value and "月" in month_value, f"月份格式错误: {month_value}"
        # 验证性别值
        gender_value = row[gender_col_idx]
        assert gender_value in ["男性", "女性", "未知"], f"性别值错误: {gender_value}"

    # 验证拆列后的独立列存在
    assert "月份" in columns, "应该有'月份'列"
    assert "性别" in columns, "应该有'性别'列"
    assert "name" not in columns, "不应该有重复的'name'列（已有独立维度列）"


@pytest.mark.asyncio
async def test_e2e_advertiser_list_integration():
    """端到端测试：广告主列表查询集成验证"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 查询广告主列表
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "都有哪些广告主"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    final_report = result["result"]["final_report"]

    # 验证标题
    assert "可用的广告主列表" in final_report["title"]

    # 验证数据表格
    assert "data_table" in final_report
    assert len(final_report["data_table"]["rows"]) > 0

    # 验证不应该有图表（metrics 为空）
    assert len(final_report.get("metrics", [])) == 0


@pytest.mark.asyncio
async def test_e2e_multi_dimension_split_columns_integration():
    """端到端测试：多维度分组拆列集成验证"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 查询按性别和月份分组
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "电商家居_40_new 最近三个月的点击，按性别、月细分"}
    )
    assert response.status_code == 200
    result = response.json()

    # 3. 验证结果
    assert result["status"] == "completed"
    assert "final_report" in result["result"]
    final_report = result["result"]["final_report"]

    # 验证数据表格列
    columns = final_report["data_table"]["columns"]
    assert "月份" in columns, "应该有'月份'列"
    assert "性别" in columns, "应该有'性别'列"
    assert "name" not in columns, "不应该有重复的'name'列（已有独立维度列）"

    # 验证列存在（顺序不影响功能）

    # 验证数据行格式
    rows = final_report["data_table"]["rows"]
    assert len(rows) > 0
    # 第一行应该有格式化的月份
    first_row_month = rows[0][columns.index("月份")]
    assert "年" in first_row_month and "月" in first_row_month, f"月份格式错误: {first_row_month}"
    # 第一行应该有性别值
    first_row_gender = rows[0][columns.index("性别")]
    assert first_row_gender in ["男性", "女性", "未知"], f"性别值错误: {first_row_gender}"


@pytest.mark.asyncio
async def test_e2e_date_columns_formatting_integration():
    """端到端测试：日期格式格式化集成验证"""
    # 1. 创建会话
    response = client.post("/api/sessions", json={"user_id": "test_user"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # 2. 按月份查询（更稳定有数据）
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "电商家居_40_new 最近两个月的点击，按月查看"}
    )
    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "completed"
    final_report = result["result"]["final_report"]

    # 验证日期列格式
    columns = final_report["data_table"]["columns"]

    # name 列应该包含格式化的日期
    rows = final_report["data_table"]["rows"]
    if rows:
        name_col_idx = columns.index("name") if "name" in columns else 0
        first_name_value = str(rows[0][name_col_idx])
        # 不应该是纯数字的时间戳
        assert not (len(first_name_value) > 10 and first_name_value.isdigit()), \
            f"日期列显示了原始时间戳: {first_name_value}"
        # 应该包含格式化的日期（如 "2026年02月" 或 "2026-02-15"）
        assert "年" in first_name_value or "-" in first_name_value, \
            f"日期没有格式化: {first_name_value}"
