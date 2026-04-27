import { useState } from 'react';
import { AlertTriangle, Star, Lightbulb, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

export type InsightType = 'problem' | 'highlight' | 'info';
export type Severity = 'high' | 'medium' | 'low';

export interface Insight {
  id: string;
  type: InsightType;
  name: string;
  severity: Severity;
  evidence: string;
  suggestion: string;
  source: string;
}

export interface InsightCardProps {
  insight: Insight;
  defaultExpanded?: boolean;
}

const severityStyles: Record<Severity, { border: string; bg: string; text: string; badge: string }> = {
  high: {
    border: 'border-l-red-500',
    bg: 'bg-red-50',
    text: 'text-red-700',
    badge: 'bg-red-100 text-red-800',
  },
  medium: {
    border: 'border-l-amber-500',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    badge: 'bg-amber-100 text-amber-800',
  },
  low: {
    border: 'border-l-blue-500',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    badge: 'bg-blue-100 text-blue-800',
  },
};

const typeIcons = {
  problem: AlertTriangle,
  highlight: Star,
  info: Lightbulb,
};

const typeLabels: Record<InsightType, string> = {
  problem: '问题',
  highlight: '亮点',
  info: '提示',
};

const severityLabels: Record<Severity, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

export function InsightCard({ insight, defaultExpanded = false }: InsightCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const styles = severityStyles[insight.severity];
  const Icon = typeIcons[insight.type];

  return (
    <div
      className={clsx(
        'border-l-4 rounded-lg shadow-sm overflow-hidden transition-all duration-200',
        styles.border,
        styles.bg
      )}
    >
      <button
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 flex-1">
          <Icon className={clsx('w-5 h-5 flex-shrink-0', styles.text)} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium text-gray-900 truncate">{insight.name}</span>
              <span
                className={clsx(
                  'text-xs px-2 py-0.5 rounded-full font-medium',
                  styles.badge
                )}
              >
                {typeLabels[insight.type]}
              </span>
              {insight.type === 'problem' && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
                  严重程度: {severityLabels[insight.severity]}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500 truncate">来源: {insight.source}</p>
          </div>
        </div>
        <div className="ml-2 flex-shrink-0">
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100">
          <div className="pt-3">
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
              数据证据
            </h4>
            <p className="text-sm text-gray-600 bg-white rounded-md p-3 border border-gray-100">
              {insight.evidence}
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
              优化建议
            </h4>
            <p className="text-sm text-gray-600 bg-white rounded-md p-3 border border-gray-100">
              {insight.suggestion}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
