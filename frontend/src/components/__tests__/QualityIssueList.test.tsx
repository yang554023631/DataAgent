import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QualityIssueList } from '../QualityIssueList';

describe('QualityIssueList', () => {
  const issues = [
    {
      check_type: 'max_series_count',
      severity: 'error' as const,
      message: '趋势图系列数量超过上限',
      suggested_action: 'hitl',
      threshold: 20,
      actual: 35,
    },
    {
      check_type: 'min_data_points',
      severity: 'warning' as const,
      message: '数据点较少，趋势参考价值有限',
      suggested_action: 'warn',
      threshold: 2,
      actual: 2,
    },
  ];

  it('renders all issue messages', () => {
    render(<QualityIssueList issues={issues} />);
    expect(screen.getByText('趋势图系列数量超过上限')).toBeInTheDocument();
    expect(screen.getByText('数据点较少，趋势参考价值有限')).toBeInTheDocument();
  });

  it('shows severity indicators', () => {
    const { container } = render(<QualityIssueList issues={issues} />);
    // Error issue should have red styling
    const errorItem = container.querySelector('[data-severity="error"]');
    expect(errorItem).toBeInTheDocument();
    // Warning issue should have yellow/orange styling
    const warningItem = container.querySelector('[data-severity="warning"]');
    expect(warningItem).toBeInTheDocument();
  });

  it('shows threshold and actual values for errors', () => {
    render(<QualityIssueList issues={issues} />);
    expect(screen.getByText(/阈值：20/)).toBeInTheDocument();
    expect(screen.getByText(/实际：35/)).toBeInTheDocument();
  });
});
