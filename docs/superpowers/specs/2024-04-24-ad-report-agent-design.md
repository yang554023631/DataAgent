# 广告报表多Agent系统 设计文档

## 一、项目概述

### 1.1 目标
构建一个基于LangGraph的多Agent对话式广告数据分析系统，用户通过自然语言就能查询数据、发现异常、获得洞察。

### 1.2 核心价值
- **交互革命**：从"UI填表单"到"说句话就能查"
- **主动发现**：系统自动检测异常，不需要用户自己找问题
- **自动下钻**：发现问题后自动定位根因
- **上下文感知**：支持增量修改，不需要每次重说

---

## 二、整体架构

### 2.1 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + ECharts |
| 后端 | FastAPI + LangGraph + Pydantic 2 |
| LLM | Claude 3 (Haiku/Sonnet) + 兼容OpenAI |
| 数据层 | 调用 `~/AL/CustomReport/` HTTP接口 |
| 部署 | Docker Compose |

### 2.2 6节点架构

```
用户输入
   ↓
🧠 意图理解 (NLU Agent)
   ↓ 有歧义？
❓ 人机协调 (HITL Node) ←──────────┐
   ↓ 澄清后                          │
📋 查询规划 (Planner Agent)          │
   ↓ 需要确认？──────────────────────┘
   ↓
⚡ 数据执行 (Executor Node)
   ↓
📊 数据分析 (Analyst Agent)
   ↓ 需要下钻？──────────────────────┐
   ↓                                │
📝 报告生成 (Reporter Agent)         │
   ↓                                │
展示给用户 → 用户反馈 → 回到意图理解 ──┘
```

---

## 三、每个节点详细设计

### 3.1 意图理解Agent (NLU Agent)

**职责**：将自然语言翻译成结构化查询意图

**输入**：用户输入 + 会话历史
**输出**：QueryIntent
```json
{
  "time_range": {"start_date": "2024-04-15", "end_date": "2024-04-21", "unit": "day"},
  "metrics": ["impressions", "clicks", "ctr"],
  "group_by": ["campaign_id"],
  "filters": [{"field": "audience_os", "op": "=", "value": 2}],
  "is_incremental": false,
  "ambiguity": {
    "has_ambiguity": true,
    "type": "advertiser_ambiguous",
    "reason": "广告主不明确，匹配到3个含'京东'的广告主",
    "options": [...]
  }
}
```

**专属Tools**：
- `parse_time_range` - 自然语言时间解析
- `map_business_terms` - 业务术语映射
- `get_advertiser_list` - 广告主模糊匹配
- `detect_ambiguity` - 歧义检测规则

**推荐模型**：Claude 3 Haiku / GPT-3.5-turbo

---

### 3.2 人机协调节点 (HITL Node)

**职责**：管理人机交互的暂停-等待-恢复流程

**触发场景**：
- 指标/广告主不明确
- 查询范围过大需要确认
- 查询失败需要用户调整

**输入**：歧义信息
**输出**：用户澄清答案

**专属Tool**：
- `generate_clarification_options` - 生成标准化澄清选项

**实现方式**：纯逻辑控制，不需要LLM

---

### 3.3 查询规划Agent (Planner Agent)

**职责**：将结构化意图转换成可执行、合法、优化过的查询请求

**核心业务规则**：
- 按`audience_*`分组 → 自动切换到`audience`索引 + `audience_type`过滤
- 有时间维度 → 折线图；分类<10个 → 柱状图；占比 → 饼图

**输入**：QueryIntent + 用户澄清
**输出**：QueryRequest + 警告列表

**专属Tools**：
- `apply_business_rules` - 应用业务规则
- `auto_select_chart_type` - 自动选择图表类型
- `validate_query_request` - 参数合法性校验
- `estimate_query_size` - 预估查询数据量

**推荐模型**：Claude 3 Haiku / GPT-3.5-turbo

---

### 3.4 数据执行节点 (Executor Node)

**职责**：可靠执行查询，获取数据

**输入**：QueryRequest
**输出**：查询结果 + 执行状态

**专属Tools**：
- `execute_ad_report_query` - 调用CustomReport接口
- `handle_query_error` - 错误处理与重试

**实现方式**：纯HTTP客户端，不需要LLM

---

### 3.5 数据分析Agent (Analyst Agent)

**职责**：深度分析数据，产出人类分析师级别的洞察

**核心策略**：算法做计算，LLM做决策

| 任务 | 实现方式 |
|------|---------|
| 异常检测 | 纯Python算法（环比突变 + Z-score） |
| 贡献度计算 | 纯Python算法 |
| 是否需要下钻 | LLM决策 |
| 选择下钻维度 | LLM决策 |
| 撰写分析结论 | LLM生成文案 |

**输入**：查询结果 + QueryRequest
**输出**：AnalysisResult + 下钻决策

**专属Tools**：
- `detect_anomalies` - 异常检测算法
- `calculate_contribution` - 贡献度拆分
- `compare_periods` - 环比同比计算
- `rank_analysis` - Top/Bottom排名
- `trend_analysis` - 趋势分析

**推荐模型**：Claude 3 Sonnet / GPT-4

**下钻控制**：最多自动下钻2层，防止无限循环

---

### 3.6 报告生成Agent (Reporter Agent)

**职责**：将数据和洞察整合成用户友好的最终输出

**输入**：QueryRequest + 查询结果 + AnalysisResult
**输出**：FinalReport

