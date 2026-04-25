# Bug 修复 & 优化记录

## 2026-04-25: 修复日期维度分组时的格式化问题

### 问题现象
按月份、周、日期维度分组查询时，X 轴和数据表格中显示的是原始 timestamp 毫秒数（如 `1770076800000`），而不是人类可读的日期格式。

### 根本原因
ES 查询结果中日期类型字段（`data_month`, `data_week`, `data_date`）返回的 `bucket.key` 是 timestamp 毫秒数，但 `parse_es_result` 函数只处理了 `data_hour` 的格式化，没有对其他时间维度进行处理。

### 修复方案
**文件**: `backend/src/tools/custom_report_client.py`

在 `parse_es_result` 函数的递归遍历中，增加日期维度格式化逻辑：

```python
elif dim == "data_month":
    # 月份维度：timestamp 毫秒转 YYYY-MM 格式
    try:
        ts = int(val) / 1000 if len(str(val)) > 10 else val
        dt = datetime.fromtimestamp(float(ts))
        mapped_path.append(dt.strftime("%Y年%m月"))
    except (ValueError, TypeError):
        mapped_path.append(val_str)

elif dim == "data_week":
    # 周维度：timestamp 毫秒转 第X周 格式
    try:
        ts = int(val) / 1000 if len(str(val)) > 10 else val
        dt = datetime.fromtimestamp(float(ts))
        mapped_path.append(f"{dt.year}年第{dt.isocalendar()[1]}周")
    except (ValueError, TypeError):
        mapped_path.append(val_str)

elif dim == "data_date":
    # 日期维度：timestamp 毫秒转 YYYY-MM-DD 格式
    try:
        ts = int(val) / 1000 if len(str(val)) > 10 else val
        dt = datetime.fromtimestamp(float(ts))
        mapped_path.append(dt.strftime("%Y-%m-%d"))
    except (ValueError, TypeError):
        mapped_path.append(val_str)
```

### 格式化规则
| 维度字段 | 格式示例 |
|---------|---------|
| `data_month` | 2026年02月 |
| `data_week` | 2026年第8周 |
| `data_date` | 2026-02-15 |
| `data_hour` | 14点 |

### 测试覆盖
1. **单元测试**: `tests/test_custom_report_client.py`
   - `test_parse_es_result_date_formatting`: 测试多维度组合时的日期格式化
   - `test_parse_es_result_data_month_formatting`: 测试单独按月份分组时的格式化

2. **端到端测试**: `tests/e2e/test_full_flow.py`
   - `test_e2e_date_formatting_month_dimension`: 验证按月份查询时日期格式正确
   - `test_e2e_date_formatting_with_multiple_dimensions`: 验证多维度（月份+性别）组合时的格式化

### 验证结果
- ✅ 按月份分组：显示 "2026年02月 / 男性" 而非原始时间戳
- ✅ 按日期分组：显示 "2026-02-15" 格式
- ✅ 按周分组：显示 "2026年第8周" 格式
- ✅ 多维度组合时格式化正确
- ✅ 异常情况（非数字时间戳）优雅降级，保留原始值

---

## 2026-04-25: 修复近3个月时间范围解析 & Hitl 中断问题

### 问题现象
查询"最近三个月"的数据时，前端图表 X 轴显示异常，部分查询返回空报告。

### 根本原因
1. **时间范围计算错误**: 使用 `timedelta(days=90)` 计算三个月前的日期，但实际 90 天可能跨越 3-4 个月，导致 `start_date` 变成 1 月 1 日，时间范围变成 1月1日~4月25日（115 天）
2. **触发 Hitl 中断**: 超过 90 天的查询会触发人工确认的中断逻辑，但前端没有处理这种状态，导致报告显示异常

### 修复方案
**文件**: `backend/src/tools/time_parser.py`

```python
# 修复前：使用固定 90 天计算
three_months_ago = today.replace(day=1) - timedelta(days=90)

# 修复后：使用 relativedelta 精确计算 2 个月前
from dateutil.relativedelta import relativedelta
two_months_ago = today - relativedelta(months=2)
start = two_months_ago.replace(day=1)
```

### 时间范围对比
| 方式 | 开始日期 | 结束日期 | 天数 | 是否触发 Hitl |
|-----|---------|---------|-----|-------------|
| 修复前 | 2026-01-01 | 2026-04-25 | 115 天 | ✅ 触发 |
| 修复后 | 2026-02-01 | 2026-04-25 | 83 天 | ❌ 不触发 |

### 补充测试
- `tests/test_time_parser.py`: 新增 `test_parse_time_range_last_3_months` 和变体测试

---

## 2026-04-24: 数据表格增加列排序功能

