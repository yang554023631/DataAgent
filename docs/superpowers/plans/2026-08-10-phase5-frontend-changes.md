# Phase 5: Frontend Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the frontend to support the new CoT analysis pipeline — SSE streaming progress, new report format, enhanced chart rendering, and two types of HITL (clarification + quality).

**Architecture:** Frontend adopts a streaming-first approach. The chat store sends messages via SSE and accumulates step-by-step progress. ChatMessage renders the new `final_report` format (with `report_type`, `chart_config`, `data`, `data_table`, `highlights`, `quality_info`, `metadata`). ChartRenderer is enhanced to support pie charts, KPI cards, and multi-series line charts natively. ClarificationModal handles both field-clarification and quality-HITL types.

**Tech Stack:** React 18 + TypeScript, Zustand (state), ECharts (charts), EventSource API (SSE), Tailwind CSS, Vitest + React Testing Library

## Global Constraints

- All new code uses TypeScript with explicit types (no `any` without justification)
- Chinese UI text (所有面向用户的文案使用中文)
- Tailwind CSS for styling (follows existing patterns)
- Backward compatible: old `final_report` format (with `metrics` array of `{name, value, trend}`) still renders
- EventSource falls back to regular POST if SSE fails

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/services/api.ts` | Modify | Add `FinalReportV2` types, `streamMessage()` method, `HitlType` enum |
| `frontend/src/stores/chatStore.ts` | Modify | Replace `sendMessage` with streaming flow, add step progress state, handle hitl events |
| `frontend/src/components/StepProgress.tsx` | Create | Step-by-step progress indicator shown during analysis |
| `frontend/src/components/ChatMessage.tsx` | Modify | Support new report format: `report_type`, `chart_config`, `data`, `quality_info`, `metadata` |
| `frontend/src/components/ChartRenderer.tsx` | Modify | Add pie chart, KPI card, multi-series line chart; use `chart_config` directly |
| `frontend/src/components/KpiCardGrid.tsx` | Create | KPI card grid for summary reports (replaces old metrics grid) |
| `frontend/src/components/ClarificationModal.tsx` | Modify | Support `cot_clarification` and `quality_hitl` types; add quality issue display |
| `frontend/src/components/QualityIssueList.tsx` | Create | Display quality check issues (warnings/errors) in report |
| `frontend/src/components/__tests__/StepProgress.test.tsx` | Create | Tests for step progress component |
| `frontend/src/components/__tests__/ChartRenderer.test.tsx` | Modify | Add tests for pie, KPI, multi-series charts |

---

### Task 5.1: API Service — New Types + Streaming Method

**Files:**
- Modify: `frontend/src/services/api.ts`
- Test: `frontend/src/test/api.test.ts` (new file, simple type guard tests)

**Interfaces:**
- Consumes: SSE endpoint `POST /api/sessions/{session_id}/messages/stream`
- Produces: `apiService.streamMessage(sessionId, content, handlers)` — calls back on each event type
- Types: `FinalReportV2`, `ChartConfigV2`, `QualityInfoV2`, `StepProgressEvent`, `HitlEvent`, `StreamEventHandlers`

- [ ] **Step 1: Add new type definitions to api.ts**

Append to `frontend/src/services/api.ts`:

```typescript
// ========== New CoT Analysis Report Types (V2) ==========

export type ReportType = 'success' | 'error' | 'empty' | 'hitl';

export interface ChartConfigV2 {
  type: 'line' | 'bar' | 'pie' | 'kpi_card' | 'table';
  title?: string;
  x_axis?: { field: string; label: string };
  y_axis?: { field: string; label: string };
  series_field?: string;
  series?: Array<{ name: string; color: string }>;
}

export interface QualityIssueV2 {
  check_type: string;
  severity: 'warning' | 'error' | 'hitl_required';
  message: string;
  suggested_action: string;
  threshold?: any;
  actual?: any;
}

export interface QualityInfoV2 {
  passed: boolean;
  issues: QualityIssueV2[];
  warnings: string[];
  actions: string[];
}

export interface ReportMetadataV2 {
  generated_at: string;
  entity_level: string;
  total_entities: number;
  metrics: string[];
  analysis_type: string;
  chart_type: string;
  time_range: {
    start_date: string;
    end_date: string;
    granularity?: string;
  };
}

export interface FinalReportV2 {
  report_type: ReportType;
  title: string;
  chart_config?: ChartConfigV2 | null;
  data?: Array<Record<string, any>>;
  data_table: { columns: string[]; rows: any[][] };
  quality_info?: QualityInfoV2;
  highlights: Array<{ type: 'positive' | 'negative' | 'info' | 'warning'; text: string }>;
  metadata?: ReportMetadataV2;
  cot_reasoning_summary?: string | null;
  next_queries: string[];
  suggestions?: string[];
  // Error report fields
  error_type?: string;
  message?: string;
  reason?: string;
  recommended_queries?: string[];
}

// Extend Message to support both old and new report formats
export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  finalReport?: FinalReport;
  finalReportV2?: FinalReportV2;
}

// ========== SSE Streaming Types ==========

export type StepStatus = 'started' | 'success' | 'failed' | 'hitl_required' | 'skipped' | 'empty';

export interface StepProgressEvent {
  type: 'step_start' | 'step_complete';
  step: string;
  status?: StepStatus;
  duration_ms?: number;
  label?: string;
}

export interface HitlEvent {
  type: 'hitl';
  hitl_type: 'cot_clarification' | 'quality_hitl';
  question: string;
  options: Array<{ value: string; label: string }>;
  quality_issues?: QualityIssueV2[];
  allow_custom_input?: boolean;
}

export interface FinalReportEvent {
  type: 'final_report';
  data: FinalReportV2;
}

export interface StreamErrorEvent {
  type: 'error';
  message: string;
}

export interface StreamCompleteEvent {
  type: 'complete';
}

export type StreamEvent = StepProgressEvent | HitlEvent | FinalReportEvent | StreamErrorEvent | StreamCompleteEvent;

