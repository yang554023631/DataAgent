import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useChatStore } from '../stores/chatStore'
import ChatMessage from '../components/ChatMessage'
import { apiService } from '../services/api'

// Mock apiService - same pattern as chatStore.test.ts
vi.mock('../services/api', () => ({
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

const mockStreamWithCoTHitl = () => {
  (apiService.streamMessage as any).mockImplementation(
    (_sessionId: string, _content: string, handlers: any) => {
      handlers.onStepStart?.('intent_analyzer');
      handlers.onStepComplete?.('intent_analyzer', 'success', 100);
      handlers.onStepStart?.('analysis_executor');
      handlers.onStepComplete?.('analysis_executor', 'hitl_required', 200);
      handlers.onHitl?.({
        hitl_type: 'cot_clarification',
        question: '请选择分析维度',
        options: [
          { value: '渠道', label: '渠道' },
          { value: '创意', label: '创意' },
        ],
        allow_custom_input: false,
      });
      return () => {};
    }
  );
};

const mockStreamWithQualityHitl = () => {
  (apiService.streamMessage as any).mockImplementation(
    (_sessionId: string, _content: string, handlers: any) => {
      handlers.onStepStart?.('intent_analyzer');
      handlers.onStepComplete?.('intent_analyzer', 'success', 100);
      handlers.onStepStart?.('analysis_executor');
      handlers.onStepComplete?.('analysis_executor', 'hitl_required', 200);
      handlers.onHitl?.({
        hitl_type: 'quality_hitl',
        quality_issues: [
          {
            issue_type: 'incomplete_data',
            message: '数据不完整',
            severity: 'high',
          }
        ],
        question: '是否继续分析？',
        options: [
          { value: 'continue', label: '继续分析' },
          { value: 'rephrase', label: '重新生成' },
        ],
        allow_custom_input: false,
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

describe('Full User Flows Integration Tests', () => {
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
      finalReportV2: null,
      _streamCleanup: undefined,
    })
    vi.clearAllMocks()
  })

  describe('A. Full streaming success flow', () => {
    it('should complete full streaming flow with correct state transitions', async () => {
      const mockReport = {
        report_type: 'analysis',
        content: 'Test analysis report',
        summary: 'Test summary',
        steps: [
          { name: 'intent_analyzer', status: 'success', duration: 100 },
          { name: 'cot_planner', status: 'success', duration: 200 },
          { name: 'filter_executor', status: 'success', duration: 150 },
          { name: 'empty_result_checker', status: 'success', duration: 50 },
          { name: 'analysis_executor', status: 'success', duration: 300 },
          { name: 'quality_checker', status: 'success', duration: 100 },
        ]
      }
      mockStreamSuccess(mockReport)

      // Set up session
      useChatStore.setState({ sessionId: 'test-session-123' })
      const { sendMessage } = useChatStore.getState()
      sendMessage('Test user message')

      // Check apiService.streamMessage was called
      expect(apiService.streamMessage).toHaveBeenCalled()

      // Check messages are added
      expect(useChatStore.getState().messages.length).toBeGreaterThanOrEqual(2)

      // Check final report is received
      await waitFor(() => {
        expect(useChatStore.getState().isStreaming).toBe(false)
        const messages = useChatStore.getState().messages
expect(messages[messages.length - 1].finalReportV2).toEqual(mockReport)
      })

      // Check messages
      const messages = useChatStore.getState().messages
      expect(messages.length).toBe(2) // user + assistant
      expect(messages[0].role).toBe('user')
      expect(messages[1].role).toBe('assistant')
    })
  })

  describe('B. Streaming with CoT clarification HITL flow', () => {
    it('should handle CoT clarification HITL and submit successfully', async () => {
      // First stream triggers HITL
      mockStreamWithCoTHitl()

      // Set up session
      useChatStore.setState({ sessionId: 'test-session-123' })
      const { sendMessage, submitClarification } = useChatStore.getState()
      sendMessage('Test message that needs clarification')

      // Wait for HITL state
      await waitFor(() => {
        expect(useChatStore.getState().showClarification).toBe(true)
        expect(useChatStore.getState().hitlType).toBe('cot_clarification')
      })

      // Mock the post-clarification stream
      const finalReportAfterClarification = {
        report_type: 'analysis',
        content: 'Report after clarification',
        summary: 'Clarified summary',
        steps: []
      }
      mockStreamSuccess(finalReportAfterClarification)

      // Mock submitClarification to return our final report
      apiService.submitClarification.mockResolvedValue({
        result: {
          final_report: finalReportAfterClarification
        }
      });

      // Submit clarification
      await submitClarification('渠道')

      // Check final report is received
      await waitFor(() => {
        expect(useChatStore.getState().isStreaming).toBe(false)
        const messages = useChatStore.getState().messages
expect(messages[messages.length - 1].finalReportV2).toEqual(finalReportAfterClarification)
      })

      // Check messages now include user clarification
      const messages = useChatStore.getState().messages
      expect(messages.length).toBe(4) // user1 -> assistant HITL -> user2 clarification -> assistant final
    })
  })

  describe('C. Streaming with quality HITL flow', () => {
    it('should handle quality HITL - continue flow', async () => {
      // First stream triggers quality HITL
      mockStreamWithQualityHitl()

      // Set up session
      useChatStore.setState({ sessionId: 'test-session-123' })
      const { sendMessage, submitHitl } = useChatStore.getState()
      sendMessage('Test message with quality issues')

      // Wait for HITL state
      await waitFor(() => {
        expect(useChatStore.getState().showClarification).toBe(true)
        expect(useChatStore.getState().hitlType).toBe('quality_hitl')
        expect(useChatStore.getState().qualityIssues.length).toBeGreaterThan(0)
      })

      // Mock the post-HITL stream
      const finalReportAfterContinue = {
        report_type: 'analysis',
        content: 'Report after continuing',
        summary: 'Continued analysis',
        steps: []
      }
      mockStreamSuccess(finalReportAfterContinue)

      // Mock submitClarification to return our final report
      apiService.submitClarification.mockResolvedValue({
        result: {
          final_report: finalReportAfterContinue
        }
      });

      // Click continue button
      await submitHitl('continue')

      // Check final report is received
      await waitFor(() => {
        expect(useChatStore.getState().isStreaming).toBe(false)
        const messages = useChatStore.getState().messages
expect(messages[messages.length - 1].finalReportV2).toEqual(finalReportAfterContinue)
      })
    })

    it('should handle quality HITL - rephrase flow', async () => {
      // First stream triggers quality HITL
      mockStreamWithQualityHitl()

      // Set up session
      useChatStore.setState({ sessionId: 'test-session-123' })
      const { sendMessage, submitHitl } = useChatStore.getState()
      sendMessage('Test message with quality issues')

      // Wait for HITL state
      await waitFor(() => {
        expect(useChatStore.getState().showClarification).toBe(true)
      })

      // Mock the rephrased stream
      const finalReportAfterRephrase = {
        report_type: 'analysis',
        content: 'Rephrased analysis report',
        summary: 'Rephrased summary',
        steps: []
      }
      mockStreamSuccess(finalReportAfterRephrase)

      // Mock submitClarification to return our final report
      apiService.submitClarification.mockResolvedValue({
        result: {
          final_report: finalReportAfterRephrase
        }
      });

      // Click rephrase button
      await submitHitl('rephrase')

      // Check final report is received
      await waitFor(() => {
        expect(useChatStore.getState().isStreaming).toBe(false)
        const messages = useChatStore.getState().messages
expect(messages[messages.length - 1].finalReportV2).toEqual(finalReportAfterRephrase)
      })
    })
  })

  describe('D. Error during streaming', () => {
    it('should handle streaming error gracefully', async () => {
      const errorMessage = 'Stream connection failed'
      mockStreamError(errorMessage)

      // Set up session
      useChatStore.setState({ sessionId: 'test-session-123' })
      const { sendMessage } = useChatStore.getState()
      sendMessage('Test message that will fail')

      // Check error state
      await waitFor(() => {
        expect(useChatStore.getState().isStreaming).toBe(false)
        expect(useChatStore.getState().error).toBe(errorMessage)
      })

      // User should be able to send another message
      let isStreamingDuringSecondCall = false;
      (apiService.streamMessage as any).mockImplementation(
        (_sessionId: string, _content: string, handlers: any) => {
          isStreamingDuringSecondCall = useChatStore.getState().isStreaming;
          handlers.onStepStart?.('intent_analyzer');
          handlers.onError?.(errorMessage);
          handlers.onComplete?.();
          return () => {};
        }
      );

      const { sendMessage: sendSecondMessage } = useChatStore.getState()
      sendSecondMessage('Second test message')

      // Check streaming was active during the call
      expect(isStreamingDuringSecondCall).toBe(true);
    })
  })

  describe('E. Empty result report rendering', () => {
    it('should render empty result report correctly', async () => {
      const emptyReport = {
        report_type: 'empty',
        content: 'No results found',
        summary: 'Empty result summary',
        suggestions: ['Try a different query', 'Use more specific keywords'],
        recommended_queries: ['How to optimize data analysis', 'Best practices for data queries'],
        steps: []
      }
      mockStreamSuccess(emptyReport)

      // Set up session
      useChatStore.setState({ sessionId: 'test-session-123' })
      const { sendMessage } = useChatStore.getState()
      sendMessage('Test empty query')

      // Check final report is received
      await waitFor(() => {
        const messages = useChatStore.getState().messages
expect(messages[messages.length - 1].finalReportV2).toEqual(emptyReport)
      })

      // Check messages
      const messages = useChatStore.getState().messages
      expect(messages.length).toBe(2)

      // Test ChatMessage component with empty report
      render(<ChatMessage message={messages[1]} />)

      // Check empty state content
      await waitFor(() => {
        // Check the empty result emoji and title
        expect(screen.getByText('📭')).toBeInTheDocument()
        expect(screen.getByText('暂无数据')).toBeInTheDocument()
        expect(screen.getByText('未找到符合条件的数据，请尝试调整筛选条件')).toBeInTheDocument()
      })
    })
  })
})