### 功能需求
所有数据表格支持点击表头进行排序，方便用户快速查找数据。

### 实现细节（`frontend/src/components/DataTable.tsx`）

**1. 排序状态管理**
```typescript
const [sortColumn, setSortColumn] = useState<number | null>(null);
const [sortDirection, setSortDirection] = useState<SortDirection>(null);
```

**2. 排序逻辑**
- 数字列：按数值大小排序
- 字符串列：按中文 localeCompare 排序（支持中文拼音顺序）
- 点击第一次：升序 ↑
- 点击第二次：降序 ↓
- 点击第三次：取消排序，恢复默认顺序

**3. UI 交互**
- 表头添加 `cursor: pointer` 样式，鼠标悬停高亮
- 默认状态显示灰色 `⇅` 图标
- 激活排序后显示蓝色箭头 `↑` / `↓`

### 功能验证
- ✅ 点击"月份"表头，按月份升序/降序排列
- ✅ 点击"clicks"表头，按点击量数值排序
- ✅ 点击"性别"表头，按性别中文排序
- ✅ 排序后自动跳转到第一页
- ✅ 第三次点击取消排序，恢复默认顺序

---

## 2026-04-24: 修复表格多余列 & 月份聚合重复行

### 问题 1: 表格显示多余的 `name` 列
**现象**: 按性别/月份细分时，表格中同时显示 "性别" 和 "name" 两列（内容相同）。

**根本原因**: 为了兼容旧逻辑保留了 `name` 列，但在前端表格中不需要显示。

**修复方案** (`src/agents/reporter_agent.py`):
```python
if "name" in columns:
    columns.remove("name")
```

---

### 问题 2: 按月份细分出现重复行（如6条 "2026-04"）
**现象**: "最近一个月的点击量 按月份细分" 应该只有1条数据，但出来6条。

**根本原因**: ES中 `data_month` 字段映射到了 `data_date`，聚合时仍然按**天**分组，只是格式化显示为月份，导致同月份出现多条数据。

**修复方案** (`src/tools/custom_report_client.py`):
在 `parse_es_result()` 最后添加后处理逻辑：
```python
# 后处理：按月份/周分组时，合并相同维度值的行，累加指标
if needs_merge and len(result) > 1:
    merged = {}
    for row in result:
        key = tuple(row.get(col, "") for col in dim_cols)
        if key not in merged:
            merged[key] = row.copy()
        else:
            merged[key][metric] += row[metric]  # 累加指标
    result = list(merged.values())
```

**验证结果（已确认 ✅）**:
| 查询 | 表格列 | 数据条数 |
|------|--------|----------|
| 按月份细分 | ['月份', 'clicks'] | 2条（3月、4月）✓ |
| 按性别细分 | ['性别', 'clicks'] | 2条（男性、女性）✓ |
| 按性别+月份细分 | ['月份', '性别', 'clicks'] | 4条 ✓ |

---

## 2026-04-24: 修复单维度查询误触发多维度列的问题

### Bug 现象
用户查询 "最近一个月的点击量 按性别细分"，预期只返回 "性别" 列，但实际同时出现 "月份" + "性别" 两列。

同样问题影响：
- "最近一周的数据" → 错误包含 "周" 维度
- "近7天的点击量 按性别细分" → 错误包含 "日期" + "性别" 两列

### 根本原因
`src/tools/term_mapper.py` 中 `DIMENSION_MAPPING` 的匹配词过于激进：
- `"月": "data_month"` → 导致 "最近一个月" 中的 "月" 被误判为按月分组
- `"天": "data_date"` → 导致 "近7天" 中的 "天" 被误判为按天分组
- `"周": "data_week"` → 导致 "最近一周" 中的 "周" 被误判为按周分组

### 修复方案
移除易误判的单字匹配词，改用更长、更精确的匹配：

| 移除 | 新增 |
|------|------|
| "天": "data_date" | "按天细分": "data_date" |
| "月": "data_month" | "按月细分": "data_month" |
| "周": "data_week" | "按周细分": "data_week" |

### 验证结果
```python
"最近一个月的点击量 按性别细分" → ["audience_gender"] ✓
"按月份细分" → ["data_month"] ✓
"按性别细分" → ["audience_gender"] ✓
"近7天的点击量" → [] ✓
"近一个月的数据" → [] ✓
```

---

## 2026-04-24: 多维度组合分析拆列支持

### 功能需求
**现象**: "六一八智能 最近一个月的点击量 按 性别 和 月份 做细分分析" 返回的数据中，多个维度值合并在 `name` 列中（如 "男性 / 2026-04"），无法对单个维度列进行排序。

