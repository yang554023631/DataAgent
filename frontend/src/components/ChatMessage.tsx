import { MetricCard } from './MetricCard';
import { HighlightList } from './HighlightList';
import { DataTable } from './DataTable';
import ChartRenderer from './ChartRenderer';
import { FinalReport } from '../services/api';

interface ChatMessageProps {
  message: {
    role: 'user' | 'assistant';
    content: string;
    timestamp?: string;
    finalReport?: FinalReport;
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
                  <MetricCard key={idx} {...metric} />
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
                    !['impressions', 'clicks', 'cost', 'conversions', 'ctr', 'cvr', 'roi'].includes(col)
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

            {message.finalReport.highlights.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">关键洞察</h4>
                <HighlightList highlights={message.finalReport.highlights} />
              </div>
            )}

            {message.finalReport.data_table.columns.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">数据详情</h4>
                <DataTable {...message.finalReport.data_table} />
              </div>
            )}

            {message.finalReport.next_queries.length > 0 && (
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
      </div>
    </div>
  );
}
