import { create } from 'zustand';
import { apiService, Message, Clarification, FinalReportV2, StepStatus } from '../services/api';
import type { StepItem } from '../components/StepProgress';

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

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  currentSteps: [],
  streamingMessageId: null,
  showClarification: false,
  clarification: null,
  hitlType: null,
  qualityIssues: [],
  error: null,

  initSession: async () => {
    try {
      const session = await apiService.createSession();
      set({ sessionId: session.session_id });

      // Add welcome message（只在没有消息时添加，避免重复）
      set(state => {
        if (state.messages.length > 0) return state;
        return {
          messages: [...state.messages, {
            role: 'assistant',
            content: '你好！我是广告报表智能助手。你可以问我：\n\n- "都有哪些广告主？"\n- "mini_6_autumn 最近三个月哪些广告表现好？哪些广告表现不好？"\n- "mini_6_autumn 最近三个月的点击量按性别和月细分"\n- "mini_6_autumn 最近三个月 CTR 表现最好和最差的广告分别是哪些？"\n\n或者其他关于广告报表的问题。',
          }]
        };
      });
    } catch (error) {
      set({ error: 'Failed to create session' });
    }
  },

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
        set(state => ({
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
        }));
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

  submitClarification: async (selectedValue: string) => {
    const { sessionId, hitlType } = get();
    if (!sessionId) return;

    // If it's a quality HITL, route to submitHitl logic
    if (hitlType === 'quality_hitl') {
      get().submitHitl(selectedValue);
      return;
    }

    // 点确认后立即关闭弹窗并进入加载状态，不用等 API 返回
    set(state => ({
      showClarification: false,
      clarification: null,
      isLoading: true,
      messages: [...state.messages, {
        role: 'user',
        content: selectedValue,
      }],
    }));

    try {
      const result = await apiService.submitClarification(sessionId, selectedValue);

      const finalReport = result.result?.final_report;
      const finalReportV2 = result.result?.final_report;
      if (finalReportV2) {
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant',
            content: '',
            finalReportV2: finalReportV2 as FinalReportV2,
            finalReport,
          }],
          isLoading: false,
        }));
      } else if (finalReport) {
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant',
            content: '',
            finalReport,
          }],
          isLoading: false,
        }));
      } else {
        const resultMessage = JSON.stringify(result.result, null, 2);
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant',
            content: `已确认！\n\n\`\`\`json\n${resultMessage}\n\`\`\``,
          }],
          isLoading: false,
        }));
      }
    } catch (error) {
      set({ isLoading: false, error: 'Failed to submit clarification' });
    }
  },

  submitHitl: async (action: string) => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({
      showClarification: false,
      clarification: null,
      hitlType: null,
      qualityIssues: [],
      isLoading: true,
    });

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

  closeClarification: () => {
    set({ showClarification: false, clarification: null });
  },
}));