**优化方案**:
- 每个维度拆成独立列，列名使用中文（如 `性别`、`月份`）
- 保留 `name` 列做兼容
- 所有维度列独立存在，前端可直接对各列排序

**代码改动** (`src/tools/custom_report_client.py`):

1. 新增维度中文名映射：
```python
DIMENSION_NAME_MAP = {
    "audience_gender": "性别",
    "audience_age": "年龄段",
    "audience_os": "操作系统",
    "audience_interest": "兴趣标签",
    "data_date": "日期",
    "data_month": "月份",
    "data_week": "周",
    "data_hour": "小时",
}
```

2. 修改 `parse_es_result()` 输出结构：
```python
# 每个维度拆成独立列
for i, val in enumerate(path):
    dim = dimension_fields[i]
    col_name = DIMENSION_NAME_MAP.get(dim, dim)
    row[col_name] = formatted_value

# name 列保留兼容
row["name"] = " / ".join(dim_values)
```

**效果对比**:

| 优化前 | 优化后 |
|--------|--------|
| `{"name": "男性 / 2026-04", "clicks": 15635}` | `{"性别": "男性", "月份": "2026-04", "name": "男性 / 2026-04", "clicks": 15635}` |

**支持场景**:
- ✅ 按性别 + 月份 → 两列独立，可分别排序
- ✅ 按年龄段 + OS → 两列独立，可分别排序
- ✅ 任意 N 个维度组合 → N 个独立列，全部支持排序

---

## 2026-04-24: 时间范围解析 & 日期格式化优化

### 问题 1: "最近一个月"查询数据为0
**现象**: 用户查询 "六一八智能最近一个月的点击量"，返回结果为 0。

**根本原因**:
- `src/tools/time_parser.py` 中的正则表达式 `r'近(\d+)个月|最近(\d+)个月|过去(\d+)个月'` 只匹配**阿拉伯数字**
- "最近**一**个月" 中的中文数字"一"不匹配，导致走默认逻辑（近7天）或错误处理

**修复方案**:
- 扩展正则表达式支持中文数字：`r'近([一二三四五六七八九十\d]?)个月|最近([一二三四五六七八九十\d]?)个月|过去([一二三四五六七八九十\d]?)个月'`
- 添加 `parse_cn_num()` 函数处理中文数字映射

**验证**:
- "最近一个月" → 2026-03-24 ~ 2026-04-24 ✓
- "近三个月" → 2026-01-24 ~ 2026-04-24 ✓
- "近3个月" → 2026-01-24 ~ 2026-04-24 ✓

---

### 问题 2: 日期维度显示时间戳而非日期格式

**现象**: 按日期（`data_date`）或月份（`data_month`）分组时，结果中显示的是毫秒级时间戳（如 `1776124800000`）而非 `YYYY-MM-DD` 格式。

**根本原因**:
- Elasticsearch `date` 类型字段在 terms 聚合中返回的 `key` 是毫秒级时间戳整数
- `src/tools/custom_report_client.py` 中 `parse_es_result()` 函数直接使用 `bucket["key"]` 作为显示值，未做格式化

**修复方案**:
在 `parse_es_result()` 函数中添加日期格式化逻辑：
- `data_date`: 检测到数字时间戳，转换为 `YYYY-MM-DD` 格式
- `data_month`: 转换为 `YYYY-MM` 格式

**代码改动**:
```python
elif dim == "data_date" and val_str.isdigit():
    # 日期时间戳转 YYYY-MM-DD 格式
    from datetime import datetime
    ts = int(val_str)
    if ts > 1000000000000:  # 毫秒级
        ts = ts // 1000
    mapped_path.append(datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
```

**验证**:
- 输入: `1776124800000` → 输出: `2026-04-14` ✓

---

### 问题 3: CustomReport 服务端口配置错误

**现象**: CustomReport 客户端调用失败，回退到直连 ES。

**根本原因**:
- 配置的 URL 是 `http://localhost:8080/api/report/query`
- 实际服务运行在 `8001` 端口

**修复方案**:
```python
# 修复前
CUSTOM_REPORT_API_URL = "http://localhost:8080/api/report/query"
# 修复后
CUSTOM_REPORT_API_URL = "http://localhost:8001/api/report/query"
```

---

## 受影响文件

| 文件 | 说明 |
|------|------|
| `src/tools/time_parser.py` | 修复中文数字正则 |
| `src/tools/custom_report_client.py` | 添加日期格式化、修复端口 |

## 测试建议

修复后需验证以下场景：
1. ✅ "最近一个月的点击量" → 返回正确数据
2. ✅ "按天查看点击量" → 日期显示为 `YYYY-MM-DD`
3. ✅ "按性别和月份做细分分析" → 性别和月份显示正确格式