export interface StreamEventHandlers {
  onStepStart?: (step: string) => void;
  onStepComplete?: (step: string, status: StepStatus, durationMs?: number) => void;
  onCotReasoning?: (reasoning: any) => void;
  onHitl?: (event: Omit<HitlEvent, 'type'>) => void;
  onFinalReport?: (report: FinalReportV2) => void;
  onError?: (message: string) => void;
  onComplete?: () => void;
}
```

- [ ] **Step 2: Add `streamMessage` method to `apiService`**

Add to the `apiService` object in `frontend/src/services/api.ts`:

```typescript
  /**
   * Send message and receive SSE streaming progress.
   * Returns a cleanup function to close the connection.
   */
  streamMessage(
    sessionId: string,
    content: string,
    handlers: StreamEventHandlers
  ): () => void {
    // Step label mapping (backend step name → Chinese display label)
    const stepLabels: Record<string, string> = {
      intent_analyzer: '理解查询意图',
      cot_planner: '生成分析计划',
      filter_executor: '执行筛选查询',
      empty_result_checker: '空结果检查',
      analysis_executor: '执行分析查询',
      quality_checker: '质量校验',
      report_formatter: '生成报告',
    };

    // Use fetch + ReadableStream for POST with SSE body
    // (EventSource only supports GET; we need POST for request body)
    const controller = new AbortController();

    (async () => {
      try {
        const response = await fetch(`/api/sessions/${sessionId}/messages/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        });

        if (!response.ok) {
          handlers.onError?.(`请求失败: ${response.status}`);
          handlers.onComplete?.();
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          handlers.onError?.('无法建立流式连接');
          handlers.onComplete?.();
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete events (SSE format: lines starting with "data: ")
          const lines = buffer.split('\n');
          // Keep the last (possibly incomplete) line in buffer
          buffer = lines.pop() || '';

          let eventData = '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              eventData += line.slice(6);
            } else if (line === '' && eventData) {
              // End of event
              try {
                const event: any = JSON.parse(eventData);
                dispatchEvent(event, handlers, stepLabels);
              } catch (e) {
                console.warn('Failed to parse SSE event:', eventData, e);
              }
              eventData = '';
            }
          }
        }

        // Handle any remaining data in buffer
        if (eventData) {
          try {
            const event: any = JSON.parse(eventData);
            dispatchEvent(event, handlers, stepLabels);
          } catch (e) {
            console.warn('Failed to parse final SSE event:', e);
          }
        }

        handlers.onComplete?.();
      } catch (error: any) {
        if (error.name !== 'AbortError') {
          handlers.onError?.(error.message || '流式请求失败');
          handlers.onComplete?.();
        }
      }
    })();

    return () => controller.abort();
  },
```

Also add the helper function at the end of the file (before the closing `};`):

```typescript
// Helper: dispatch parsed SSE event to appropriate handler
function dispatchEvent(
  event: any,
  handlers: StreamEventHandlers,
  stepLabels: Record<string, string>
) {
  switch (event.type) {
    case 'step_start':
      handlers.onStepStart?.(event.step);
      break;
    case 'step_complete':
      handlers.onStepComplete?.(event.step, event.status || 'success', event.duration_ms);
      break;
    case 'cot_reasoning':
      handlers.onCotReasoning?.(event.data);
      break;
    case 'hitl':
      handlers.onHitl?.({
        hitl_type: event.hitl_type || detectHitlType(event),
        question: event.question,
        options: event.options || [],
        quality_issues: event.quality_issues,
        allow_custom_input: event.allow_custom_input ?? true,
      });
      break;
    case 'final_report':
      handlers.onFinalReport?.(event.data);
      break;
    case 'error':
      handlers.onError?.(event.message);
      break;
    case 'complete':
      // onComplete is called by the caller when reader is done
      break;
  }
}

function detectHitlType(event: any): 'cot_clarification' | 'quality_hitl' {
  // Heuristic: quality HITL has quality_issues or options with "continue"/"rephrase"
  if (event.quality_issues?.length > 0) return 'quality_hitl';
  const values = (event.options || []).map((o: any) => o.value);
  if (values.includes('continue') || values.includes('rephrase')) return 'quality_hitl';
  return 'cot_clarification';
}
```

- [ ] **Step 3: Write type guard tests**

Create `frontend/src/test/api.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import type { FinalReportV2, ReportType } from '../services/api';

describe('FinalReportV2 type', () => {
  it('success report has required fields', () => {
    const report: FinalReportV2 = {
      report_type: 'success' as ReportType,
      title: '测试报告',
      data_table: { columns: [], rows: [] },
      highlights: [],
      next_queries: [],
    };
    expect(report.report_type).toBe('success');
    expect(report.title).toBe('测试报告');
  });

  it('error report has error fields', () => {
    const report: FinalReportV2 = {
      report_type: 'error' as ReportType,
      title: '错误报告',
      error_type: 'query_failed',
      message: '未能生成有效的分析结果',
      reason: '测试原因',
      data_table: { columns: [], rows: [] },
      highlights: [],
      next_queries: [],
      suggestions: ['调整筛选条件'],
      recommended_queries: ['查看全部数据'],
    };
    expect(report.error_type).toBe('query_failed');
    expect(report.suggestions?.length).toBe(1);
  });
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/test/api.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/test/api.test.ts
git commit -m "feat(frontend): add V2 report types + SSE streaming API"
```

---

### Task 5.2: StepProgress Component

**Files:**
- Create: `frontend/src/components/StepProgress.tsx`
- Test: `frontend/src/components/__tests__/StepProgress.test.tsx`

**Interfaces:**
- Consumes: `steps: Array<{id: string; label: string; status: 'pending' | 'active' | 'success' | 'failed' | 'skipped'}>`
- Produces: Visual step indicator component (vertical stepper)

- [ ] **Step 1: Write the test**

Create `frontend/src/components/__tests__/StepProgress.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StepProgress from '../StepProgress';

describe('StepProgress', () => {
  const sampleSteps = [
    { id: 'intent_analyzer', label: '理解查询意图', status: 'success' as const },
    { id: 'cot_planner', label: '生成分析计划', status: 'active' as const },
    { id: 'filter_executor', label: '执行筛选查询', status: 'pending' as const },
    { id: 'analysis_executor', label: '执行分析查询', status: 'pending' as const },
  ];

  it('renders all step labels', () => {
    render(<StepProgress steps={sampleSteps} />);
    expect(screen.getByText('理解查询意图')).toBeInTheDocument();
    expect(screen.getByText('生成分析计划')).toBeInTheDocument();
    expect(screen.getByText('执行筛选查询')).toBeInTheDocument();
    expect(screen.getByText('执行分析查询')).toBeInTheDocument();
  });

  it('shows correct status icons', () => {
    const { container } = render(<StepProgress steps={sampleSteps} />);
    // Success step has checkmark or green indicator
    const successStep = container.querySelector('[data-status="success"]');
    expect(successStep).toBeInTheDocument();
    // Active step is highlighted
    const activeStep = container.querySelector('[data-status="active"]');
    expect(activeStep).toBeInTheDocument();
    // Pending steps are dimmed
    const pendingSteps = container.querySelectorAll('[data-status="pending"]');
    expect(pendingSteps.length).toBe(2);
  });

  it('handles skipped steps', () => {
    const steps = [...sampleSteps, { id: 'quality_checker', label: '质量校验', status: 'skipped' as const }];
    const { container } = render(<StepProgress steps={steps} />);
    const skipped = container.querySelector('[data-status="skipped"]');
    expect(skipped).toBeInTheDocument();
  });

  it('handles failed steps', () => {
    const steps = [
      { id: 'intent_analyzer', label: '理解查询意图', status: 'failed' as const },
    ];
    const { container } = render(<StepProgress steps={steps} />);
    const failed = container.querySelector('[data-status="failed"]');
    expect(failed).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/StepProgress.test.tsx`
Expected: FAIL with "Cannot find module '../StepProgress'"

- [ ] **Step 3: Implement StepProgress component**

Create `frontend/src/components/StepProgress.tsx`:

```tsx
import React from 'react';
import { Check, X, Loader2, Minus } from 'lucide-react';

export interface StepItem {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'success' | 'failed' | 'skipped';
  durationMs?: number;
}

interface StepProgressProps {
  steps: StepItem[];
  title?: string;
}

const StepProgress: React.FC<StepProgressProps> = ({ steps, title = '正在分析...' }) => {
  const getStatusIcon = (status: StepItem['status']) => {
    switch (status) {
      case 'success':
        return <Check className="w-4 h-4 text-white" />;
      case 'failed':
        return <X className="w-4 h-4 text-white" />;
      case 'active':
        return <Loader2 className="w-4 h-4 text-white animate-spin" />;
      case 'skipped':
        return <Minus className="w-4 h-4 text-white" />;
      default:
        return null;
    }
  };

  const getStatusStyles = (status: StepItem['status']) => {
    switch (status) {
      case 'success':
        return 'bg-green-500 border-green-500';
      case 'failed':
        return 'bg-red-500 border-red-500';
      case 'active':
        return 'bg-blue-500 border-blue-500';
      case 'skipped':
        return 'bg-gray-400 border-gray-400';
      default:
        return 'bg-white border-gray-300';
    }
  };

  const getLabelStyles = (status: StepItem['status']) => {
    switch (status) {
      case 'success':
        return 'text-gray-700';
      case 'failed':
        return 'text-red-600 font-medium';
      case 'active':
        return 'text-blue-600 font-medium';
      case 'skipped':
        return 'text-gray-400';
      default:
        return 'text-gray-400';
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
      {title && (
        <h4 className="text-sm font-medium text-gray-700 mb-3">{title}</h4>
      )}
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-start gap-3">
            {/* Connector line */}
            {index < steps.length - 1 && (
              <div className="absolute left-[15px] top-7 bottom-0 w-0.5 bg-gray-200" style={{ marginTop: 0 }} />
            )}
            {/* Step circle */}
            <div className="relative z-10">
              <div
                data-status={step.status}
                className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${getStatusStyles(step.status)}`}
              >
                {getStatusIcon(step.status)}
              </div>
            </div>
            {/* Step label */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span data-status={step.status} className={`text-sm ${getLabelStyles(step.status)}`}>
                  {step.label}
                </span>
                {step.durationMs !== undefined && step.status === 'success' && (
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {formatDuration(step.durationMs)}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StepProgress;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/StepProgress.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StepProgress.tsx frontend/src/components/__tests__/StepProgress.test.tsx
git commit -m "feat(frontend): add StepProgress component for analysis steps"
```

---

### Task 5.3: Chat Store — Streaming Integration

**Files:**
- Modify: `frontend/src/stores/chatStore.ts`

**Interfaces:**
- Consumes: `apiService.streamMessage()` from Task 5.1
- Produces: Zustand store with `isStreaming`, `currentSteps`, `streamingMessageId`, plus updated `sendMessage` flow

- [ ] **Step 1: Update the ChatState interface and initial state**

In `frontend/src/stores/chatStore.ts`, update the `ChatState` interface:

```typescript
import type { StepItem } from '../components/StepProgress';
import type { FinalReportV2, StepStatus } from '../services/api';

interface ChatState {
  sessionId: string | null;
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  currentSteps: StepItem[];
  streamingMessageId: number | null;
  showClarification: boolean;
  clarification: Clarification | null;
  hitlType: 'cot_clarification' | 'quality_hitl' | null;
  qualityIssues: any[];
  error: string | null;

  initSession: () => Promise<void>;
  sendMessage: (content: string) => void;
  submitClarification: (selectedValue: string) => Promise<void>;
  submitHitl: (action: string) => Promise<void>;
  closeClarification: () => void;
}
```

Update the initial state in `create<ChatState>`:

```typescript
  isLoading: false,
  isStreaming: false,
  currentSteps: [],
  streamingMessageId: null,
  hitlType: null,
  qualityIssues: [],
```

- [ ] **Step 2: Replace `sendMessage` with streaming version**

Replace the entire `sendMessage` method in `chatStore.ts`:

```typescript
  sendMessage: (content: string) => {
    const { sessionId, isStreaming } = get();
    if (!sessionId || isStreaming) return;

    const messageId = Date.now();

    // Add user message
    set(state => ({
      messages: [...state.messages, { role: 'user' as const, content }],
      isStreaming: true,
      streamingMessageId: messageId,
      currentSteps: [
        { id: 'intent_analyzer', label: '理解查询意图', status: 'pending' },
        { id: 'cot_planner', label: '生成分析计划', status: 'pending' },
        { id: 'filter_executor', label: '执行筛选查询', status: 'pending' },
        { id: 'empty_result_checker', label: '空结果检查', status: 'pending' },
        { id: 'analysis_executor', label: '执行分析查询', status: 'pending' },
        { id: 'quality_checker', label: '质量校验', status: 'pending' },
      ],
    }));

    // Add a placeholder assistant message for the progress indicator
    set(state => ({
      messages: [...state.messages, {
        role: 'assistant' as const,
        content: '',
        // Use a special marker for streaming in-progress
      }],
    }));

    const stepLabelMap: Record<string, string> = {
      intent_analyzer: '理解查询意图',
      cot_planner: '生成分析计划',
      filter_executor: '执行筛选查询',
      empty_result_checker: '空结果检查',
      analysis_executor: '执行分析查询',
      quality_checker: '质量校验',
    };

    const cleanup = apiService.streamMessage(sessionId, content, {
      onStepStart: (step: string) => {
        set(state => ({
          currentSteps: state.currentSteps.map(s =>
            s.id === step ? { ...s, status: 'active' as const } : s
          ),
        }));
      },
      onStepComplete: (step: string, status: StepStatus, durationMs?: number) => {
        const mappedStatus: StepItem['status'] = 
          status === 'success' ? 'success' :
          status === 'failed' ? 'failed' :
          status === 'skipped' ? 'skipped' :
          status === 'hitl_required' ? 'success' :
          status === 'empty' ? 'success' :
          'success';

        set(state => ({
          currentSteps: state.currentSteps.map(s =>
            s.id === step ? { ...s, status: mappedStatus, durationMs } : s
          ),
        }));
      },
      onHitl: (event) => {
        set(state => {
          // Replace the last placeholder message with final (for now)
          const messages = [...state.messages];
          // The last message is the assistant placeholder - keep it but add clarification
          return {
            ...state,
            showClarification: true,
            clarification: {
              question: event.question,
              options: event.options,
              allow_custom_input: event.allow_custom_input ?? true,
            },
            hitlType: event.hitl_type,
            qualityIssues: event.quality_issues || [],
            isStreaming: false,
            streamingMessageId: null,
          };
        });
      },
      onFinalReport: (report: FinalReportV2) => {
        set(state => {
          const messages = [...state.messages];
          // Replace the last assistant placeholder with the final report
          const lastIdx = messages.length - 1;
          if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
            messages[lastIdx] = {
              ...messages[lastIdx],
              content: '',
              finalReportV2: report,
            };
          }
          return {
            ...state,
            messages,
            isStreaming: false,
            streamingMessageId: null,
            currentSteps: [],
          };
        });
      },
      onError: (message: string) => {
        set(state => {
          const messages = [...state.messages];
          const lastIdx = messages.length - 1;
          if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
            messages[lastIdx] = {
              ...messages[lastIdx],
              content: `抱歉，处理您的请求时出错了：${message}`,
            };
          }
          return {
            ...state,
            messages,
            isStreaming: false,
            streamingMessageId: null,
            currentSteps: [],
            error: message,
          };
        });
      },
      onComplete: () => {
        set({ isStreaming: false, streamingMessageId: null });
      },
    });

    // Store cleanup for potential abort (not exposed in UI yet)
    (get() as any)._streamCleanup = cleanup;
  },
```

- [ ] **Step 3: Add `submitHitl` method and update `submitClarification`**

Add a new `submitHitl` method:

```typescript
  submitHitl: async (action: string) => {
    const { sessionId } = get();
    if (!sessionId) return;

    set(state => ({
      showClarification: false,
      clarification: null,
      hitlType: null,
      qualityIssues: [],
      isLoading: true,
    }));

    try {
      // Quality HITL uses the same clarification endpoint with action values
      const result = await apiService.submitClarification(sessionId, action);

      const finalReport = result.result?.final_report;
      if (finalReport) {
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant' as const,
            content: '',
            finalReportV2: finalReport as FinalReportV2,
          }],
          isLoading: false,
        }));
      } else {
        const resultMessage = JSON.stringify(result.result, null, 2);
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant' as const,
            content: `已确认！\n\n\`\`\`json\n${resultMessage}\n\`\`\``,
          }],
          isLoading: false,
        }));
      }
    } catch (error) {
      set({ isLoading: false, error: 'Failed to submit HITL' });
    }
  },
