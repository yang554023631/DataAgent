import React from 'react';
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import type { QualityIssueV2 } from '../services/api';

interface QualityIssueListProps {
  issues: QualityIssueV2[];
}

const formatValue = (val: any): string => {
  if (val === undefined || val === null) return '-';
  if (typeof val === 'number') return String(val);
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
};

export const QualityIssueList: React.FC<QualityIssueListProps> = ({ issues }) => {
  if (!issues || issues.length === 0) return null;

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'error':
      case 'hitl_required':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      default:
        return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'error':
      case 'hitl_required':
        return <AlertCircle className="w-4 h-4 flex-shrink-0" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 flex-shrink-0" />;
      default:
        return <Info className="w-4 h-4 flex-shrink-0" />;
    }
  };

  return (
    <div className="space-y-2">
      {issues.map((issue, index) => (
        <div
          key={index}
          data-severity={issue.severity}
          className={`p-3 rounded-lg border ${getSeverityStyles(issue.severity)}`}
        >
          <div className="flex items-start gap-2">
            {getSeverityIcon(issue.severity)}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{issue.message}</div>
              {(issue.threshold !== undefined || issue.actual !== undefined) && (
                <div className="text-xs mt-1 opacity-80">
                  {issue.threshold !== undefined && <span>阈值：{formatValue(issue.threshold)}</span>}
                  {issue.threshold !== undefined && issue.actual !== undefined && <span className="mx-2">|</span>}
                  {issue.actual !== undefined && <span>实际：{formatValue(issue.actual)}</span>}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
