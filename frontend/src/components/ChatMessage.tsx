import { MetricCard } from './MetricCard';
import { HighlightList } from './HighlightList';
import { DataTable } from './DataTable';
import ChartRenderer from './ChartRenderer';
import { QualityIssueList } from './QualityIssueList';
import { FinalReport, FinalReportV2 } from '../services/api';

interface ChatMessageProps {
  message: {
    role: 'user' | 'assistant';
    content: string;
    timestamp?: string;
    finalReport?: FinalReport;
    finalReportV2?: FinalReportV2;
  };
  onSuggestionClick?: (query: string) => void;
}

export default function ChatMessage({ message, onSuggestionClick }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex w-full mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`w-full rounded-lg px-4 py-3 ${
        isUser
          ? 'bg-blue-600 text-white max-w-[60%]'
          : 'bg-gray-100 text-gray-800 max-w-full'
      }`}>
        {message.content.split('\n').map((line, i) => (
          <p key={i} className="whitespace-pre-wrap">{line}</p>
        ))}

        {message.finalReport && (
          <div className="mt-4 space-y-4">
            <h3 className="text-lg font-semibold">{message.finalReport.title}</h3>

            {message.finalReport.metrics.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {message.finalReport.metrics.map((metric, idx) => (
                  <MetricCard
                    key={idx}
                    {...metric}
                    trend={metric.trend as ('up' | 'down' | 'flat' | undefined)}
                  />
                ))}
              </div>
            )}

            {/* 图表渲染 - 只有在有指标数据时才显示 */}
            {message.finalReport?.metrics?.length > 0 && (
              <ChartRenderer
                report={message.finalReport as any}
                data={message.finalReport.data_table?.rows?.map((row: any[]) => {
                  const obj: Record<string, any> = {};
                  message.finalReport?.data_table.columns?.forEach((col: string, i: number) => {
                    obj[col] = row[i];
                  });
                  // 多维度时，name 是所有维度列的组合值（用于图表X轴显示）
                  const dimensionColumns = Object.keys(obj).filter(col =>
                    !['impressions', 'clicks', 'cost', 'conversions', 'reach', 'frequency', 'ctr', 'cvr', 'roi'].includes(col)
                  );
                  if (dimensionColumns.length > 0) {
                    obj.name = dimensionColumns.map(col => obj[col]).join(' / ');
                  }
                  return obj;
                }) || []}
                groupBy={[]}
                metrics={message.finalReport.metrics?.map((m: any) => m.name) || []}
              />
            )}

            {message.finalReport.highlights?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">关键提示</h4>
                <HighlightList highlights={message.finalReport.highlights} />
              </div>
            )}

            {message.finalReport.data_table?.columns?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">数据详情</h4>
                <DataTable {...message.finalReport.data_table} />
              </div>
            )}

            {message.finalReport.next_queries?.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-sm font-medium mb-2">推荐查询</h4>
                <ul className="space-y-1">
                  {message.finalReport.next_queries.map((query, idx) => (
                    <li
                      key={idx}
                      className="text-sm text-blue-600 cursor-pointer hover:underline"
                      onClick={() => onSuggestionClick?.(query)}
                    >
                      → {query}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* V2 Report Format (CoT analysis) */}
        {message.finalReportV2 && (
          <div className="mt-4 space-y-4">
            {/* Title */}
            <h3 className="text-lg font-semibold">{message.finalReportV2.title}</h3>

            {/* Error report */}
            {message.finalReportV2.report_type === 'error' && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="text-red-800 font-medium mb-2">
                  {message.finalReportV2.message}
                </div>
                {message.finalReportV2.reason && (
                  <div className="text-red-600 text-sm mb-3">
                    原因：{message.finalReportV2.reason}
                  </div>
                )}
                {message.finalReportV2.suggestions && message.finalReportV2.suggestions.length > 0 && (
                  <div className="text-sm">
                    <div className="text-red-700 font-medium mb-1">建议：</div>
                    <ul className="list-disc list-inside text-red-600 space-y-1">
                      {message.finalReportV2.suggestions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Empty report */}
            {message.finalReportV2.report_type === 'empty' && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                <div className="text-4xl mb-2">📭</div>
                <div className="text-yellow-800 font-medium">暂无数据</div>
                <div className="text-yellow-600 text-sm mt-1">
                  未找到符合条件的数据，请尝试调整筛选条件
                </div>
              </div>
            )}

            {/* Chart (for success/hitl reports with data) */}
            {message.finalReportV2.report_type !== 'error' &&
             message.finalReportV2.chart_config &&
             message.finalReportV2.data &&
             message.finalReportV2.data.length > 0 && (
              <ChartRenderer
                report={{
                  chart_config: message.finalReportV2.chart_config,
                  is_comparison: false,
                }}
                data={message.finalReportV2.data}
                groupBy={[]}
                metrics={message.finalReportV2.metadata?.metrics || []}
              />
            )}

            {/* Highlights */}
            {message.finalReportV2.highlights?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">关键提示</h4>
                <HighlightList highlights={message.finalReportV2.highlights} />
              </div>
            )}

            {/* Quality Issues - Replaced with QualityIssueList component in Task 5.6 */}
            {message.finalReportV2.quality_info?.issues &&
             message.finalReportV2.quality_info.issues.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">质量提示</h4>
                <QualityIssueList issues={message.finalReportV2.quality_info.issues} />
              </div>
            )}

            {/* Data Table */}
            {message.finalReportV2.data_table?.columns?.length > 0 &&
             message.finalReportV2.data_table.rows?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">数据详情</h4>
                <DataTable {...message.finalReportV2.data_table} />
              </div>
            )}

            {/* Metadata (subtle) */}
            {message.finalReportV2.metadata && (
              <div className="text-xs text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
                <span>分析类型：{message.finalReportV2.metadata.analysis_type}</span>
                <span>实体层级：{message.finalReportV2.metadata.entity_level}</span>
                <span>实体数量：{message.finalReportV2.metadata.total_entities}</span>
                {message.finalReportV2.metadata.generated_at && (
                  <span>生成时间：{new Date(message.finalReportV2.metadata.generated_at).toLocaleString('zh-CN')}</span>
                )}
              </div>
            )}

            {/* Next Queries */}
            {message.finalReportV2.next_queries?.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-3">
                <h4 className="text-sm font-medium mb-2">推荐查询</h4>
                <ul className="space-y-1">
                  {message.finalReportV2.next_queries.map((query, idx) => (
                    <li
                      key={idx}
                      className="text-sm text-blue-600 cursor-pointer hover:underline"
                      onClick={() => onSuggestionClick?.(query)}
                    >
                      → {query}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
