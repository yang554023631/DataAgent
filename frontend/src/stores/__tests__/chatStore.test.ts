import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useChatStore } from '../chatStore'

// Mock apiService
vi.mock('../../services/api', () => ({
  apiService: {
    createSession: vi.fn().mockResolvedValue({ session_id: 'test-session-123' }),
    sendMessage: vi.fn(),
    submitClarification: vi.fn(),
  },
  Message: {} as any,
  Clarification: {} as any,
}))

import { apiService } from '../../services/api'

describe('chatStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useChatStore.setState({
      sessionId: null,
      messages: [],
      isLoading: false,
      showClarification: false,
      clarification: null,
      error: null,
    })
    vi.clearAllMocks()
  })

  describe('初始化状态', () => {
    it('应该有正确的初始状态', () => {
      const state = useChatStore.getState()

      expect(state.sessionId).toBeNull()
      expect(state.messages).toEqual([])
      expect(state.isLoading).toBe(false)
      expect(state.showClarification).toBe(false)
      expect(state.clarification).toBeNull()
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

      expect(useChatStore.getState().error).toBe('Failed to create session')
    })
  })

  describe('sendMessage', () => {
    beforeEach(() => {
      useChatStore.setState({ sessionId: 'test-session-123' })
    })

    it('没有 sessionId 时不发送消息', async () => {
      useChatStore.setState({ sessionId: null })
      const { sendMessage } = useChatStore.getState()

      await sendMessage('测试消息')

      expect(apiService.sendMessage).not.toHaveBeenCalled()
      expect(useChatStore.getState().messages).toHaveLength(0)
    })

    it('应该先添加用户消息到历史', async () => {
      (apiService.sendMessage as any).mockResolvedValueOnce({
        status: 'success',
        result: { final_report: { title: '测试报表' } },
      })

      const { sendMessage } = useChatStore.getState()
      await sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      expect(messages[0].role).toBe('user')
      expect(messages[0].content).toBe('测试消息')
    })

    it('应该设置加载状态', async () => {
      (apiService.sendMessage as any).mockResolvedValueOnce({
        status: 'success',
        result: { final_report: { title: '测试报表' } },
      })

      const { sendMessage } = useChatStore.getState()
      const promise = sendMessage('测试消息')

      expect(useChatStore.getState().isLoading).toBe(true)
      await promise
      expect(useChatStore.getState().isLoading).toBe(false)
    })

    it('成功响应应该添加 Assistant 消息（带 final_report）', async () => {
      const mockFinalReport = {
        title: '测试报表',
        metrics: [],
        highlights: [],
        data_table: { columns: [], rows: [] },
        next_queries: [],
      };

      (apiService.sendMessage as any).mockResolvedValueOnce({
        status: 'success',
        result: { final_report: mockFinalReport },
      })

      const { sendMessage } = useChatStore.getState()
      await sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(2)
      expect(messages[1].role).toBe('assistant')
      expect(messages[1].content).toBe('')
      expect(messages[1].finalReport).toEqual(mockFinalReport)
    })

    it('特定广告主查询应该正确渲染 final_report 而不是显示 JSON', async () => {
      const mockAdvertiserReport = {
        title: '电商家居_40_new 广告报表分析',
        time_range: { start: '2024-01-01', end: '2024-03-31' },
        metrics: [
          { name: '点击量', value: '12,500', trend: 'up' },
          { name: '曝光量', value: '250,000', trend: 'up' },
        ],
        highlights: [{ type: 'positive', text: '点击量环比增长 15%' }],
        data_table: {
          columns: ['月份', '点击量', '曝光量'],
          rows: [['1月', 3500, 70000]],
        },
        next_queries: ['按渠道查看点击量'],
      };

      (apiService.sendMessage as any).mockResolvedValueOnce({
        status: 'completed',
        result: {
          query_intent: { advertiser_id: 2, advertiser_name: '电商家居_40_new' },
          final_report: mockAdvertiserReport,
        },
      })

      const { sendMessage } = useChatStore.getState()
      await sendMessage('电商家居_40_new 最近三个月的点击量 按月细分')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(2)
      expect(messages[1].role).toBe('assistant')
      expect(messages[1].content).toBe('')
      expect(messages[1].finalReport).toBeDefined()
      expect(messages[1].finalReport?.title).toBe('电商家居_40_new 广告报表分析')
      expect(messages[1].finalReport?.metrics).toHaveLength(2)
    })

    it('没有 final_report 时应该显示 JSON 结果', async () => {
      (apiService.sendMessage as any).mockResolvedValueOnce({
        status: 'completed',
        result: { query_intent: { time_range: '最近7天' } },
      })

      const { sendMessage } = useChatStore.getState()
      await sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(2)
      expect(messages[1].role).toBe('assistant')
      expect(messages[1].content).toContain('查询成功')
      expect(messages[1].content).toContain('最近7天')
      expect(messages[1].finalReport).toBeUndefined()
    })

    it('需要澄清时应该显示澄清模态框', async () => {
      (apiService.sendMessage as any).mockResolvedValueOnce({
        status: 'waiting_for_clarification',
        clarification: {
          question: '请选择维度',
          options: [
            { value: '渠道', label: '渠道' },
            { value: '创意', label: '创意' },
          ],
          allow_custom_input: false,
        },
      })

      const { sendMessage } = useChatStore.getState()
      await sendMessage('测试消息')

      expect(useChatStore.getState().showClarification).toBe(true)
      expect(useChatStore.getState().clarification).toEqual({
        question: '请选择维度',
        options: [
          { value: '渠道', label: '渠道' },
          { value: '创意', label: '创意' },
        ],
        allow_custom_input: false,
      })
      expect(useChatStore.getState().isLoading).toBe(false)
    })

    it('API 失败时应该显示错误消息', async () => {
      (apiService.sendMessage as any).mockRejectedValueOnce(new Error('API Error'))

      const { sendMessage } = useChatStore.getState()
      await sendMessage('测试消息')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(2)
      expect(messages[1].content).toBe('抱歉，处理您的请求时出错了。')
      expect(useChatStore.getState().isLoading).toBe(false)
    })
  })

  describe('submitClarification', () => {
    beforeEach(() => {
      useChatStore.setState({
        sessionId: 'test-session-123',
        showClarification: true,
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
            title: '澄清后的报表',
            metrics: [],
            highlights: [],
            data_table: { columns: [], rows: [] },
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

    it('应该添加 Assistant 回复消息（带 final_report）', async () => {
      const mockFinalReport = {
        title: '澄清后的报表',
        metrics: [],
        highlights: [],
        data_table: { columns: [], rows: [] },
        next_queries: [],
      };

      (apiService.submitClarification as any).mockResolvedValueOnce({
        result: { final_report: mockFinalReport },
      })

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      const messages = useChatStore.getState().messages
      expect(messages).toHaveLength(1)
      expect(messages[0].content).toBe('')
      expect(messages[0].finalReport).toEqual(mockFinalReport)
    })

    it('提交失败时应该设置错误状态', async () => {
      (apiService.submitClarification as any).mockRejectedValueOnce(new Error('API Error'))

      const { submitClarification } = useChatStore.getState()
      await submitClarification('渠道')

      expect(useChatStore.getState().error).toBe('Failed to submit clarification')
      expect(useChatStore.getState().isLoading).toBe(false)
    })
  })

  describe('closeClarification', () => {
    it('应该关闭澄清模态框并清空数据', () => {
      useChatStore.setState({
        showClarification: true,
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
    })
  })
})
