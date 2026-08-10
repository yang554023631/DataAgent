import React from 'react';
import { Check, X, Loader2, Minus } from 'lucide-react';

export interface StepItem {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'success' | 'failed' | 'skipped';
  durationMs?: number;
}

interface StepProgressProps {
  steps: StepItem[];
  title?: string;
}

const StepProgress: React.FC<StepProgressProps> = ({ steps, title = '正在分析...' }) => {
  const getStatusIcon = (status: StepItem['status']) => {
    switch (status) {
      case 'success':
        return <Check className="w-4 h-4 text-white" />;
      case 'failed':
        return <X className="w-4 h-4 text-white" />;
      case 'active':
        return <Loader2 className="w-4 h-4 text-white animate-spin" />;
      case 'skipped':
        return <Minus className="w-4 h-4 text-white" />;
      default:
        return null;
    }
  };

  const getStatusStyles = (status: StepItem['status']) => {
    switch (status) {
      case 'success':
        return 'bg-green-500 border-green-500';
      case 'failed':
        return 'bg-red-500 border-red-500';
      case 'active':
        return 'bg-blue-500 border-blue-500';
      case 'skipped':
        return 'bg-gray-400 border-gray-400';
      default:
        return 'bg-white border-gray-300';
    }
  };

  const getLabelStyles = (status: StepItem['status']) => {
    switch (status) {
      case 'success':
        return 'text-gray-700';
      case 'failed':
        return 'text-red-600 font-medium';
      case 'active':
        return 'text-blue-600 font-medium';
      case 'skipped':
        return 'text-gray-400';
      default:
        return 'text-gray-400';
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
      {title && (
        <h4 className="text-sm font-medium text-gray-700 mb-3">{title}</h4>
      )}
      <div className="space-y-2">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-start gap-3 relative">
            {/* Connector line */}
            {index < steps.length - 1 && (
              <div className="absolute left-[15px] top-7 bottom-0 w-0.5 bg-gray-200" style={{ marginTop: 0 }} />
            )}
            {/* Step circle */}
            <div className="relative z-10">
              <div
                data-status={step.status}
                className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${getStatusStyles(step.status)}`}
              >
                {getStatusIcon(step.status)}
              </div>
            </div>
            {/* Step label */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span data-status={step.status} className={`text-sm ${getLabelStyles(step.status)}`}>
                  {step.label}
                </span>
                {step.durationMs !== undefined && step.status === 'success' && (
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {formatDuration(step.durationMs)}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StepProgress;