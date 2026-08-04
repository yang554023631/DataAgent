# 全链路日志与请求追踪

**日期**: 2026-08-04
**状态**: 设计中
**分支**: `insight-engine-optimization-0804`

## 背景

当前应用缺少统一的日志体系，处理过程不可追溯。排查问题时无法快速定位：
- 某个请求经过了哪些处理节点
- 每个节点的输入输出是什么
- 错误发生在哪个环节、对应的请求是谁
- 同一轮对话的多次请求之间的关联

本次优化目标：建立一套完整的日志和请求追踪体系，让整个处理过程可追溯、可排查。

## 设计目标

1. 每个请求有唯一 `request_id`，响应 header 中返回 `X-Request-ID`
2. 所有日志自动携带 `request_id` 和 `session_id`，可按 ID 串联全链路
3. 关键处理步骤都有日志记录（请求、节点流转、ES 查询、LLM 调用、规则引擎等）
4. 错误日志独立文件，方便快速定位问题
5. 日志纯文本格式，按天滚动，本地运行友好

## 整体架构

三层日志体系：

```
请求入口 (FastAPI Middleware)
  ├─ 生成 request_id，写入 contextvars
  ├─ 记录请求开始/结束日志
  └─ 响应 header 注入 X-Request-ID

业务层 (各模块代码)
  ├─ 直接使用 logger.info/error
  └─ 每条日志自动带上 request_id / session_id（通过 LogFilter）

LangGraph 层 (节点回调)
  ├─ on_node_start: "进入 [节点名]"
  └─ on_node_end: "离开 [节点名]，耗时 X ms"
```

### 核心技术选型

| 技术 | 用途 |
|------|------|
| `contextvars` | 存储 request_id / session_id，异步安全，日志自动携带 |
| `TimedRotatingFileHandler` | 按天滚动日志文件，保留 30 天 |
| 自定义 `LogFilter` | 从 contextvars 提取 ID 注入日志格式 |
| LangGraph callback | 统一打节点生命周期日志 |
| FastAPI Middleware | 请求入口统一生成 ID、打日志、注入响应 header |

## 日志格式与配置

### 日志格式

```
%(asctime)s [%(levelname)s] [%(request_id)s] [%(session_id)s] [%(name)s] %(message)s
```

示例：
```
2026-08-04 17:30:45,123 [INFO] [req-abc123] [sess-def456] [src.agents.nlu_agent] NLU解析完成: 意图=报表查询, 指标=消耗, 维度=广告组
```

- `asctime`：时间戳，格式 `YYYY-MM-DD HH:MM:SS,mmm`
- `levelname`：日志级别（INFO / ERROR）
- `request_id`：请求唯一 ID，无请求上下文时显示 `-`
- `session_id`：会话 ID，无时显示 `-`
- `name`：logger 名称（模块路径），方便定位来源

### 日志级别

仅使用 **INFO** 和 **ERROR** 两个级别：
- **INFO**：正常流程的关键信息（请求、节点、ES 查询、LLM 调用、结果等）
- **ERROR**：异常和错误，附带完整堆栈

> 说明：WARNING 级别保留给 error.log 的过滤阈值使用，业务代码不主动打 WARNING。

### 日志文件

| 文件 | 级别 | 说明 |
|------|------|------|
| `logs/app.log` | INFO+ | 全量日志 |
| `logs/error.log` | WARNING+ | 仅错误和警告（内容与 app.log 中对应级别完全一致） |

路径相对于 `backend/` 目录，完整路径：`backend/logs/`

### 滚动策略

- 按天滚动（每天生成一个新文件）
- 保留 30 天历史
- 编码：UTF-8
- 控制台同步输出（开发时方便直接查看）

### 配置项 (settings.py)

```python
LOG_LEVEL: str = "INFO"          # 日志级别
LOG_DIR: str = "logs"            # 日志目录（相对 backend/）
LOG_BACKUP_DAYS: int = 30        # 保留天数
LOG_TRUNCATE_LEN: int = 1000     # 长文本截断长度（字符数）
```

## 关键日志点

### 请求层 (FastAPI Middleware)

| 时机 | 级别 | 内容 |
|------|------|------|
| 请求进入 | INFO | `请求开始: POST /api/sessions/{id}/messages, session_id=xxx, 用户输入="..."` |
| 请求返回 | INFO | `请求完成: 状态=200, 耗时=1234ms, 结果摘要="..."` |
| 请求异常 | ERROR | `请求异常: error=xxx` + 完整堆栈 |

> 用户输入全量打印，不截断。

### LangGraph 节点层 (回调统一打)

| 时机 | 级别 | 内容 |
|------|------|------|
| 节点开始 | INFO | `进入节点: intent_router` |
| 节点结束 | INFO | `离开节点: intent_router, 耗时=45ms` |
| 节点异常 | ERROR | `节点异常: nlu, error=xxx` + 完整堆栈 |

覆盖所有节点：intent_router、rag_retrieve、rag_generate_answer、nlu、hitl、advertiser_handle、planner、executor、insight、analyst、reporter。

### 业务关键节点 (代码埋点)

