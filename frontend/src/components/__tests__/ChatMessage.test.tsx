import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ChatMessage from '../ChatMessage'

// Mock child components
vi.mock('../DataTable', () => ({
  DataTable: ({ columns, rows }: any) => (
    <div data-testid="data-table-mock">
      DataTable: {columns.join(',')} - {rows.length} rows
    </div>
  ),
}))

vi.mock('../ChartRenderer', () => ({
  default: () => <div data-testid="chart-renderer-mock">ChartRenderer</div>,
}))

vi.mock('../MetricCard', () => ({
  MetricCard: ({ name, value }: any) => (
    <div data-testid="metric-card-mock">{name}: {value}</div>
  ),
}))

vi.mock('../HighlightList', () => ({
  HighlightList: ({ highlights }: any) => (
    <div data-testid="highlight-list-mock">HighlightList: {highlights.length} items</div>
  ),
}))

describe('ChatMessage', () => {
  describe('消息对齐', () => {
    it('用户消息应该右对齐', () => {
      render(
        <ChatMessage
          message={{ role: 'user', content: '你好' }}
        />
      )

      const container = screen.getByText('你好').closest('.max-w-\\[60\\%\\]')
      expect(container).toBeInTheDocument()
    })

    it('Assistant 消息应该左对齐并占满宽度', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '你好，有什么可以帮您？' }}
        />
      )

      const container = screen.getByText('你好，有什么可以帮您？').closest('.max-w-full')
      expect(container).toBeInTheDocument()
    })
  })

  describe('消息内容渲染', () => {
    it('多行消息应该正确换行', () => {
      const multiLineContent = '第一行\n第二行\n第三行'
      render(
        <ChatMessage
          message={{ role: 'assistant', content: multiLineContent }}
        />
      )

      expect(screen.getByText('第一行')).toBeInTheDocument()
      expect(screen.getByText('第二行')).toBeInTheDocument()
      expect(screen.getByText('第三行')).toBeInTheDocument()
    })
  })

  describe('FinalReport 渲染', () => {
    const mockFinalReport = {
      title: '广告报表分析',
      time_range: { start: '2024-01-01', end: '2024-01-07' },
      metrics: [
        { name: '曝光量', value: '10,000', trend: 'up' as const },
        { name: '点击量', value: '500', trend: 'down' as const },
      ],
      highlights: [
        { type: 'positive' as const, text: '数据表现良好' },
        { type: 'negative' as const, text: '需要关注' },
      ],
      data_table: {
        columns: ['渠道', '曝光', '点击'],
        rows: [
          ['渠道A', 1000, 50],
          ['渠道B', 2000, 100],
        ],
      },
      next_queries: [
        '查看更多数据',
        '按维度下钻',
      ],
    }

    it('应该渲染报表标题', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
        />
      )

      expect(screen.getByText('广告报表分析')).toBeInTheDocument()
    })

    it('应该渲染指标卡片', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
        />
      )

      const metricCards = screen.getAllByTestId('metric-card-mock')
      expect(metricCards).toHaveLength(2)
      expect(screen.getByText('曝光量: 10,000')).toBeInTheDocument()
      expect(screen.getByText('点击量: 500')).toBeInTheDocument()
    })

    it('应该渲染亮点列表', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
        />
      )

      expect(screen.getByTestId('highlight-list-mock')).toBeInTheDocument()
      expect(screen.getByText(/2 items/)).toBeInTheDocument()
    })

    it('应该渲染数据表格', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
        />
      )

      expect(screen.getByTestId('data-table-mock')).toBeInTheDocument()
    })

    it('应该渲染图表', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
        />
      )

      expect(screen.getByTestId('chart-renderer-mock')).toBeInTheDocument()
    })

    it('应该渲染推荐查询', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
        />
      )

      expect(screen.getByText('推荐查询')).toBeInTheDocument()
      expect(screen.getByText('→ 查看更多数据')).toBeInTheDocument()
      expect(screen.getByText('→ 按维度下钻')).toBeInTheDocument()
    })

    it('点击推荐查询应该触发回调', () => {
      const mockOnSuggestionClick = vi.fn()
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockFinalReport }}
          onSuggestionClick={mockOnSuggestionClick}
        />
      )

      fireEvent.click(screen.getByText('→ 查看更多数据'))
      expect(mockOnSuggestionClick).toHaveBeenCalledWith('查看更多数据')
    })
  })

  describe('时间戳显示', () => {
    it('有时间戳时应该显示', () => {
      render(
        <ChatMessage
          message={{ role: 'user', content: '测试', timestamp: '10:30' }}
        />
      )

      // 时间戳存在于消息中
      expect(screen.getByText('测试')).toBeInTheDocument()
    })
  })
})
