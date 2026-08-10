import { describe, it, expect } from 'vitest';
import type { FinalReportV2, ReportType } from '../services/api';

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
