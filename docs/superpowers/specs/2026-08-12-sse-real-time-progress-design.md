# SSE 实时进度推送修复设计

## 问题背景

当前系统已经实现了 SSE (Server-Sent Events) 功能，目的是在后端处理较慢时，**实时通知用户当前处理到哪个阶段**，减少用户的等待焦虑。

但现有实现存在根本性问题：
- **当前行为**：整个分析流程完全执行完毕后，才从 `execution_trace` 回放步骤，批量发送所有 SSE 事件
- **用户感知**：页面一直卡住，所有步骤状态一次性全部更新，体验和非流式没有区别
- **预期行为**：每一步开始/完成时，**立即推送事件给前端**，前端实时更新进度

## 根因分析

### 当前实现流程图

```
┌─────────────────────────────────────────────────────────────┐
│ stream_message                                              │
│  1. await graph_app.ainvoke() 【阻塞等待全程完成】          │
│  2. 得到完整的 execution_trace                              │
│  3. for step in execution_trace:                           │
│        yield event + asyncio.sleep(0.1)                    │
└─────────────────────────────────────────────────────────────┘
```

**问题本质**：`graph_app.ainvoke()` 是阻塞调用，必须等到整个图执行完，控制权才会回到 `stream_message`。所以不可能在执行过程中推送事件。

## 解决方案：contextvars + asyncio.Queue

### 架构设计

使用 Python `contextvars` 保存当前请求的异步队列，节点执行每一步时**实时推送事件**到队列，SSE 一边执行一边消费输出。

```
┌─────────────────────────────────────────────────────────────┐
│ stream_message                                              │
│                                                             │
│  • 创建 asyncio.Queue()                                     │
│  • contextvars 设置当前队列                                 │
│  • 启动两个并发任务：                                       │
│    1. Task A: await graph_app.ainvoke() 执行图            │
│    2. Task B: while queue not None:                        │
│               event = await queue.get()                     │
│               yield event  → → →  SSE 前端                 │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ contextvars 上下文                                          │
│  sse_event_queue: Queue  ←  每个请求一个独立队列            │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ 各个图节点 (analysis_node / intent_classifier / ...)       │
│                                                             │
│  step_start:                                                │
│      execution_trace.append(...)                            │
│      queue = sse_event_queue.get()  ← 从上下文读取         │
│      if queue: await queue.put({type: step_start, ...})    │
│                                                             │
│  step_complete:                                             │
│      execution_trace.append(...)                            │
│      queue = sse_event_queue.get()                          │
│      if queue: await queue.put({type: step_complete, ...}) │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ 前端 SSE 客户端                                             │
│  实时接收事件，逐步更新进度条/步骤状态                        │
└─────────────────────────────────────────────────────────────┘
```

### 组件拆分

| 组件 | 位置 | 职责 |
|------|------|------|
| `sse_event_queue` contextvar | `src/services/streaming_context.py` (新增) | 保存当前请求的事件队列 |
| `stream_message` 修改 | `src/services/session_service.py` | 创建队列，设置上下文，并发运行图执行和事件消费 |
| `analysis_node` 修改 | `src/graph/nodes.py` | 每一步开始/完成后推送事件到队列 |
| 其他顶层节点 | `src/graph/nodes.py` | `intent_classifier`, `report_intent`, `nl_dsl_node` 等也同步支持 |

### 数据结构

**SSE 事件格式**（保持向后兼容，前端不需要修改解析逻辑）：

```typescript
// step_start 事件
{
  type: "step_start",
  step: string,              // 步骤名: "intent_analyzer", "cot_planner", 等
  status: "started"
}

// step_complete 事件
{
  type: "step_complete",
  step: string,
  status: "success" | "failed" | "started",
  duration_ms?: number,      // 耗时（如果完成）
  ...extra_fields            // 其他元数据（extracted_fields, entity_count 等）
}

// 原有事件类型保持不变：
// - cot_reasoning
// - hitl
// - final_report
// - complete
// - error
```

### 并发控制

- `asyncio.gather(graph_task, consumer_task)` 同时运行
- graph 执行完成后，发送 `None` 哨兵到队列，消费者退出循环
- 每个请求独立创建 Queue，互不干扰
- contextvars 天然支持并发，多个同时请求不会互相干扰

## 修改范围

### 1. 新增文件

- `backend/src/services/streaming_context.py` - 定义 contextvar

### 2. 修改文件

| 文件 | 修改内容 | 改动规模 |
|------|----------|----------|
| `backend/src/services/session_service.py` | `stream_message()` 重构为并发队列模式 | 中等（≈50行修改） |
| `backend/src/graph/nodes.py` | `analysis_node` 中每个步骤追加事件到 `execution_trace` 后，推送事件到队列 | 中等（每个 step 加几行代码） |
| `backend/src/graph/nodes.py` | 检查其他节点是否也需要推送（顶层节点 `intent_classifier`, `report_intent` 等） | 小 |

### 3. 兼容性保证

- **非流式请求**（`send_message` 同步接口）不受影响：contextvar 默认是 `None`，节点不做任何事情
- **向前兼容**：SSE 输出事件格式保持不变，前端代码不需要修改
- **execution_trace 保留**：现有逻辑完全保留，用于事后回放和最终结果完整性
- **异常安全**：推送失败不影响主流程，队列不存在（非流式）直接跳过

## 错误处理

- 如果推送事件到队列失败（队列满等异常），**只打日志不中断主流程**
- 即使推送失败，主流程仍然能正常完成，最终会发送完整结果
- graph 执行异常，consumer 任务会收到哨兵退出，SSE 输出 error 事件后正常结束

## 优点

1. **真正实时**：每一步开始/完成立即推送，前端实时更新
2. **侵入性小**：只在添加事件的地方加几行代码，不改变现有业务逻辑
3. **兼容性好**：非流式请求完全不受影响，现有 API 不需要变化
4. **并发安全**：contextvars 保证多个请求隔离，互不干扰
5. **保留现有功能**：`execution_trace` 仍然完整保留，不影响回放和调试

## 备选方案对比

| 方案 | 问题 |
|------|------|
| 方案B：回调注入 state | 需要修改 `AdReportState` 添加回调字段，每个节点都要从 state 取回调再调用，改动更大 |
| 方案C：保持回放模式 | 不解决根本问题，用户体验没有改善 |

## 实施步骤

1. 新增 `streaming_context.py` 定义 contextvar
2. 重构 `session_service.stream_message` 使用并发队列模式
3. 修改 `analysis_node`，每个 step 推送事件
4. 检查其他顶层节点，确保整条链路都有实时推送
5. 测试验证：启动后端，用请求 ID `10fd6ce8-bd12-4041-ae12-329b7dca2d24` 验证
6. 提交代码，重启后端

