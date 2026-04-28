import { AlertTriangle, Star, Layers, Users } from 'lucide-react';
import { Insight, InsightCard } from './InsightCard';

export interface InsightPanelProps {
  problems: Insight[];
  highlights: Insight[];
  summary?: string;
}

const DIMENSION_LABELS: Record<string, { label: string; icon: typeof Layers }> = {
  creative: { label: '素材维度', icon: Layers },
  ad_group: { label: '广告组维度', icon: Users },
};

export function InsightPanel({ problems, highlights, summary }: InsightPanelProps) {
  const hasInsights = problems.length > 0 || highlights.length > 0;

  // 按维度分组
  const groupByDimension = (insights: Insight[]) => {
    const grouped: Record<string, Insight[]> = {};
    for (const insight of insights) {
      const dim = insight.dimension || 'other';
      if (!grouped[dim]) grouped[dim] = [];
      // 去掉名称中的维度前缀
      const cleanInsight = {
        ...insight,
        name: insight.name
          .replace(/^\[素材\]\s*/, '')
          .replace(/^\[广告组\]\s*/, ''),
      };
      grouped[dim].push(cleanInsight);
    }
    return grouped;
  };

  const groupedProblems = groupByDimension(problems);
  const groupedHighlights = groupByDimension(highlights);

  if (!hasInsights) {
    return (
      <div className="bg-gray-50 rounded-lg p-6 text-center">
        <p className="text-gray-500 text-sm">数据表现平稳</p>
      </div>
    );
  }

  const renderDimensionGroup = (
    dim: string,
    insights: Insight[],
    type: 'problem' | 'highlight'
  ) => {
    const config = DIMENSION_LABELS[dim] || { label: '其他', icon: Layers };
    const Icon = config.icon;
    const bgColor = type === 'problem' ? 'bg-red-50' : 'bg-green-50';
    const textColor = type === 'problem' ? 'text-red-700' : 'text-green-700';

    return (
      <div key={`${dim}-${type}`} className={`${bgColor} rounded-lg p-4 mb-3`}>
        <div className="flex items-center gap-2 mb-3">
          <Icon className={`w-4 h-4 ${textColor}`} />
          <span className={`text-sm font-medium ${textColor}`}>
            {config.label} ({insights.length}条)
          </span>
        </div>
        <div className="space-y-2">
          {insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} compact />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {summary && (
        <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
          <p className="text-blue-700 text-sm font-medium">{summary}</p>
        </div>
      )}

      {problems.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <h3 className="font-semibold text-red-700">
              问题发现 ({problems.length})
            </h3>
          </div>
          {Object.entries(groupedProblems).map(([dim, items]) =>
            renderDimensionGroup(dim, items, 'problem')
          )}
        </div>
      )}

      {highlights.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Star className="w-5 h-5 text-green-500" />
            <h3 className="font-semibold text-green-700">
              数据亮点 ({highlights.length})
            </h3>
          </div>
          {Object.entries(groupedHighlights).map(([dim, items]) =>
            renderDimensionGroup(dim, items, 'highlight')
          )}
        </div>
      )}
    </div>
  );
}
