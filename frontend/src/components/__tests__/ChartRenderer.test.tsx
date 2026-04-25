import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChartRenderer from '../ChartRenderer'

// Mock echarts-for-react
vi.mock('echarts-for-react', () => ({
  default: ({ option, style }: any) => (
    <div data-testid="echarts-mock" data-option={JSON.stringify(option)} style={style}>
      ECharts Mock
    </div>
  ),
}))

describe('ChartRenderer', () => {
  describe('基础渲染', () => {
    it('空数据时不渲染图表', () => {
      const { container } = render(
        <ChartRenderer data={[]} metrics={['clicks']} />
      )
      expect(container.firstChild).toBeNull()
    })

    it('只有一条数据时不渲染图表', () => {
      const { container } = render(
        <ChartRenderer
          data={[{ name: '渠道A', clicks: 1000 }]}
          metrics={['clicks']}
        />
      )
      expect(container.firstChild).toBeNull()
    })
  })

  describe('普通查询图表', () => {
    const mockData = [
      { name: '渠道A', clicks: 1000 },
      { name: '渠道B', clicks: 2000 },
      { name: '渠道C', clicks: 1500 },
    ]

    it('分类维度应该渲染柱状图', () => {
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'bar', series: [] } }}
          data={mockData}
          metrics={['clicks']}
        />
      )

      const chart = screen.getByTestId('echarts-mock')
      expect(chart).toBeInTheDocument()

      const option = JSON.parse(chart.dataset.option || '{}')
      expect(option.xAxis).toBeDefined()
      expect(option.yAxis).toBeDefined()
    })

    it('时间维度应该渲染折线图', () => {
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'line', series: [] } }}
          data={mockData}
          metrics={['clicks']}
        />
      )

      const chart = screen.getByTestId('echarts-mock')
      expect(chart).toBeInTheDocument()

      const option = JSON.parse(chart.dataset.option || '{}')
      expect(option.xAxis.boundaryGap).toBe(false)
    })

    it('图表应该包含正确的指标中文名称', () => {
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'bar', series: [] } }}
          data={mockData}
          metrics={['clicks']}
        />
      )

      expect(screen.getByText('点击量 分布')).toBeInTheDocument()
    })

    it('图表容器应该有正确的高度', () => {
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'bar', series: [] } }}
          data={mockData}
          metrics={['clicks']}
        />
      )

      const container = screen.getByTestId('echarts-mock').parentElement
      expect(container).toHaveClass('min-h-[500px]')
    })
  })

  describe('对比查询图表', () => {
    const mockComparisonData = {
      period1: { name: '第一周', color: '#10b981', data: [{ name: '渠道A', clicks: 1000 }] },
      period2: { name: '第二周', color: '#3b82f6', data: [{ name: '渠道A', clicks: 1200 }] },
    }

    it('对比柱状图应该正确渲染', () => {
      render(
        <ChartRenderer
          report={{
            is_comparison: true,
            chart_config: {
              type: 'bar',
              series: [],
              comparison_data: mockComparisonData,
            },
          }}
          metrics={['clicks']}
        />
      )

      const chart = screen.getByTestId('echarts-mock')
      expect(chart).toBeInTheDocument()

      const option = JSON.parse(chart.dataset.option || '{}')
      expect(option.legend.data).toContain('第一周')
      expect(option.legend.data).toContain('第二周')
    })

    it('对比折线图应该正确渲染', () => {
      const timeComparisonData = {
        period1: { name: '第一周', color: '#10b981', data: Array.from({ length: 5 }, (_, i) => ({ name: `Day${i + 1}`, clicks: 1000 + i * 100 })) },
        period2: { name: '第二周', color: '#3b82f6', data: Array.from({ length: 5 }, (_, i) => ({ name: `Day${i + 1}`, clicks: 1200 + i * 100 })) },
      }

      render(
        <ChartRenderer
          report={{
            is_comparison: true,
            chart_config: {
              type: 'line',
              series: [],
              comparison_data: timeComparisonData,
            },
          }}
          metrics={['clicks']}
        />
      )

      const chart = screen.getByTestId('echarts-mock')
      expect(chart).toBeInTheDocument()

      const option = JSON.parse(chart.dataset.option || '{}')
      expect(option.series).toHaveLength(2)
      expect(option.series[0].type).toBe('line')
      expect(option.series[1].type).toBe('line')
    })

    it('对比图表应该显示正确的标题', () => {
      render(
        <ChartRenderer
          report={{
            is_comparison: true,
            chart_config: {
              type: 'bar',
              series: [],
              comparison_data: mockComparisonData,
            },
          }}
          metrics={['clicks']}
        />
      )

      expect(screen.getByText('第一周 vs 第二周 对比')).toBeInTheDocument()
    })
  })

  describe('指标中文名称映射', () => {
    it('impressions 应该显示为 "曝光量"', () => {
      const impressionsData = [
        { name: '渠道A', impressions: 10000 },
        { name: '渠道B', impressions: 20000 },
      ]
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'bar', metrics: ['impressions'], series: [] } }}
          data={impressionsData}
          metrics={['impressions']}
        />
      )
      expect(screen.getByText('曝光量 分布')).toBeInTheDocument()
    })

    it('ctr 应该显示为 "点击率"', () => {
      const ctrData = [
        { name: '渠道A', ctr: 0.05 },
        { name: '渠道B', ctr: 0.08 },
      ]
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'bar', metrics: ['ctr'], series: [] } }}
          data={ctrData}
          metrics={['ctr']}
        />
      )
      expect(screen.getByText('点击率 分布')).toBeInTheDocument()
    })

    it('cost 应该显示为 "花费"', () => {
      const costData = [
        { name: '渠道A', cost: 5000 },
        { name: '渠道B', cost: 8000 },
      ]
      render(
        <ChartRenderer
          report={{ chart_config: { type: 'bar', metrics: ['cost'], series: [] } }}
          data={costData}
          metrics={['cost']}
        />
      )
      expect(screen.getByText('花费 分布')).toBeInTheDocument()
    })
  })
})
