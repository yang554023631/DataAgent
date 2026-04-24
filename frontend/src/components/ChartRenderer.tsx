import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface ChartSeriesConfig {
  name: string;
  color: string;
}

interface ChartConfig {
  type: 'line' | 'bar' | 'pie';
  series: ChartSeriesConfig[];
  metrics?: string[];
  comparison_data?: {
    period1: { name: string; color: string; data: any[] };
    period2: { name: string; color: string; data: any[] };
  };
}

interface ChartRendererProps {
  report?: {
    chart_config?: ChartConfig;
    is_comparison?: boolean;
  };
  data?: any[];
  groupBy?: string[];
  metrics?: string[];
}

const getMetricDisplayName = (metric: string): string => {
  const mapping: Record<string, string> = {
    impressions: '曝光量',
    clicks: '点击量',
    cost: '花费',
    conversions: '转化数',
    ctr: '点击率',
    cvr: '转化率',
    roi: 'ROI',
  };
  return mapping[metric] || metric;
};

const ChartRenderer: React.FC<ChartRendererProps> = ({ report, data, groupBy = [], metrics = [] }) => {
  // 对比查询图表渲染
  if (report?.is_comparison && report.chart_config?.comparison_data) {
    const { type, comparison_data } = report.chart_config;
    const { period1, period2 } = comparison_data;

    // 提取维度值和指标值
    const primaryMetric = metrics[0] || 'clicks';
    const categories: string[] = [];
    const series1Data: number[] = [];
    const series2Data: number[] = [];

    // 假设两个周期的数据长度相同且一一对应
    const maxLen = Math.min(period1.data.length, period2.data.length, 15); // 最多显示15个点

    for (let i = 0; i < maxLen; i++) {
      const item1 = period1.data[i];
      const item2 = period2.data[i];

      if (item1 && item2) {
        const category = item1.name || item1[groupBy?.[0] || 'name'] || `第${i + 1}项`;
        categories.push(String(category));
        series1Data.push(Number(item1[primaryMetric]) || 0);
        series2Data.push(Number(item2[primaryMetric]) || 0);
      }
    }

    // 双折线图（时间趋势对比）
    if (type === 'line') {
      const lineOption: EChartsOption = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross',
          },
        },
        legend: {
          data: [period1.name, period2.name],
        },
        grid: {
          left: '3%',
          right: '4%',
          top: '10%',
          bottom: '15%',
          containLabel: true,
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: categories,
        },
        yAxis: {
          type: 'value',
        },
        series: [
          {
            name: period1.name,
            type: 'line',
            smooth: true,
            data: series1Data,
            lineStyle: { color: period1.color, width: 2 },
            itemStyle: { color: period1.color },
          },
          {
            name: period2.name,
            type: 'line',
            smooth: true,
            data: series2Data,
            lineStyle: { color: period2.color, width: 2 },
            itemStyle: { color: period2.color },
          },
        ],
      };

      return (
        <div className="w-full h-[520px] bg-white rounded-lg shadow-sm p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            {period1.name} vs {period2.name} 趋势对比
          </h3>
          <ReactECharts option={lineOption} style={{ height: '420px' }} />
        </div>
      );
    }

    // 分组柱状图（分类维度对比）
    if (type === 'bar') {
      const barOption: EChartsOption = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow',
          },
        },
        legend: {
          data: [period1.name, period2.name],
        },
        grid: {
          left: '3%',
          right: '4%',
          top: '10%',
          bottom: '15%',
          containLabel: true,
        },
        xAxis: {
          type: 'category',
          data: categories,
        },
        yAxis: {
          type: 'value',
        },
        series: [
          {
            name: period1.name,
            type: 'bar',
            data: series1Data,
            itemStyle: { color: period1.color },
          },
          {
            name: period2.name,
            type: 'bar',
            data: series2Data,
            itemStyle: { color: period2.color },
          },
        ],
      };

      return (
        <div className="w-full h-[520px] bg-white rounded-lg shadow-sm p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            {period1.name} vs {period2.name} 对比
          </h3>
          <ReactECharts option={barOption} style={{ height: '420px' }} />
        </div>
      );
    }
  }

  // 普通查询图表渲染
  if (data && data.length > 1) {  // 至少2条数据才渲染图表
    // 使用后端传的 chart_config 来确定图表类型和指标
    const chartType = report?.chart_config?.type || 'bar';
    const primaryMetric = report?.chart_config?.metrics?.[0] || 'clicks';
    const categories: string[] = [];
    const values: number[] = [];

    data.slice(0, 15).forEach((item) => {
      // 第一列作为分类（维度值）
      const firstKey = Object.keys(item)[0];
      const category = item[firstKey] || item.name || '-';
      categories.push(String(category));
      values.push(Number(item[primaryMetric]) || 0);
    });

    // 根据图表类型渲染
    const isTimeDimension = chartType === 'line';

    if (isTimeDimension) {
      // 时间趋势用折线图
      const lineOption: EChartsOption = {
        tooltip: {
          trigger: 'axis',
        },
        grid: {
          left: '3%',
          right: '4%',
          top: '10%',
          bottom: '15%',
          containLabel: true,
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: categories,
        },
        yAxis: {
          type: 'value',
        },
        series: [
          {
            name: getMetricDisplayName(primaryMetric),
            type: 'line',
            smooth: true,
            data: values,
            lineStyle: { color: '#3b82f6', width: 2 },
            itemStyle: { color: '#3b82f6' },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                  { offset: 1, color: 'rgba(59, 130, 246, 0.05)' },
                ],
              },
            },
          },
        ],
      };

      return (
        <div className="w-full h-[520px] bg-white rounded-lg shadow-sm p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            {getMetricDisplayName(primaryMetric)} 趋势
          </h3>
          <ReactECharts option={lineOption} style={{ height: '220px' }} />
        </div>
      );
    }

    // 分类维度用柱状图
    const barOption: EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow',
        },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: {
          rotate: categories.length > 5 ? 30 : 0,
          interval: 0,
        },
      },
      yAxis: {
        type: 'value',
      },
      series: [
        {
          name: getMetricDisplayName(primaryMetric),
          type: 'bar',
          data: values,
          itemStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: '#60a5fa' },
                { offset: 1, color: '#3b82f6' },
              ],
            },
            borderRadius: [4, 4, 0, 0],
          },
        },
      ],
    };

    return (
      <div className="w-full h-[520px] bg-white rounded-lg shadow-sm p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          {getMetricDisplayName(primaryMetric)} 分布
        </h3>
        <ReactECharts option={barOption} style={{ height: '220px' }} />
      </div>
    );
  }

  // 没有数据时不渲染
  return null;
};

export default ChartRenderer;