```json
{
  "title": "2024-04-15 ~ 2024-04-21 广告效果报告",
  "key_metrics": [
    {"name": "总曝光", "value": "43,690", "change": "+12.3%"}
  ],
  "highlights": [
    "🟢 男性用户CTR达到2.99%，表现优秀",
    "🔴 女性用户CTR仅2.19%，建议优化素材"
  ],
  "report_url": "https://report.example.com/?id=abc123",
  "next_queries": [
    "按年龄维度分析",
    "对比iOS和Android表现"
  ]
}
```

**专属Tools**：
- `generate_report_url` - 生成报表链接
- `suggest_next_queries` - 推荐后续分析
- `format_numbers` - 数字格式化

**推荐模型**：Claude 3 Sonnet / GPT-4

---

## 四、State 设计

### 4.1 字段定义

```python
class AdReportState(BaseModel):
    # 会话基本信息
    session_id: str
    user_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # 用户输入
    user_input: str
    conversation_history: List[Dict]
    
    # 意图理解输出
    query_intent: Optional[Dict]
    ambiguity: Optional[Dict]
    
    # 人机澄清输出
    user_feedback: Optional[Dict]
    clarification_count: int = 0
    
    # 查询规划输出
    query_request: Optional[Dict]
    query_warnings: List[str]
    
    # 数据执行输出
    query_result: Optional[Dict]
    execution_time_ms: Optional[int]
    
    # 数据分析输出
    analysis_result: Optional[Dict]
    drill_down_level: int = 0
    drill_down_history: List[Dict]
    needs_drill_down: bool = False
    
    # 报告生成输出
    final_report: Optional[Dict]
    
    # 执行控制
    current_phase: ExecutionPhase
    error: Optional[Dict]
```

### 4.2 读写权限

| 字段 | 写入者 | 读取者 |
|------|--------|--------|
| query_intent | NLU | Planner, HITL |
| ambiguity | NLU, Planner | HITL |
| user_feedback | HITL | NLU, Planner |
| query_request | Planner | Executor, Analyst |
| query_result | Executor | Analyst, Reporter |
| analysis_result | Analyst | Reporter |
| final_report | Reporter | 前端 |

---

## 五、目录结构

```
ad-report-agent/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatMessage.tsx      # 聊天消息组件
│   │   │   ├── ChartRenderer.tsx    # 图表渲染
│   │   │   ├── ClarificationModal.tsx # 澄清弹窗
│   │   │   └── MetricCard.tsx       # 指标卡片
│   │   ├── services/
│   │   │   └── api.ts               # API客户端
│   │   ├── stores/
│   │   │   └── chatStore.ts         # 聊天状态
│   │   └── types/
│   │       └── index.ts             # 类型定义
│   └── package.json
│
├── backend/
│   ├── src/
│   │   ├── agents/                  # 6个Agent实现
│   │   │   ├── nlu.py
│   │   │   ├── planner.py
│   │   │   ├── executor.py
│   │   │   ├── analyst.py
│   │   │   ├── reporter.py
│   │   │   └── hitl.py
│   │   ├── graph/                   # LangGraph定义
│   │   │   ├── state.py
│   │   │   └── builder.py
│   │   ├── tools/                   # 所有Tool实现
│   │   │   ├── time_parser.py
│   │   │   ├── term_mapper.py
│   │   │   ├── anomaly_detector.py
│   │   │   ├── contribution.py
│   │   │   ├── custom_report_client.py
│   │   │   └── ...
│   │   ├── models/                  # Pydantic模型
│   │   │   ├── intent.py
│   │   │   ├── query.py
│   │   │   └── analysis.py
│   │   ├── api/                     # FastAPI路由
│   │   │   ├── routes.py
│   │   │   └── schemas.py
│   │   ├── prompts/                 # Prompt模板
│   │   │   ├── nlu.txt
│   │   │   ├── planner.txt
│   │   │   └── analyst.txt
│   │   ├── config/                  # 配置
│   │   │   └── settings.py
│   │   └── main.py
│   ├── tests/                       # 单元测试
│   │   ├── tools/
│   │   └── agents/
│   └── pyproject.toml
│
├── docker-compose.yml
├── .env.example
└── Makefile
```

---

## 六、实施阶段规划

### 第一阶段（MVP）：跑通主流程
1. 项目脚手架搭建
2. State定义 + Graph骨架
3. 数据执行节点（调用CustomReport接口）
4. 查询规划Agent（简化版）
5. 报告生成Agent（简化版）
6. 基础前端对话界面
7. LangGraph Studio调试支持

**目标**：用户说"看昨天的曝光点击" → 系统能查数据 → 生成报表URL

### 第二阶段：完善交互和理解
8. 意图理解Agent（完整实现）
9. 人机协调节点（暂停-恢复机制）
10. 上下文理解与增量修改
11. 业务术语词典

### 第三阶段：核心分析能力
12. 数据分析Agent（异常检测）
13. 自动下钻闭环
14. 归因分析
15. 对比分析

### 第四阶段：高级功能
16. 报表模板库
17. 订阅推送
18. 创意效果诊断
19. 预算预测告警

---

## 七、关键设计原则

1. **计算用代码，决策用LLM** - 凡是数学计算都用纯Python，LLM只做需要业务理解的判断
2. **Tool = 纯函数** - 不依赖State，输入输出明确，可独立测试
3. **业务规则配置化** - 术语映射、阈值、推荐逻辑都可配置
4. **错误可恢复** - 每个节点都考虑失败场景，返回友好提示
5. **防无限循环** - 澄清次数限制、下钻深度限制
