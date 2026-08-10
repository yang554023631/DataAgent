import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export type InsightType = 'problem' | 'highlight' | 'info';
export type Severity = 'high' | 'medium' | 'low';

export interface Insight {
  id: string;
  type: InsightType;
  name: string;
  severity: Severity;
  evidence: string;
  suggestion: string;
  source: string;
}

export interface FinalReport {
  title: string;
  time_range?: { start: string; end: string };
  metrics: Array<{ name: string; value: string | number; trend?: string }>;
  highlights: Array<{ type: 'positive' | 'negative' | 'info'; text: string }>;
  insights?: {
    problems: Insight[];
    highlights: Insight[];
    summary?: string;
  };
  data_table: { columns: string[]; rows: any[][] };
  next_queries: string[];
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  finalReport?: FinalReport;
  finalReportV2?: FinalReportV2;
}

export interface Clarification {
  question: string;
  options: Array<{ value: string; label: string }>;
  allow_custom_input: boolean;
}

export interface Session {
  session_id: string;
}

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

export const apiService = {
  async createSession(): Promise<Session> {
    const response = await api.post('/sessions', {});
    return response.data;
  },

  async sendMessage(sessionId: string, content: string) {
    const response = await api.post(`/sessions/${sessionId}/messages`, { content });
    return response.data;
  },

  async submitClarification(sessionId: string, selectedValue: string) {
    const response = await api.post(`/sessions/${sessionId}/clarification`, {
      selected_value: selectedValue,
    });
    return response.data;
  },

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
        let eventData = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete events (SSE format: lines starting with "data: ")
          const lines = buffer.split('\n');
          // Keep the last (possibly incomplete) line in buffer
          buffer = lines.pop() || '';

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
};

// Helper: dispatch parsed SSE event to appropriate handler
// Exported for testing
export function dispatchEvent(
  event: any,
  handlers: StreamEventHandlers,
  _stepLabels: Record<string, string>
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

// Exported for testing
export function detectHitlType(event: any): 'cot_clarification' | 'quality_hitl' {
  // Heuristic: quality HITL has quality_issues or options with "continue"/"rephrase"
  if (event.quality_issues?.length > 0) return 'quality_hitl';
  const values = (event.options || []).map((o: any) => o.value);
  if (values.includes('continue') || values.includes('rephrase')) return 'quality_hitl';
  return 'cot_clarification';
}
