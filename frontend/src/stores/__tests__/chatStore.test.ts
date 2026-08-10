import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useChatStore } from '../chatStore'

// Mock apiService - streamMessage simulates SSE flow synchronously
vi.mock('../../services/api', () => ({
  apiService: {
    createSession: vi.fn().mockResolvedValue({ session_id: 'test-session-123' }),
    streamMessage: vi.fn(),
    submitClarification: vi.fn(),
  },
  Message: {} as any,
  Clarification: {} as any,
  FinalReportV2: {} as any,
  StepStatus: {} as any,
  QualityIssueV2: {} as any,
}))

import { apiService } from '../../services/api'

// Helper to create a mock streamMessage that fires callbacks synchronously
const mockStreamSuccess = (report: any) => {
  (apiService.streamMessage as any).mockImplementation(
    (_sessionId: string, _content: string, handlers: any) => {
      handlers.onStepStart?.('intent_analyzer');
      handlers.onStepComplete?.('intent_analyzer', 'success', 100);
      handlers.onStepStart?.('cot_planner');
      handlers.onStepComplete?.('cot_planner', 'success', 200);
      handlers.onStepStart?.('filter_executor');
      handlers.onStepComplete?.('filter_executor', 'success', 150);
      handlers.onStepStart?.('empty_result_checker');
      handlers.onStepComplete?.('empty_result_checker', 'success', 50);
      handlers.onStepStart?.('analysis_executor');
      handlers.onStepComplete?.('analysis_executor', 'success', 300);
      handlers.onStepStart?.('quality_checker');
      handlers.onStepComplete?.('quality_checker', 'success', 100);
      handlers.onFinalReport?.(report);
      handlers.onComplete?.();
      return () => {}; // no-op cleanup
    }
  );
};

const mockStreamHitl = (hitlType: 'cot_clarification' | 'quality_hitl', extra: any = {}) => {
  (apiService.streamMessage as any).mockImplementation(
    (_sessionId: string, _content: string, handlers: any) => {
      handlers.onStepStart?.('intent_analyzer');
      handlers.onStepComplete?.('intent_analyzer', 'success', 100);
      handlers.onStepStart?.('analysis_executor');
      handlers.onStepComplete?.('analysis_executor', 'hitl_required', 200);
      handlers.onHitl?.({
        hitl_type: hitlType,
        question: '请选择维度',
        options: [
          { value: '渠道', label: '渠道' },
          { value: '创意', label: '创意' },
        ],
        allow_custom_input: false,
        ...extra,
      });
      return () => {};
    }
  );
};

const mockStreamError = (message: string) => {
  (apiService.streamMessage as any).mockImplementation(
    (_sessionId: string, _content: string, handlers: any) => {
      handlers.onStepStart?.('intent_analyzer');
      handlers.onError?.(message);
      handlers.onComplete?.();
      return () => {};
    }
  );
};

