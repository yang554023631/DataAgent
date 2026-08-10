import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StepProgress from '../StepProgress';

describe('StepProgress', () => {
  const sampleSteps = [
    { id: 'intent_analyzer', label: '理解查询意图', status: 'success' as const },
    { id: 'cot_planner', label: '生成分析计划', status: 'active' as const },
    { id: 'filter_executor', label: '执行筛选查询', status: 'pending' as const },
    { id: 'analysis_executor', label: '执行分析查询', status: 'pending' as const },
  ];

  it('renders all step labels', () => {
    render(<StepProgress steps={sampleSteps} />);
    expect(screen.getByText('理解查询意图')).toBeInTheDocument();
    expect(screen.getByText('生成分析计划')).toBeInTheDocument();
    expect(screen.getByText('执行筛选查询')).toBeInTheDocument();
    expect(screen.getByText('执行分析查询')).toBeInTheDocument();
  });

  it('shows correct status icons', () => {
    const { container } = render(<StepProgress steps={sampleSteps} />);
    // Success step has checkmark or green indicator
    const successStep = container.querySelector('[data-status="success"]');
    expect(successStep).toBeInTheDocument();
    // Active step is highlighted
    const activeStep = container.querySelector('[data-status="active"]');
    expect(activeStep).toBeInTheDocument();
    // Pending steps are dimmed
    const pendingSteps = container.querySelectorAll('[data-status="pending"]');
    expect(pendingSteps.length).toBe(2);
  });

  it('handles skipped steps', () => {
    const steps = [...sampleSteps, { id: 'quality_checker', label: '质量校验', status: 'skipped' as const }];
    const { container } = render(<StepProgress steps={steps} />);
    const skipped = container.querySelector('[data-status="skipped"]');
    expect(skipped).toBeInTheDocument();
  });

  it('handles failed steps', () => {
    const steps = [
      { id: 'intent_analyzer', label: '理解查询意图', status: 'failed' as const },
    ];
    const { container } = render(<StepProgress steps={steps} />);
    const failed = container.querySelector('[data-status="failed"]');
    expect(failed).toBeInTheDocument();
  });
});