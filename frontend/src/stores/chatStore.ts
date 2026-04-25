import { create } from 'zustand';
import { apiService, Message, Clarification } from '../services/api';

interface ChatState {
  sessionId: string | null;
  messages: Message[];
  isLoading: boolean;
  showClarification: boolean;
  clarification: Clarification | null;
  error: string | null;

  initSession: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  submitClarification: (selectedValue: string) => Promise<void>;
  closeClarification: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  messages: [],
  isLoading: false,
  showClarification: false,
  clarification: null,
  error: null,

  initSession: async () => {
    try {
      const session = await apiService.createSession();
      set({ sessionId: session.session_id });

      // Add welcome message
      set(state => ({
        messages: [...state.messages, {
          role: 'assistant',
          content: '你好！我是广告报表智能助手。你可以问我：\n\n- "看上周的曝光点击"\n- "按渠道看 CTR"\n- "安卓端的花费"\n\n或者其他关于广告报表的问题。',
        }]
      }));
    } catch (error) {
      set({ error: 'Failed to create session' });
    }
  },

  sendMessage: async (content: string) => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({ isLoading: true });

    // Add user message
    set(state => ({
      messages: [...state.messages, { role: 'user', content }]
    }));

    try {
      const result = await apiService.sendMessage(sessionId, content);

      if (result.status === 'waiting_for_clarification') {
        set({
          showClarification: true,
          clarification: result.clarification,
          isLoading: false,
        });
      } else {
        // 如果有 final_report，用它渲染报表；否则显示 JSON
        const finalReport = result.result?.final_report;
        if (finalReport) {
          set(state => ({
            messages: [...state.messages, {
              role: 'assistant',
              content: '',
              finalReport,
            }],
            isLoading: false,
          }));
        } else {
          const resultMessage = JSON.stringify(result.result?.query_intent || result.result, null, 2);
          set(state => ({
            messages: [...state.messages, {
              role: 'assistant',
              content: `查询成功！\n\n\`\`\`json\n${resultMessage}\n\`\`\``,
            }],
            isLoading: false,
          }));
        }
      }
    } catch (error) {
      set(state => ({
        messages: [...state.messages, {
          role: 'assistant',
          content: '抱歉，处理您的请求时出错了。',
        }],
        isLoading: false,
      }));
    }
  },

  submitClarification: async (selectedValue: string) => {
    const { sessionId } = get();
    if (!sessionId) return;

    set({ isLoading: true });

    try {
      const result = await apiService.submitClarification(sessionId, selectedValue);

      const finalReport = result.result?.final_report;
      if (finalReport) {
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant',
            content: '',
            finalReport,
          }],
          showClarification: false,
          clarification: null,
          isLoading: false,
        }));
      } else {
        const resultMessage = JSON.stringify(result.result, null, 2);
        set(state => ({
          messages: [...state.messages, {
            role: 'assistant',
            content: `已确认！\n\n\`\`\`json\n${resultMessage}\n\`\`\``,
          }],
          showClarification: false,
          clarification: null,
          isLoading: false,
        }));
      }
    } catch (error) {
      set({ isLoading: false, error: 'Failed to submit clarification' });
    }
  },

  closeClarification: () => {
    set({ showClarification: false, clarification: null });
  },
}));