describe('chatStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useChatStore.setState({
      sessionId: null,
      messages: [],
      isLoading: false,
      isStreaming: false,
      currentSteps: [],
      showClarification: false,
      clarification: null,
      hitlType: null,
      qualityIssues: [],
      error: null,
      _streamCleanup: undefined,
    })
    vi.clearAllMocks()
  })

  describe('初始化状态', () => {
    it('应该有正确的初始状态', () => {
      const state = useChatStore.getState()

      expect(state.sessionId).toBeNull()
      expect(state.messages).toEqual([])
      expect(state.isLoading).toBe(false)
      expect(state.isStreaming).toBe(false)
      expect(state.currentSteps).toEqual([])
      expect(state.showClarification).toBe(false)
      expect(state.clarification).toBeNull()
      expect(state.hitlType).toBeNull()
      expect(state.qualityIssues).toEqual([])
      expect(state.error).toBeNull()
    })
  })

  describe('initSession', () => {
    it('应该创建 session 并添加欢迎消息', async () => {
      const { initSession } = useChatStore.getState()

      await initSession()

      expect(apiService.createSession).toHaveBeenCalled()
      expect(useChatStore.getState().sessionId).toBe('test-session-123')
      expect(useChatStore.getState().messages).toHaveLength(1)
      expect(useChatStore.getState().messages[0].role).toBe('assistant')
      expect(useChatStore.getState().messages[0].content).toContain('你好！我是广告报表智能助手')
    })

    it('API 失败时应该设置 error 状态', async () => {
      (apiService.createSession as any).mockRejectedValueOnce(new Error('API Error'))

      const { initSession } = useChatStore.getState()
      await initSession()

      expect(useChatStore.getState().error).toBe('创建会话失败')
    })
  })

  describe('sendMessage (streaming)', () => {
    beforeEach(() => {
      useChatStore.setState({ sessionId: 'test-session-123' })
    })

    it('没有 sessionId 时不发送消息', () => {
      useChatStore.setState({ sessionId: null })
      const { sendMessage } = useChatStore.getState()

      sendMessage('测试消息')

      expect(apiService.streamMessage).not.toHaveBeenCalled()
      expect(useChatStore.getState().messages).toHaveLength(0)
    })

    it('应该先添加用户消息和助手占位符到历史', () => {
      const mockReport = {
        report_type: 'success',
        title: '测试报表',
        data_table: { columns: [], rows: [] },
        highlights: [],
        next_queries: [],
      };
      mockStreamSuccess(mockReport);

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      // User message + assistant placeholder (replaced synchronously by onFinalReport)
      expect(messages.length).toBeGreaterThanOrEqual(2)
      expect(messages[0].role).toBe('user')
      expect(messages[0].content).toBe('测试消息')
    })

    it('应该设置 streaming 状态并在完成后清除', () => {
      const mockReport = {
        report_type: 'success',
        title: '测试报表',
        data_table: { columns: [], rows: [] },
        highlights: [],
        next_queries: [],
      };

      // Mock that we can inspect state during streaming
      let isStreamingDuringCall = false;
      (apiService.streamMessage as any).mockImplementation(
        (_sessionId: string, _content: string, handlers: any) => {
          // Capture streaming state before onFinalReport fires
          // (sendMessage sets isStreaming: true synchronously before calling streamMessage)
          isStreamingDuringCall = useChatStore.getState().isStreaming;
          handlers.onFinalReport?.(mockReport);
          handlers.onComplete?.();
          return () => {};
        }
      );

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      // Streaming was active during the call
      expect(isStreamingDuringCall).toBe(true)
      // After final report, streaming should be false
      expect(useChatStore.getState().isStreaming).toBe(false)
    })

    it('成功响应应该添加 Assistant 消息（带 finalReportV2）', () => {
      const mockFinalReport = {
        report_type: 'success',
        title: '测试报表',
        data_table: { columns: [], rows: [] },
        highlights: [],
        next_queries: [],
      };
      mockStreamSuccess(mockFinalReport);

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(2)
      expect(messages[1].role).toBe('assistant')
      expect(messages[1].content).toBe('')
      expect(messages[1].finalReportV2).toEqual(mockFinalReport)
    })

    it('currentSteps 应该在流式过程中更新并在完成后清空', () => {
      let stepsDuringStreaming: any[] = [];
      const mockReport = {
        report_type: 'success',
        title: '测试报表',
        data_table: { columns: [], rows: [] },
        highlights: [],
        next_queries: [],
      };

      (apiService.streamMessage as any).mockImplementation(
        (_sessionId: string, _content: string, handlers: any) => {
          handlers.onStepStart?.('intent_analyzer');
          stepsDuringStreaming = [...useChatStore.getState().currentSteps];
          handlers.onStepComplete?.('intent_analyzer', 'success', 100);
          handlers.onFinalReport?.(mockReport);
          handlers.onComplete?.();
          return () => {};
        }
      );

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      // During streaming, intent_analyzer should be active
      const intentStep = stepsDuringStreaming.find(s => s.id === 'intent_analyzer');
      expect(intentStep?.status).toBe('active');

      // After final report, steps should be cleared
      expect(useChatStore.getState().currentSteps).toEqual([])
    })

    it('需要澄清时应该显示澄清模态框（cot_clarification）', () => {
      mockStreamHitl('cot_clarification');

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      expect(useChatStore.getState().showClarification).toBe(true)
      expect(useChatStore.getState().clarification).toEqual({
        question: '请选择维度',
        options: [
          { value: '渠道', label: '渠道' },
          { value: '创意', label: '创意' },
        ],
        allow_custom_input: false,
      })
      expect(useChatStore.getState().hitlType).toBe('cot_clarification')
      expect(useChatStore.getState().isStreaming).toBe(false)
    })

    it('quality_hitl 时应该显示质量问题列表', () => {
      mockStreamHitl('quality_hitl', {
        quality_issues: [
          { check_type: 'sample_size', severity: 'warning', message: '样本量不足', suggested_action: '放宽筛选条件' }
        ],
        options: [
          { value: 'continue', label: '继续查看结果' },
          { value: 'rephrase', label: '重新表述问题' },
        ],
      });

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      expect(useChatStore.getState().showClarification).toBe(true)
      expect(useChatStore.getState().hitlType).toBe('quality_hitl')
      expect(useChatStore.getState().qualityIssues).toHaveLength(1)
      expect(useChatStore.getState().qualityIssues[0].check_type).toBe('sample_size')
    })

    it('API 失败时应该显示错误消息', () => {
      mockStreamError('连接超时');

      const { sendMessage } = useChatStore.getState()
      sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(2)
      expect(messages[1].content).toContain('抱歉，处理您的请求时出错了')
      expect(messages[1].content).toContain('连接超时')
      expect(useChatStore.getState().isStreaming).toBe(false)
      expect(useChatStore.getState().error).toBe('连接超时')
    })
  })

  describe('submitClarification', () => {
    beforeEach(() => {
      useChatStore.setState({
        sessionId: 'test-session-123',
        showClarification: true,
        hitlType: 'cot_clarification',
        clarification: {
          question: '请选择维度',
          options: [
            { value: '渠道', label: '渠道' },
            { value: '创意', label: '创意' },
          ],
          allow_custom_input: false,
        },
      })
    })

    it('没有 sessionId 时不提交', async () => {
      useChatStore.setState({ sessionId: null })
      const { submitClarification } = useChatStore.getState()

      await submitClarification('渠道')

      expect(apiService.submitClarification).not.toHaveBeenCalled()
    })

    it('应该提交澄清并关闭模态框', async () => {
      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: {
          final_report: {
            report_type: 'success',
            title: '澄清后的报表',
            data_table: { columns: [], rows: [] },
            highlights: [],
            next_queries: [],
          },
        },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      expect(apiService.submitClarification).toHaveBeenCalledWith('test-session-123', '渠道')
      expect(useChatStore.getState().showClarification).toBe(false)
      expect(useChatStore.getState().clarification).toBeNull()
    })

    it('提交前应该添加用户消息', async () => {
      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: {
          final_report: {
            report_type: 'success',
            title: '澄清后的报表',
            data_table: { columns: [], rows: [] },
            highlights: [],
            next_queries: [],
          },
        },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      const messages = useChatStore.getState().messages
      // User message + assistant reply
      expect(messages.length).toBeGreaterThanOrEqual(2)
      expect(messages[0].role).toBe('user')
      expect(messages[0].content).toBe('渠道')
    })

    it('V2 格式报告应该分配到 finalReportV2', async () => {
      const mockFinalReport = {
        report_type: 'success',
        title: '澄清后的报表',
        data_table: { columns: [], rows: [] },
        highlights: [],
        next_queries: [],
      };

      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: { final_report: mockFinalReport },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      const messages = useChatStore.getState().messages
      const assistantMsg = messages[messages.length - 1]
      expect(assistantMsg.role).toBe('assistant')
      expect(assistantMsg.content).toBe('')
      expect(assistantMsg.finalReportV2).toEqual(mockFinalReport)
      expect(assistantMsg.finalReport).toBeUndefined()
    })

    it('V1 格式报告应该分配到 finalReport', async () => {
      const mockFinalReportV1 = {
        title: 'V1 格式报表',
        metrics: [],
        highlights: [],
        data_table: { columns: [], rows: [] },
        next_queries: [],
      };

      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: { final_report: mockFinalReportV1 },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      const messages = useChatStore.getState().messages
      const assistantMsg = messages[messages.length - 1]
      expect(assistantMsg.role).toBe('assistant')
      expect(assistantMsg.finalReport).toEqual(mockFinalReportV1)
      expect(assistantMsg.finalReportV2).toBeUndefined()
    })

    it('没有 final_report 时应该显示 JSON 结果', async () => {
      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: { query_intent: { time_range: '最近7天' } },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      const messages = useChatStore.getState().messages
      const assistantMsg = messages[messages.length - 1]
      expect(assistantMsg.role).toBe('assistant')
      expect(assistantMsg.content).toContain('已确认')
      expect(assistantMsg.content).toContain('最近7天')
    })

    it('提交失败时应该设置中文错误状态', async () => {
      (apiService.submitClarification as any).mockRejectedValueOnce(new Error('API Error'))

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      expect(useChatStore.getState().error).toBe('提交失败，请重试')
      expect(useChatStore.getState().isLoading).toBe(false)
    })

    it('quality_hitl 类型时应该路由到 submitHitl 逻辑', async () => {
      useChatStore.setState({
        sessionId: 'test-session-123',
        showClarification: true,
        hitlType: 'quality_hitl',
        qualityIssues: [
          { check_type: 'sample_size', severity: 'warning', message: '样本量不足', suggested_action: '继续' }
        ],
        clarification: {
          question: '数据质量提示',
          options: [
            { value: 'continue', label: '继续查看结果' },
            { value: 'rephrase', label: '重新表述问题' },
          ],
          allow_custom_input: false,
        },
      });

      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: {
          final_report: {
            report_type: 'success',
            title: '质量确认后的报表',
            data_table: { columns: [], rows: [] },
            highlights: [],
            next_queries: [],
          },
        },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('continue')

      // Should still call submitClarification API
      expect(apiService.submitClarification).toHaveBeenCalledWith('test-session-123', 'continue')

      // User message should show display label for continue
      const messages = useChatStore.getState().messages
      expect(messages[0].role).toBe('user')
      expect(messages[0].content).toBe('继续查看结果')

      // quality issues should be cleared
      expect(useChatStore.getState().qualityIssues).toEqual([])
      expect(useChatStore.getState().hitlType).toBeNull()
    })
  })

  describe('closeClarification', () => {
    it('应该关闭澄清模态框并清空数据', () => {
      useChatStore.setState({
        showClarification: true,
        hitlType: 'cot_clarification',
        clarification: {
          question: '请选择维度',
          options: [
            { value: '渠道', label: '渠道' },
            { value: '创意', label: '创意' },
          ],
          allow_custom_input: false,
        },
      })

      const { closeClarification } = useChatStore.getState()
      closeClarification()

      expect(useChatStore.getState().showClarification).toBe(false)
      expect(useChatStore.getState().clarification).toBeNull()
      expect(useChatStore.getState().hitlType).toBeNull()
      expect(useChatStore.getState().qualityIssues).toEqual([])
    })
  })
})
