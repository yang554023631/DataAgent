import { describe, it, expect, vi } from 'vitest';
import type { FinalReportV2, ReportType } from '../services/api';
import { dispatchEvent, detectHitlType } from '../services/api';

describe('FinalReportV2 type', () => {
  it('success report has required fields', () => {
    const report: FinalReportV2 = {
      report_type: 'success' as ReportType,
      title: '测试报告',
      data_table: { columns: [], rows: [] },
      highlights: [],
      next_queries: [],
    };
    expect(report.report_type).toBe('success');
    expect(report.title).toBe('测试报告');
  });

  it('error report has error fields', () => {
    const report: FinalReportV2 = {
      report_type: 'error' as ReportType,
      title: '错误报告',
      error_type: 'query_failed',
      message: '未能生成有效的分析结果',
      reason: '测试原因',
      data_table: { columns: [], rows: [] },
      highlights: [],
      next_queries: [],
      suggestions: ['调整筛选条件'],
      recommended_queries: ['查看全部数据'],
    };
    expect(report.error_type).toBe('query_failed');
    expect(report.suggestions?.length).toBe(1);
  });
});

describe('dispatchEvent', () => {
  const stepLabels: Record<string, string> = {
    intent_analyzer: '理解查询意图',
    cot_planner: '生成分析计划',
  };

  it('step_start 事件应该调用 onStepStart 并传入正确的 step 名称', () => {
    const onStepStart = vi.fn();
    const handlers = { onStepStart };
    const event = { type: 'step_start', step: 'intent_analyzer' };

    dispatchEvent(event, handlers, stepLabels);

    expect(onStepStart).toHaveBeenCalledTimes(1);
    expect(onStepStart).toHaveBeenCalledWith('intent_analyzer');
  });

  it('step_complete 事件应该调用 onStepComplete 并传入 step, status, duration', () => {
    const onStepComplete = vi.fn();
    const handlers = { onStepComplete };
    const event = { type: 'step_complete', step: 'cot_planner', status: 'success', duration_ms: 250 };

    dispatchEvent(event, handlers, stepLabels);

    expect(onStepComplete).toHaveBeenCalledTimes(1);
    expect(onStepComplete).toHaveBeenCalledWith('cot_planner', 'success', 250);
  });

  it('step_complete 没有 status 时默认 success', () => {
    const onStepComplete = vi.fn();
    const handlers = { onStepComplete };
    const event = { type: 'step_complete', step: 'cot_planner' };

    dispatchEvent(event, handlers, stepLabels);

    expect(onStepComplete).toHaveBeenCalledWith('cot_planner', 'success', undefined);
  });

  it('hitl 事件应该调用 onHitl 并传入正确的数据', () => {
    const onHitl = vi.fn();
    const handlers = { onHitl };
    const event = {
      type: 'hitl',
      hitl_type: 'cot_clarification',
      question: '请选择维度',
      options: [
        { value: '渠道', label: '渠道' },
        { value: '创意', label: '创意' },
      ],
      allow_custom_input: false,
    };

    dispatchEvent(event, handlers, stepLabels);

    expect(onHitl).toHaveBeenCalledTimes(1);
    expect(onHitl).toHaveBeenCalledWith({
      hitl_type: 'cot_clarification',
      question: '请选择维度',
      options: [
        { value: '渠道', label: '渠道' },
        { value: '创意', label: '创意' },
      ],
      quality_issues: undefined,
      allow_custom_input: false,
    });
  });

  it('hitl 事件没有 allow_custom_input 时默认为 true', () => {
    const onHitl = vi.fn();
    const handlers = { onHitl };
    const event = {
      type: 'hitl',
      hitl_type: 'cot_clarification',
      question: '请选择',
      options: [],
    };

    dispatchEvent(event, handlers, stepLabels);

    expect(onHitl).toHaveBeenCalledWith(
      expect.objectContaining({ allow_custom_input: true })
    );
  });

  it('final_report 事件应该调用 onFinalReport 并传入报告', () => {
    const onFinalReport = vi.fn();
    const handlers = { onFinalReport };
    const report = {
      report_type: 'success',
      title: '测试报表',
      data_table: { columns: [], rows: [] },
      highlights: [],
      next_queries: [],
    };
    const event = { type: 'final_report', data: report };

    dispatchEvent(event, handlers, stepLabels);

    expect(onFinalReport).toHaveBeenCalledTimes(1);
    expect(onFinalReport).toHaveBeenCalledWith(report);
  });

  it('error 事件应该调用 onError 并传入消息', () => {
    const onError = vi.fn();
    const handlers = { onError };
    const event = { type: 'error', message: '连接超时' };

    dispatchEvent(event, handlers, stepLabels);

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('连接超时');
  });

  it('未知事件类型应该被静默忽略', () => {
    const onStepStart = vi.fn();
    const onStepComplete = vi.fn();
    const onHitl = vi.fn();
    const onFinalReport = vi.fn();
    const onError = vi.fn();
    const handlers = { onStepStart, onStepComplete, onHitl, onFinalReport, onError };
    const event = { type: 'unknown_event', some_data: 'test' };

    // Should not throw
    expect(() => dispatchEvent(event, handlers, stepLabels)).not.toThrow();

    // No handler should be called
    expect(onStepStart).not.toHaveBeenCalled();
    expect(onStepComplete).not.toHaveBeenCalled();
    expect(onHitl).not.toHaveBeenCalled();
    expect(onFinalReport).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('没有对应的 handler 时不应该报错', () => {
    const handlers = {};
    const event = { type: 'step_start', step: 'intent_analyzer' };

    expect(() => dispatchEvent(event, handlers, stepLabels)).not.toThrow();
  });
});

describe('detectHitlType', () => {
  it('quality_issues 数组非空时返回 quality_hitl', () => {
    const event = {
      quality_issues: [
        { check_type: 'sample_size', severity: 'warning', message: '样本量小' }
      ],
      options: [{ value: 'option1', label: '选项1' }],
    };

    expect(detectHitlType(event)).toBe('quality_hitl');
  });

  it('options 包含 continue 时返回 quality_hitl', () => {
    const event = {
      options: [
        { value: 'continue', label: '继续查看结果' },
        { value: 'rephrase', label: '重新表述问题' },
      ],
    };

    expect(detectHitlType(event)).toBe('quality_hitl');
  });

  it('options 包含 rephrase 时返回 quality_hitl', () => {
    const event = {
      options: [
        { value: 'rephrase', label: '重新表述问题' },
      ],
    };

    expect(detectHitlType(event)).toBe('quality_hitl');
  });

  it('两个条件都不满足时返回 cot_clarification', () => {
    const event = {
      options: [
        { value: '渠道', label: '渠道' },
        { value: '创意', label: '创意' },
      ],
    };

    expect(detectHitlType(event)).toBe('cot_clarification');
  });

  it('没有 options 和 quality_issues 时返回 cot_clarification', () => {
    const event = {};

    expect(detectHitlType(event)).toBe('cot_clarification');
  });

  it('quality_issues 为空数组时返回 cot_clarification', () => {
    const event = {
      quality_issues: [],
      options: [{ value: '渠道', label: '渠道' }],
    };

    expect(detectHitlType(event)).toBe('cot_clarification');
  });
});
