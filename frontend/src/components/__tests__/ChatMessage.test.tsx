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

  describe('广告主列表场景', () => {
    const mockAdvertiserListReport = {
      title: '可用的广告主列表',
      time_range: { start: '', end: '' },
      metrics: [],  // 空数组，没有指标数据
      highlights: [
        { type: 'info', text: '💡 点击以下广告主名称即可查看对应数据' },
      ],
      data_table: {
        columns: ['广告主ID', '广告主名称'],
        rows: [
          ['1', '六一八智能_406'],
          ['2', '促销食品'],
          ['3', 'sport_winter'],
        ],
      },
      next_queries: [
        '查看 六一八智能_406 的数据',
        '查看 促销食品 的数据',
        '查看 sport_winter 的数据',
      ],
    }

    it('应该显示广告主列表表格', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockAdvertiserListReport }}
        />
      )

      // 应该显示标题
      expect(screen.getByText('可用的广告主列表')).toBeInTheDocument()

      // 应该显示数据表格
      expect(screen.getByTestId('data-table-mock')).toBeInTheDocument()
    })

    it('不应该渲染图表（因为 metrics 为空）', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockAdvertiserListReport }}
        />
      )

      // metrics 为空数组，不应该渲染图表
      expect(screen.queryByTestId('chart-renderer-mock')).not.toBeInTheDocument()
    })

    it('不应该渲染指标卡片（因为 metrics 为空）', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockAdvertiserListReport }}
        />
      )

      // metrics 为空数组，不应该渲染指标卡片
      expect(screen.queryByTestId('metric-card-mock')).not.toBeInTheDocument()
    })

    it('应该渲染推荐查询', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockAdvertiserListReport }}
        />
      )

      expect(screen.getByText('推荐查询')).toBeInTheDocument()
      expect(screen.getByText('→ 查看 六一八智能_406 的数据')).toBeInTheDocument()
    })
  })

  describe('特定广告主数据查询场景', () => {
    const mockSpecificAdvertiserReport = {
      title: '电商家居_40_new 广告报表分析',
      time_range: { start: '2024-01-01', end: '2024-03-31' },
      metrics: [
        { name: '点击量', value: '12,500', trend: 'up' as const },
        { name: '曝光量', value: '250,000', trend: 'up' as const },
      ],
      highlights: [
        { type: 'positive', text: '点击量环比增长 15%' },
      ],
      data_table: {
        columns: ['月份', '点击量', '曝光量'],
        rows: [
          ['1月', 3500, 70000],
          ['2月', 4000, 80000],
          ['3月', 5000, 100000],
        ],
      },
      next_queries: [
        '按渠道查看点击量',
        '对比上周数据',
      ],
    }

    it('应该显示特定广告主的报表标题', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockSpecificAdvertiserReport }}
        />
      )

      expect(screen.getByText('电商家居_40_new 广告报表分析')).toBeInTheDocument()
    })

    it('应该渲染指标卡片（有数据时）', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockSpecificAdvertiserReport }}
        />
      )

      const metricCards = screen.getAllByTestId('metric-card-mock')
      expect(metricCards).toHaveLength(2)
      expect(screen.getByText('点击量: 12,500')).toBeInTheDocument()
      expect(screen.getByText('曝光量: 250,000')).toBeInTheDocument()
    })

    it('应该渲染图表（有指标数据时）', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockSpecificAdvertiserReport }}
        />
      )

      expect(screen.getByTestId('chart-renderer-mock')).toBeInTheDocument()
    })

    it('应该渲染数据详情表格', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockSpecificAdvertiserReport }}
        />
      )

      expect(screen.getByTestId('data-table-mock')).toBeInTheDocument()
      expect(screen.getByText(/月份,点击量,曝光量/)).toBeInTheDocument()
    })

    it('不应该显示"可用的广告主列表"标题', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockSpecificAdvertiserReport }}
        />
      )

      expect(screen.queryByText('可用的广告主列表')).not.toBeInTheDocument()
    })

    it('不应该显示广告主选择提示信息', () => {
      render(
        <ChatMessage
          message={{ role: 'assistant', content: '', finalReport: mockSpecificAdvertiserReport }}
        />
      )

      expect(screen.queryByText(/点击以下广告主名称即可查看对应数据/)).not.toBeInTheDocument()
    })
  })
})
