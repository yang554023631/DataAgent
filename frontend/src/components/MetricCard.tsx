import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
  name: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'flat';
}

export const MetricCard: React.FC<MetricCardProps> = ({ name, value, change, trend = 'flat' }) => {
  const getTrendIcon = () => {
    switch (trend) {
      case 'up': return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'down': return <TrendingDown className="w-4 h-4 text-red-500" />;
      default: return <Minus className="w-4 h-4 text-gray-500" />;
    }
  };

  const formatChange = (change?: number) => {
    if (change === undefined) return null;
    const sign = change > 0 ? '+' : '';
    return `${sign}${(change * 100).toFixed(1)}%`;
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 border border-gray-100">
      <div className="text-sm text-gray-500 mb-1">{name}</div>
      <div className="flex items-end justify-between">
        <span className="text-2xl font-bold text-gray-900">{value}</span>
        <div className="flex items-center gap-1">
          {getTrendIcon()}
          {change !== undefined && <span className="text-sm text-gray-600">{formatChange(change)}</span>}
        </div>
      </div>
    </div>
  );
};