| 位置 | 级别 | 内容 | 截断 |
|------|------|------|:----:|
| NLU 解析后 | INFO | 完整 query_intent 结构（指标、维度、时间、广告主、过滤条件等） | 否 |
| ES 查询后 | INFO | 索引名、广告主数量、聚合维度、结果条数、耗时；DSL 和结果摘要 | **是（1000字）** |
| 规则引擎执行后 | INFO | 亮点命中列表、问题命中列表、检查对象总数 | 否 |
| LLM 调用后 | INFO | 模型名、token 用量、耗时、prompt 摘要、response 摘要 | **是（1000字）** |
| RAG 检索后 | INFO | 查询语句、命中文档数、文档标题列表 | 否 |
| 最终结果 | INFO | final_report 完整内容 | 否 |

> **截断规则**：仅 LLM 的 prompt/response 内容和 ES 的 DSL/大结果集做截断。截断方式：前 1000 字符 + `... (共XXXX字)`。小于等于 1000 字全量打印。提供统一工具函数 `truncate_log(text, max_len)`。

## 模块划分

### 1. 日志初始化模块
**文件**: `src/config/logging_config.py`

职责：
- 配置 root logger（格式、文件 handler、控制台 handler）
- 设置按天滚动和保留天数
- 注册自定义 LogFilter
- 提供 `setup_logging()` 函数，在应用启动时调用

### 2. 上下文变量模块
**文件**: `src/config/context.py`

职责：
- 定义 `request_id_var: ContextVar[str]` 和 `session_id_var: ContextVar[str]`
- 提供 `get_request_id()` / `set_request_id()` / `get_session_id()` / `set_session_id()` 辅助函数
- 提供 `truncate_log(text, max_len)` 截断工具函数

### 3. 请求追踪 Middleware
**文件**: `src/api/middleware.py`

职责：
- 请求进入：生成 UUID 格式的 request_id → 写入 contextvars → 打请求开始日志
- 从请求 URL 路径中解析 session_id（正则匹配 `/api/sessions/{session_id}/...` 模式），写入 contextvars；非会话相关的请求（如 health check）session_id 为 `-`
- 请求返回：计算耗时 → 打请求完成日志 → 在响应 header 注入 `X-Request-ID`
- 全局异常捕获：打 ERROR 日志 + 堆栈，然后重新抛出

### 4. LangGraph 回调
**文件**: `src/graph/callbacks.py`

职责：
- 实现 `on_node_start` / `on_node_end` / `on_node_error` 回调
- 记录节点进入、离开（含耗时）、异常
- 回调内部异常安全（try/except 兜底，不影响主流程）

### 5. 业务代码埋点

在以下节点/模块中添加业务日志：

| 模块 | 日志内容 |
|------|---------|
| `src/graph/nodes.py` - nlu_node | NLU 解析结果 |
| `src/graph/nodes.py` - executor_node | ES 查询摘要 + 结果统计 |
| `src/tools/insight_rules.py` 或 insight_node | 规则引擎命中统计 |
| `src/agents/insight_agent.py` | 洞察生成结果摘要 |
| `src/graph/nodes.py` - analyst_node | LLM 调用摘要（模型、token、耗时、内容截断） |
| `src/rag/` 各模块 | RAG 检索结果摘要 |
| `src/graph/nodes.py` - reporter_node | 最终结果摘要 |

### 6. 配置更新
**文件**: `src/config/settings.py`

新增日志相关配置项。

## 错误处理与边界情况

### 无 request_id 的场景
- 应用启动日志、health check、离线脚本等不经过 HTTP 的代码
- LogFilter 中做兜底：contextvars 取不到就填 `-`，不会抛异常
- 日志格式：`2026-08-04 17:30:00,000 [INFO] [-] [-] [src.main] 应用启动完成`

### LangGraph 回调异常
- 回调内部全部包裹 try/except
- 回调本身出错时打一条简单 warning，然后吞掉，不影响主流程

### 日志截断
- 按字符数截断（不是字节数），中文友好
- 统一使用 `truncate_log(text, max_len)` 函数
- 截断长度通过 `settings.LOG_TRUNCATE_LEN` 配置，默认 1000
- 仅作用于 LLM 的 prompt/response 和 ES 的 DSL/大结果集，其余全量打印

### 敏感信息
- 本地运行场景不做脱敏
- 用户输入、广告主数据、LLM 返回等业务信息全量打印
- 如需上生产再补充脱敏规则

### 初始化时机
- 在 `main.py` 中 app 创建前调用 `setup_logging()`
- 确保所有模块的 logger 在配置完成后才输出
- uvicorn 的 access log 暂不纳入统一格式（后续可优化）

## 改动文件清单

新增文件：
- `src/config/logging_config.py` — 日志初始化配置
- `src/config/context.py` — 上下文变量 + 工具函数
- `src/api/middleware.py` — 请求追踪中间件
- `src/graph/callbacks.py` — LangGraph 日志回调

修改文件：
- `src/main.py` — 初始化日志、注册 middleware
- `src/config/settings.py` — 新增日志配置项
- `src/graph/builder.py` — 注册回调
- `src/graph/nodes.py` — 各节点业务日志埋点
- `src/tools/insight_rules.py` — 规则引擎日志
- `src/agents/insight_agent.py` — 洞察日志
- RAG 相关模块 — 检索日志埋点