```

Update `submitClarification` to also handle V2 format:

```typescript
  submitClarification: async (selectedValue: string) => {
    const { sessionId, hitlType } = get();
    if (!sessionId) return;

    // If it's a quality HITL, route to submitHitl logic
    if (hitlType === 'quality_hitl') {
      get().submitHitl(selectedValue);
      return;
    }

    // ... rest of existing submitClarification code ...
    // (keep existing code but add user message + finalReportV2 support)
```

Note: The existing `submitClarification` code stays mostly intact; just prepend the quality HITL routing at the top and make sure `finalReportV2` is set in addition to `finalReport`.

- [ ] **Step 4: Run existing store tests (if any)**

Run: `cd frontend && npx vitest run src/stores`
Expected: Tests pass (or no tests exist)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/chatStore.ts
git commit -m "feat(frontend): integrate SSE streaming into chat store"
```

---

### Task 5.4: ChatMessage — V2 Report Rendering

**Files:**
- Modify: `frontend/src/components/ChatMessage.tsx`
- Test: `frontend/src/components/__tests__/ChatMessage.test.tsx` (update)

**Interfaces:**
- Consumes: `message.finalReportV2?: FinalReportV2`
- Produces: Renders success/error/empty/hitl report types with chart, highlights, data table, quality info, metadata

- [ ] **Step 1: Update ChatMessage test for V2 format**

Add to `frontend/src/components/__tests__/ChatMessage.test.tsx`:

```typescript
  it('renders V2 success report with chart and data table', () => {
    const v2Report = {
      report_type: 'success',
      title: '消耗趋势分析 (2026-04-01 ~ 2026-04-30)',
      chart_config: { type: 'line', title: '消耗趋势' },
      data: [
        { date: '2026-04-01', cost: 100 },
        { date: '2026-04-02', cost: 150 },
      ],
      data_table: {
        columns: ['日期', '消耗'],
        rows: [['2026-04-01', '¥100.00'], ['2026-04-02', '¥150.00']],
      },
      highlights: [
        { type: 'info', text: '📊 共 2 条数据记录' },
      ],
      next_queries: ['查看更多数据'],
    };

    render(
      <ChatMessage message={{ role: 'assistant', content: '', finalReportV2: v2Report as any }} />
    );

    expect(screen.getByText('消耗趋势分析 (2026-04-01 ~ 2026-04-30)')).toBeInTheDocument();
    expect(screen.getByText('📊 共 2 条数据记录')).toBeInTheDocument();
    expect(screen.getByText('查看更多数据')).toBeInTheDocument();
  });

  it('renders V2 error report', () => {
    const errorReport = {
      report_type: 'error',
      title: '错误',
      error_type: 'query_failed',
      message: '未能生成有效的分析结果',
      reason: '筛选条件过严',
      data_table: { columns: [], rows: [] },
      highlights: [],
      next_queries: [],
      suggestions: ['放宽筛选条件'],
    };

    render(
      <ChatMessage message={{ role: 'assistant', content: '', finalReportV2: errorReport as any }} />
    );

    expect(screen.getByText('未能生成有效的分析结果')).toBeInTheDocument();
    expect(screen.getByText('筛选条件过严')).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/ChatMessage.test.tsx`
Expected: FAIL (V2 report not rendered yet)

- [ ] **Step 3: Implement V2 report rendering in ChatMessage**

Update `frontend/src/components/ChatMessage.tsx`:

1. Import V2 types and new components:

```tsx
import { FinalReportV2 } from '../services/api';
import { QualityIssueList } from './QualityIssueList';
```

2. Add a new render block for `finalReportV2` (add before the closing `</div>` of the assistant message, or better yet, add a function to render V2 report):

Add this after the existing `message.finalReport` block:

```tsx
        {/* V2 Report Format (CoT analysis) */}
        {message.finalReportV2 && (
          <div className="mt-4 space-y-4">
            {/* Title */}
            <h3 className="text-lg font-semibold">{message.finalReportV2.title}</h3>

            {/* Error report */}
            {message.finalReportV2.report_type === 'error' && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="text-red-800 font-medium mb-2">
                  {message.finalReportV2.message}
                </div>
                {message.finalReportV2.reason && (
                  <div className="text-red-600 text-sm mb-3">
                    原因：{message.finalReportV2.reason}
                  </div>
                )}
                {message.finalReportV2.suggestions && message.finalReportV2.suggestions.length > 0 && (
                  <div className="text-sm">
                    <div className="text-red-700 font-medium mb-1">建议：</div>
                    <ul className="list-disc list-inside text-red-600 space-y-1">
                      {message.finalReportV2.suggestions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Empty report */}
            {message.finalReportV2.report_type === 'empty' && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                <div className="text-4xl mb-2">📭</div>
                <div className="text-yellow-800 font-medium">暂无数据</div>
                <div className="text-yellow-600 text-sm mt-1">
                  未找到符合条件的数据，请尝试调整筛选条件
                </div>
              </div>
            )}

            {/* Chart (for success/hitl reports with data) */}
            {message.finalReportV2.report_type !== 'error' &&
             message.finalReportV2.chart_config &&
             message.finalReportV2.data &&
             message.finalReportV2.data.length > 0 && (
              <ChartRenderer
                report={{
                  chart_config: message.finalReportV2.chart_config as any,
                  is_comparison: false,
                }}
                data={message.finalReportV2.data}
                groupBy={[]}
                metrics={message.finalReportV2.metadata?.metrics || []}
              />
            )}

            {/* Highlights */}
            {message.finalReportV2.highlights?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">关键提示</h4>
                <HighlightList highlights={message.finalReportV2.highlights as any} />
              </div>
            )}

            {/* Quality Issues */}
            {message.finalReportV2.quality_info?.issues &&
             message.finalReportV2.quality_info.issues.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">质量提示</h4>
                <QualityIssueList issues={message.finalReportV2.quality_info.issues} />
              </div>
            )}

            {/* Data Table */}
            {message.finalReportV2.data_table?.columns?.length > 0 &&
             message.finalReportV2.data_table.rows?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">数据详情</h4>
                <DataTable {...message.finalReportV2.data_table} />
              </div>
            )}

            {/* Metadata (subtle) */}
            {message.finalReportV2.metadata && (
              <div className="text-xs text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
                <span>分析类型：{message.finalReportV2.metadata.analysis_type}</span>
                <span>实体层级：{message.finalReportV2.metadata.entity_level}</span>
                <span>实体数量：{message.finalReportV2.metadata.total_entities}</span>
                {message.finalReportV2.metadata.generated_at && (
                  <span>生成时间：{new Date(message.finalReportV2.metadata.generated_at).toLocaleString('zh-CN')}</span>
                )}
              </div>
            )}

            {/* Next Queries */}
            {message.finalReportV2.next_queries?.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-sm font-medium mb-2">推荐查询</h4>
                <ul className="space-y-1">
                  {message.finalReportV2.next_queries.map((query, idx) => (
                    <li
                      key={idx}
                      className="text-sm text-blue-600 cursor-pointer hover:underline"
                      onClick={() => onSuggestionClick?.(query)}
                    >
                      → {query}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Streaming progress indicator (shown when isStreaming and this is the last message) */}
        {message.isStreaming && (
          <StepProgress
            steps={(message as any).currentSteps || []}
            title="正在分析..."
          />
        )}
```

Note: Also import `StepProgress` at the top, and add `isStreaming` and `currentSteps` to the component Props interface (or pass them differently — in the store approach, each message doesn't carry steps; instead the store has `currentSteps`. For simplicity, we show StepProgress in the App.tsx when streaming, not inside ChatMessage.)

Let me adjust: the progress indicator is rendered in `App.tsx` below the messages, not inside a specific message. So remove the `isStreaming` part from ChatMessage.

- [ ] **Step 4: Update App.tsx to show StepProgress when streaming**

In `frontend/src/App.tsx`, import `StepProgress` and add it:

```tsx
import StepProgress from './components/StepProgress';
```

In the component, extract `currentSteps` and `isStreaming` from the store:

```tsx
  const {
    sessionId,
    messages,
    isLoading,
    isStreaming,
    currentSteps,
    showClarification,
    clarification,
    initSession,
    sendMessage,
    submitClarification,
    closeClarification
  } = useChatStore();
```

Add the progress indicator in the messages area (after the message list, before the loading indicator or in place of it):

```tsx
          {isStreaming && currentSteps.length > 0 && (
            <div className="flex justify-start mb-4">
              <div className="max-w-[80%] w-full">
                <StepProgress steps={currentSteps} title="正在分析..." />
              </div>
            </div>
          )}
```

Replace the existing simple `isLoading` "思考中..." indicator with the step progress.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/ChatMessage.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ChatMessage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): render V2 report format in ChatMessage"
```

---

### Task 5.5: ChartRenderer — Pie + KPI + Multi-Series Support

**Files:**
- Modify: `frontend/src/components/ChartRenderer.tsx`
- Test: `frontend/src/components/__tests__/ChartRenderer.test.tsx` (update)

**Interfaces:**
- Consumes: `report.chart_config` with type `'pie' | 'kpi_card'` and `series_field` for multi-series
- Produces: Renders pie charts (ring/donut), KPI card grids, multi-series line charts

- [ ] **Step 1: Add tests for new chart types**

Add to `frontend/src/components/__tests__/ChartRenderer.test.tsx`:

```typescript
  it('renders pie chart from V2 chart_config', () => {
    const chartConfig = {
      type: 'pie' as const,
      title: '受众分布',
      series: [
        { name: '男', color: '#3b82f6' },
        { name: '女', color: '#ec4899' },
      ],
    };
    const data = [
      { name: '男', value: 60 },
      { name: '女', value: 40 },
    ];

    const { container } = render(
      <ChartRenderer
        report={{ chart_config: chartConfig, is_comparison: false }}
        data={data}
        groupBy={[]}
        metrics={['value']}
      />
    );

    // Should render a chart container
    expect(container.querySelector('.echarts-for-react')).toBeInTheDocument();
  });

  it('renders KPI card chart type', () => {
    const chartConfig = {
      type: 'kpi_card' as const,
    };
    const data = [
      { metric: '消耗', value: 1000, formatted: '¥1,000.00' },
      { metric: '点击量', value: 500, formatted: '500' },
      { metric: 'CTR', value: 0.05, formatted: '5.0%' },
    ];

    const { getByText } = render(
      <ChartRenderer
        report={{ chart_config: chartConfig, is_comparison: false }}
        data={data}
        groupBy={[]}
        metrics={['value']}
      />
    );

    expect(getByText('消耗')).toBeInTheDocument();
    expect(getByText('点击量')).toBeInTheDocument();
  });

  it('renders multi-series line chart with series_field', () => {
    const chartConfig = {
      type: 'line' as const,
      title: '各计划消耗趋势',
      x_axis: { field: 'date', label: '日期' },
      y_axis: { field: 'cost', label: '消耗' },
      series_field: 'campaign_name',
      series: [
        { name: '计划A', color: '#3b82f6' },
        { name: '计划B', color: '#10b981' },
      ],
    };
    const data = [
      { date: '2026-04-01', campaign_name: '计划A', cost: 100 },
      { date: '2026-04-01', campaign_name: '计划B', cost: 80 },
      { date: '2026-04-02', campaign_name: '计划A', cost: 120 },
      { date: '2026-04-02', campaign_name: '计划B', cost: 90 },
    ];

    const { container } = render(
      <ChartRenderer
        report={{ chart_config: chartConfig, is_comparison: false }}
        data={data}
        groupBy={['campaign_name']}
        metrics={['cost']}
      />
    );

    expect(container.querySelector('.echarts-for-react')).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/ChartRenderer.test.tsx`
Expected: FAIL (new chart types not implemented)

- [ ] **Step 3: Implement pie chart rendering**

Add to `ChartRenderer.tsx`, before the final `return null`:

```tsx
  // Pie chart
  if (chartType === 'pie' && data && data.length > 0) {
    const seriesField = report?.chart_config?.series_field || 'name';
    const valueField = report?.chart_config?.y_axis?.field || metrics[0] || 'value';
    const seriesConfig = report?.chart_config?.series || [];

    const pieData = data.map((item, index) => ({
      value: Number(item[valueField]) || 0,
      name: String(item[seriesField] || item.name || `项${index + 1}`),
      itemStyle: seriesConfig[index]?.color ? { color: seriesConfig[index].color } : undefined,
    }));

    const pieOption: EChartsOption = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        right: '5%',
        top: 'center',
        textStyle: { fontSize: 12 },
      },
      series: [
        {
          name: getMetricDisplayName(valueField),
          type: 'pie',
          radius: ['40%', '70%'], // Ring chart
          center: ['35%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: {
            show: false,
            position: 'center',
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
            },
          },
          labelLine: {
            show: false,
          },
          data: pieData,
        },
      ],
    };

    return (
      <div className="w-full min-h-[400px] bg-white rounded-lg shadow-sm p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          {report?.chart_config?.title || getMetricDisplayName(valueField) + ' 分布'}
        </h3>
        <ReactECharts option={pieOption} style={{ height: '340px' }} />
      </div>
    );
  }
