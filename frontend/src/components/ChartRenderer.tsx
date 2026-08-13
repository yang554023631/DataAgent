import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { ChartConfigV2 } from '../services/api';

interface ChartSeriesConfig {
  name: string;
  color: string;
}

interface ChartConfig {
  type: 'line' | 'bar' | 'pie' | 'kpi_card';
  series: ChartSeriesConfig[];
  metrics?: string[];
  comparison_data?: {
    period1: { name: string; color: string; data: any[] };
    period2: { name: string; color: string; data: any[] };
  };
  // ChartConfigV2 fields
  title?: string;
  x_axis?: { field: string; label: string };
  y_axis?: { field: string; label: string };
  series_field?: string;
}

interface ChartRendererProps {
  report?: {
    chart_config?: ChartConfig | ChartConfigV2;
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
    reach: '覆盖人数',
    frequency: '频次',
    ctr: '点击率',
    cvr: '转化率',
    roi: 'ROI',
  };
  return mapping[metric] || metric;
};

const ChartRenderer: React.FC<ChartRendererProps> = ({ report, data, groupBy = [], metrics = [] }) => {
  // 对比查询图表渲染
  if (report?.is_comparison && 'comparison_data' in (report.chart_config || {})) {
    const chartConfig = report.chart_config as ChartConfig;
    const { type, comparison_data } = chartConfig;
    if (!comparison_data) return null;
    const { period1, period2 } = comparison_data;

    // 提取维度值和指标值
    const primaryMetric = metrics[0] || 'clicks';
    const categories: string[] = [];
    const series1Data: number[] = [];
    const series2Data: number[] = [];

    // 假设两个周期的数据长度相同且一一对应
    const maxLen = Math.min(period1.data.length, period2.data.length);

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
          left: 60,
          right: 40,
          top: 60,
          bottom: 100,
          containLabel: true,
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: categories,
          axisLabel: {
            rotate: 45,
            interval: 0,
            fontSize: 11,
          },
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            fontSize: 11,
          },
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
        <div className="w-full min-h-[500px] bg-white rounded-lg shadow-sm p-4">
          <ReactECharts option={lineOption} style={{ height: '440px' }} />
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
          left: 60,
          right: 40,
          top: 60,
          bottom: 120,  // 加大底部边距，给长标签留出足够空间
          containLabel: true,
        },
        xAxis: {
          type: 'category',
          data: categories,
          axisLabel: {
            rotate: 45,
            interval: 0,
            fontSize: 11,
          },
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
        <div className="w-full min-h-[500px] bg-white rounded-lg shadow-sm p-4">
          <ReactECharts option={barOption} style={{ height: '440px' }} />
        </div>
      );
    }
  }

  // 使用后端传的 chart_config 来确定图表类型和指标
  const chartType = report?.chart_config?.type || 'bar';

  // KPI Card (summary)
  if (chartType === 'kpi_card' && data && data.length > 0) {
    // Auto-detect metric name and value fields
    const nameField = Object.keys(data[0]).find(k =>
      k.includes('name') || k.includes('metric') || k.includes('label')
    ) || 'name';
    const valueField = Object.keys(data[0]).find(k =>
      k.includes('value') || k.includes('formatted') || ['cost', 'click', 'impression', 'ctr', 'cvr'].includes(k)
    ) || 'value';
    const formattedField = Object.keys(data[0]).find(k =>
      k.includes('formatted') || k.includes('display')
    );

    return (
      <div className="w-full bg-white rounded-lg shadow-sm p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          {report?.chart_config?.title || '核心指标'}
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {data.map((item, idx) => {
            const name = String(item[nameField] || `指标${idx + 1}`);
            const value = formattedField && item[formattedField]
              ? String(item[formattedField])
              : (typeof item[valueField] === 'number'
                ? item[valueField].toLocaleString()
                : String(item[valueField] || '-'));
            const color = report?.chart_config?.series?.[idx]?.color;
            return (
              <div
                key={idx}
                className="bg-gray-50 rounded-lg p-4 border border-gray-100"
              >
                <div className="text-sm text-gray-500 mb-1">{name}</div>
                <div
                  className="text-2xl font-bold"
                  style={{ color: color || '#1f2937' }}
                >
                  {value}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Pie chart
  if (chartType === 'pie' && data && data.length > 0) {
    const seriesField = report?.chart_config?.series_field || 'name';
    const valueField = report?.chart_config?.y_axis?.field || metrics[0] || 'value';
    const seriesConfig = report?.chart_config?.series || [];

    const pieData = data.map((item, index) => {
      // 优先使用 chart_config.series 中的 name（受众分布已经后端映射好了中文）
      // 如果没有，再从 data 中拿，最后 fallback 到 项N
      let name: string;
      if (seriesConfig[index]?.name) {
        name = seriesConfig[index].name;
      } else {
        name = String(item[seriesField] || item.name || item.label || `项${index + 1}`);
      }
      return {
        value: Number(item[valueField]) || 0,
        name,
        itemStyle: seriesConfig[index]?.color ? { color: seriesConfig[index].color } : undefined,
      };
    });

    const pieOption: EChartsOption = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        right: '5%',
        top: 'center',
        textStyle: { fontSize: 12 },
      },
      series: [
        {
          name: getMetricDisplayName(valueField),
          type: 'pie',
          radius: ['40%', '70%'], // Ring chart
          center: ['35%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: {
            show: false,
            position: 'center',
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
            },
          },
          labelLine: {
            show: false,
          },
          data: pieData,
        },
      ],
    };

    return (
      <div className="w-full min-h-[400px] bg-white rounded-lg shadow-sm p-4">
        <ReactECharts option={pieOption} style={{ height: '340px' }} />
      </div>
    );
  }

  // 普通查询图表渲染（至少2条数据才渲染图表）
  if (data && data.length > 1) {
    // Get x and y field from chart_config if provided
    const xField = report?.chart_config?.x_axis?.field;
    const yField = report?.chart_config?.y_axis?.field;
    const primaryMetric = ('metrics' in (report?.chart_config || {})
      ? (report?.chart_config as ChartConfig)?.metrics?.[0]
      : undefined) || (yField ? undefined : metrics?.[0]) || 'clicks';
    const categories: string[] = [];
    const values: number[] = [];

    // 确定哪些列是维度列（排除指标列和 name）
    const metricColumns = ['impressions', 'clicks', 'cost', 'conversions', 'reach', 'frequency', 'ctr', 'cvr', 'roi'];
    let dimensionColumns = Object.keys(data[0] || {})
      .filter(col => !metricColumns.includes(col) && col !== 'name');

    // If x_field is specified, use it directly as the only dimension
    if (xField) {
      dimensionColumns = [xField];
    }

    data.forEach((item) => {
      // 如果有多维度列，使用 name 列的组合值作为分类（因为 name 包含所有维度的组合）
      // 如果只有单个维度列，直接使用该维度值
      // 如果有 series_field，每个点就是一个分类，将 x_field + series_field 组合起来更清晰
      let category: string;
      if (report?.chart_config?.series_field && dimensionColumns.length === 1) {
        // When we have a series field (like 'period'), combine it with x field for better readability
        const xVal = String(item[xField]) || '';
        const seriesVal = String(item[report.chart_config.series_field]) || '';

        // Translate period names to more readable Chinese
        const friendlyNames: Record<string, string> = {
          'current_period': '当前期',
          'compare_period': '对比期',
          'current': '当前期',
          'compare': '对比期',
          '4月': '4月',
          '3月': '3月',
          '2026-04': '4月',
          '2026-03': '3月',
        };
        const friendlySeries = friendlyNames[seriesVal] || seriesVal;
        // Format: "cost (4月)"
        category = `${xVal} (${friendlySeries})`;
      } else if (dimensionColumns.length > 1 && item.name) {
        category = String(item.name);
      } else if (dimensionColumns.length === 1) {
        category = String(item[dimensionColumns[0]]) || item.name || '-';
      } else {
        const firstKey = Object.keys(item)[0];
        category = item[firstKey] || item.name || '-';
      }
      categories.push(category);
      // Use y_field from chart_config if provided, otherwise fall back to primaryMetric
      const valueKey = yField || primaryMetric;
      values.push(Number(item[valueKey]) || 0);
    });

    // 根据图表类型渲染
    const isTimeDimension = chartType === 'line';

    if (isTimeDimension) {
      // Check if multi-series (has series_field or multiple series in config)
      const seriesField = report?.chart_config?.series_field;
      const hasMultipleSeries = seriesField && report?.chart_config?.series && report.chart_config.series.length > 1;

      if (hasMultipleSeries && seriesField) {
        // Multi-series line chart
        const xField = report?.chart_config?.x_axis?.field || dimensionColumns[0] || 'date';
        const yField = report?.chart_config?.y_axis?.field || primaryMetric;

        // Pivot data: group by x value, then by series name
        const xValues: string[] = [];
        const seriesNames: string[] = [];
        const dataMap: Record<string, Record<string, number>> = {}; // xValue -> seriesName -> value

        data.forEach((item) => {
          const xVal = String(item[xField] || '');
          const sName = String(item[seriesField] || '');

          if (!xValues.includes(xVal)) xValues.push(xVal);
          if (!seriesNames.includes(sName)) seriesNames.push(sName);

          if (!dataMap[xVal]) dataMap[xVal] = {};
          dataMap[xVal][sName] = Number(item[yField]) || 0;
        });

        const defaultColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];
        const seriesConfig = report?.chart_config?.series || [];

        // Build name-to-color map from chart_config.series for correct matching
        // regardless of series order in data vs config
        const seriesColorMap: Record<string, string> = {};
        seriesConfig.forEach((s) => {
          if (s.name && s.color) {
            seriesColorMap[s.name] = s.color;
          }
        });

        const multiLineOption: EChartsOption = {
          tooltip: {
            trigger: 'axis',
          },
          legend: {
            data: seriesNames,
            type: 'scroll',
            bottom: 0,
            textStyle: { fontSize: 11 },
          },
          grid: {
            left: 60,
            right: 40,
            top: 30,
            bottom: 80,
            containLabel: true,
          },
          xAxis: {
            type: 'category',
            boundaryGap: false,
            data: xValues,
            axisLabel: {
              rotate: 45,
              interval: 0,
              fontSize: 11,
            },
          },
          yAxis: {
            type: 'value',
            axisLabel: { fontSize: 11 },
          },
          series: seriesNames.map((sName, idx) => {
            const color = seriesColorMap[sName] || defaultColors[idx % defaultColors.length];
            return {
              name: sName,
              type: 'line',
              smooth: true,
              data: xValues.map(xVal => dataMap[xVal]?.[sName] ?? null),
              lineStyle: {
                color,
                width: 2,
              },
              itemStyle: {
                color,
              },
            };
          }),
        };

        return (
          <div className="w-full min-h-[500px] bg-white rounded-lg shadow-sm p-4">
            <ReactECharts option={multiLineOption} style={{ height: '440px' }} />
          </div>
        );
      } else {
        // 时间趋势用折线图 - 单系列
        const lineOption: EChartsOption = {
          tooltip: {
            trigger: 'axis',
          },
          grid: {
            left: 60,
            right: 40,
            top: 30,  // 去掉标题后top可以更小，腾出更多空间给图表
            bottom: 100,
            containLabel: true,
          },
          xAxis: {
            type: 'category',
            boundaryGap: false,
            data: categories,
            axisLabel: {
              rotate: 45,
              interval: 0,
              fontSize: 11,
            },
          },
          yAxis: {
            type: 'value',
            axisLabel: {
              fontSize: 11,
            },
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
          <div className="w-full min-h-[500px] bg-white rounded-lg shadow-sm p-4">
            <ReactECharts option={lineOption} style={{ height: '440px' }} />
          </div>
        );
      }
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
        left: 60,
        right: 40,
        top: 30,  // 去掉标题后top可以更小，腾出更多空间给图表
        bottom: 120,  // 加大底部边距，给长标签留出足够空间
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: {
          rotate: 45,  // 加大旋转角度，避免重叠
          interval: 0,
          fontSize: 11,
        },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          fontSize: 11,
        },
      },
      series: [
        {
          name: getMetricDisplayName(primaryMetric),
          type: 'bar',
          data: values,
          barWidth: '50%',  // 控制条形宽度，避免太胖
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
      <div className="w-full min-h-[500px] bg-white rounded-lg shadow-sm p-4">
        <ReactECharts option={barOption} style={{ height: '440px' }} />
      </div>
    );
  }

  // 没有数据时不渲染
  return null;
};

export default ChartRenderer;
