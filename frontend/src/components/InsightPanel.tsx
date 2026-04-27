import { AlertTriangle, Star } from 'lucide-react';
import { Insight, InsightCard } from './InsightCard';

export interface InsightPanelProps {
  problems: Insight[];
  highlights: Insight[];
  summary?: string;
}

export function InsightPanel({ problems, highlights, summary }: InsightPanelProps) {
  const hasInsights = problems.length > 0 || highlights.length > 0;

  if (!hasInsights) {
    return (
      <div className="bg-gray-50 rounded-lg p-6 text-center">
      <p className="text-gray-500 text-sm">数据表现平稳</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
    {summary && (
        <div className="bg-gray-50 rounded-lg p-4">
        <p className="text-gray-700 text-sm">{summary}</p>
      </div>
    )}

    {problems.length > 0 && (
        <div>
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <h3 className="font-semibold text-red-700">
          问题发现 ({problems.length})
          </h3>
        </div>
        <div className="space-y-3 mt-3">
          {problems.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      </div>
    )}

    {highlights.length > 0 && (
        <div>
        <div className="flex items-center gap-2 mb-3">
          <Star className="w-5 h-5 text-green-500" />
          <h3 className="font-semibold text-green-700">
          数据亮点 ({highlights.length})
          </h3>
        </div>
        <div className="space-y-3 mt-3">
          {highlights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      </div>
    )}
    </div>
  );
}