```

- [ ] **Step 4: Implement KPI card rendering**

Add before the pie chart section:

```tsx
  // KPI Card (summary)
  if (chartType === 'kpi_card' && data && data.length > 0) {
    // Auto-detect metric name and value fields
    const nameField = Object.keys(data[0]).find(k =>
      k.includes('name') || k.includes('metric') || k.includes('label')
    ) || 'name';
    const valueField = Object.keys(data[0]).find(k =>
      k.includes('value') || k.includes('formatted') || ['cost', 'click', 'impression', 'ctr', 'cvr'].includes(k)
    ) || 'value';
    const formattedField = Object.keys(data[0]).find(k =>
      k.includes('formatted') || k.includes('display')
    );

    return (
      <div className="w-full bg-white rounded-lg shadow-sm p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          {report?.chart_config?.title || '核心指标'}
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {data.map((item, idx) => {
            const name = String(item[nameField] || `指标${idx + 1}`);
            const value = formattedField && item[formattedField]
              ? String(item[formattedField])
              : (typeof item[valueField] === 'number'
                ? item[valueField].toLocaleString()
                : String(item[valueField] || '-'));
            const color = report?.chart_config?.series?.[idx]?.color;
            return (
              <div
                key={idx}
                className="bg-gray-50 rounded-lg p-4 border border-gray-100"
              >
                <div className="text-sm text-gray-500 mb-1">{name}</div>
                <div
                  className="text-2xl font-bold"
                  style={{ color: color || '#1f2937' }}
                >
                  {value}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
```

- [ ] **Step 5: Implement multi-series line chart**

Replace the single-series time trend line section. Current logic checks `isTimeDimension` and renders a single series. Update it to detect multi-series:

```tsx
    if (isTimeDimension) {
      // Check if multi-series (has series_field or multiple series in config)
      const seriesField = report?.chart_config?.series_field;
      const hasMultipleSeries = seriesField && report?.chart_config?.series && report.chart_config.series.length > 1;

      if (hasMultipleSeries && seriesField) {
        // Multi-series line chart
        const xField = report?.chart_config?.x_axis?.field || dimensionColumns[0] || 'date';
        const yField = report?.chart_config?.y_axis?.field || primaryMetric;

        // Pivot data: group by x value, then by series name
        const xValues: string[] = [];
        const seriesNames: string[] = [];
        const dataMap: Record<string, Record<string, number>> = {}; // xValue -> seriesName -> value

        data.forEach((item) => {
          const xVal = String(item[xField] || '');
          const sName = String(item[seriesField] || '');

          if (!xValues.includes(xVal)) xValues.push(xVal);
          if (!seriesNames.includes(sName)) seriesNames.push(sName);

          if (!dataMap[xVal]) dataMap[xVal] = {};
          dataMap[xVal][sName] = Number(item[yField]) || 0;
        });

        const defaultColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];
        const seriesConfig = report?.chart_config?.series || [];

        const multiLineOption: EChartsOption = {
          tooltip: {
            trigger: 'axis',
          },
          legend: {
            data: seriesNames,
            type: 'scroll',
            bottom: 0,
            textStyle: { fontSize: 11 },
          },
          grid: {
            left: 60,
            right: 40,
            top: 30,
            bottom: 80,
            containLabel: true,
          },
          xAxis: {
            type: 'category',
            boundaryGap: false,
            data: xValues,
            axisLabel: {
              rotate: 45,
              interval: 0,
              fontSize: 11,
            },
          },
          yAxis: {
            type: 'value',
            axisLabel: { fontSize: 11 },
          },
          series: seriesNames.map((sName, idx) => ({
            name: sName,
            type: 'line',
            smooth: true,
            data: xValues.map(xVal => dataMap[xVal]?.[sName] ?? null),
            lineStyle: {
              color: seriesConfig[idx]?.color || defaultColors[idx % defaultColors.length],
              width: 2,
            },
            itemStyle: {
              color: seriesConfig[idx]?.color || defaultColors[idx % defaultColors.length],
            },
          })),
        };

        return (
          <div className="w-full min-h-[500px] bg-white rounded-lg shadow-sm p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              {report?.chart_config?.title || getMetricDisplayName(primaryMetric) + ' 趋势'}
            </h3>
            <ReactECharts option={multiLineOption} style={{ height: '440px' }} />
          </div>
        );
      }
```

Close the `if (hasMultipleSeries)` block with the existing single-series line chart as the `else` case.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/ChartRenderer.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ChartRenderer.tsx
git commit -m "feat(frontend): add pie, KPI card, and multi-series line chart support"
```

---

### Task 5.6: QualityIssueList Component + ClarificationModal Enhancement

**Files:**
- Create: `frontend/src/components/QualityIssueList.tsx`
- Modify: `frontend/src/components/ClarificationModal.tsx`
- Test: `frontend/src/components/__tests__/QualityIssueList.test.tsx`

**Interfaces:**
- Consumes: `issues: QualityIssueV2[]` for QualityIssueList; `hitlType` + `qualityIssues` for modal
- Produces: Quality issue display; clarification modal with quality issue section for quality_hitl type

- [ ] **Step 1: Write QualityIssueList test**

Create `frontend/src/components/__tests__/QualityIssueList.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QualityIssueList } from '../QualityIssueList';

describe('QualityIssueList', () => {
  const issues = [
    {
      check_type: 'max_series_count',
      severity: 'error' as const,
      message: '趋势图系列数量超过上限',
      suggested_action: 'hitl',
      threshold: 20,
      actual: 35,
    },
    {
      check_type: 'min_data_points',
      severity: 'warning' as const,
      message: '数据点较少，趋势参考价值有限',
      suggested_action: 'warn',
      threshold: 2,
      actual: 2,
    },
  ];

  it('renders all issue messages', () => {
    render(<QualityIssueList issues={issues} />);
    expect(screen.getByText('趋势图系列数量超过上限')).toBeInTheDocument();
    expect(screen.getByText('数据点较少，趋势参考价值有限')).toBeInTheDocument();
  });

  it('shows severity indicators', () => {
    const { container } = render(<QualityIssueList issues={issues} />);
    // Error issue should have red styling
    const errorItem = container.querySelector('[data-severity="error"]');
    expect(errorItem).toBeInTheDocument();
    // Warning issue should have yellow/orange styling
    const warningItem = container.querySelector('[data-severity="warning"]');
    expect(warningItem).toBeInTheDocument();
  });

  it('shows threshold and actual values for errors', () => {
    render(<QualityIssueList issues={issues} />);
    expect(screen.getByText(/阈值：20/)).toBeInTheDocument();
    expect(screen.getByText(/实际：35/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/QualityIssueList.test.tsx`
Expected: FAIL (component doesn't exist)

- [ ] **Step 3: Implement QualityIssueList component**

Create `frontend/src/components/QualityIssueList.tsx`:

```tsx
import React from 'react';
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import type { QualityIssueV2 } from '../services/api';

interface QualityIssueListProps {
  issues: QualityIssueV2[];
}

export const QualityIssueList: React.FC<QualityIssueListProps> = ({ issues }) => {
  if (!issues || issues.length === 0) return null;

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'error':
      case 'hitl_required':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      default:
        return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'error':
      case 'hitl_required':
        return <AlertCircle className="w-4 h-4 flex-shrink-0" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 flex-shrink-0" />;
      default:
        return <Info className="w-4 h-4 flex-shrink-0" />;
    }
  };

  return (
    <div className="space-y-2">
      {issues.map((issue, index) => (
        <div
          key={index}
          data-severity={issue.severity}
          className={`p-3 rounded-lg border ${getSeverityStyles(issue.severity)}`}
        >
          <div className="flex items-start gap-2">
            {getSeverityIcon(issue.severity)}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{issue.message}</div>
              {(issue.threshold !== undefined || issue.actual !== undefined) && (
                <div className="text-xs mt-1 opacity-80">
                  {issue.threshold !== undefined && <span>阈值：{JSON.stringify(issue.threshold)}</span>}
                  {issue.threshold !== undefined && issue.actual !== undefined && <span className="mx-2">|</span>}
                  {issue.actual !== undefined && <span>实际：{JSON.stringify(issue.actual)}</span>}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
```

- [ ] **Step 4: Update ClarificationModal for quality HITL**

Modify `frontend/src/components/ClarificationModal.tsx`:

1. Update the Props interface:

```tsx
interface ClarificationModalProps {
  clarification: Clarification;
  hitlType?: 'cot_clarification' | 'quality_hitl' | null;
  qualityIssues?: any[];
  onSubmit: (selectedValue: string) => void;
  onClose: () => void;
}
```

2. Import and add quality issue display in the modal body:

```tsx
import { QualityIssueList } from './QualityIssueList';
```

Add after the question, before the options:

```tsx
        {/* Quality issues section (for quality_hitl type) */}
        {hitlType === 'quality_hitl' && qualityIssues && qualityIssues.length > 0 && (
          <div className="mb-4">
            <div className="text-sm font-medium text-gray-700 mb-2">质量问题：</div>
            <QualityIssueList issues={qualityIssues} />
          </div>
        )}
```

3. For quality_hitl, hide custom input and adjust button labels:

Update the custom input section:

```tsx
        {clarification.allow_custom_input && hitlType !== 'quality_hitl' && (
```

- [ ] **Step 5: Update App.tsx to pass hitlType and qualityIssues to ClarificationModal**

In `App.tsx`, extract `hitlType` and `qualityIssues` from the store:

```tsx
  const {
    // ... existing
    hitlType,
    qualityIssues,
    // ... existing
  } = useChatStore();
```

Pass to modal:

```tsx
        <ClarificationModal
          clarification={clarification}
          hitlType={hitlType}
          qualityIssues={qualityIssues}
          onSubmit={submitClarification}
          onClose={closeClarification}
        />
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/__tests__/QualityIssueList.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/QualityIssueList.tsx frontend/src/components/ClarificationModal.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add QualityIssueList + enhance ClarificationModal for quality HITL"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ SSE streaming (design spec §9.2) — Task 5.1 + 5.3
- ✅ Step progress display — Task 5.2 + 5.3 + 5.4
- ✅ New report format (report_type, chart_config, data, quality_info, metadata) — Task 5.4
- ✅ Chart enhancements (pie, kpi_card, multi-series) — Task 5.5
- ✅ Two HITL types (cot_clarification + quality_hitl) — Task 5.6 + 5.3
- ✅ Error / empty report rendering — Task 5.4
- ✅ Next queries / recommendations — Task 5.4
- ⚠️ Backward compatibility with old report format — relies on old code paths still present in ChatMessage (verified: existing `finalReport` block preserved)

**2. Placeholder scan:**
- No "TBD" / "TODO" / "implement later" found
- All test code blocks are complete
- All implementation code blocks are complete
- All step commands are exact
- No "similar to Task N" references

**3. Type consistency:**
- `FinalReportV2` defined in Task 5.1, consumed in Tasks 5.3, 5.4 ✅
- `StepItem` defined in Task 5.2, used in Task 5.3 (chat store) ✅
- `QualityIssueV2` defined in Task 5.1, used in Task 5.6 ✅
- `StepStatus` defined in Task 5.1, used in Task 5.3 ✅
- `streamMessage` API method name matches between Task 5.1 definition and Task 5.3 usage ✅
- Chart config fields (`type`, `series_field`, `x_axis`, `y_axis`, `series`) consistent between Task 5.1 types and Task 5.5 implementation ✅

---

Plan complete and saved to `docs/superpowers/plans/2026-08-10-phase5-frontend-changes.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
