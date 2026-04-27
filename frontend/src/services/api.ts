import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export interface FinalReport {
  title: string;
  time_range?: { start: string; end: string };
  metrics: Array<{ name: string; value: string | number; trend?: string }>;
  highlights: Array<{ type: 'positive' | 'negative' | 'info'; text: string }>;
  insights?: {
    problems: Insight[];
    highlights: Insight[];
    summary?: string;
  };
  data_table: { columns: string[]; rows: any[][] };
  next_queries: string[];
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  finalReport?: FinalReport;
}

export interface Clarification {
  question: string;
  options: Array<{ value: string; label: string }>;
  allow_custom_input: boolean;
}

export interface Session {
  session_id: string;
}

export const apiService = {
  async createSession(): Promise<Session> {
    const response = await api.post('/sessions', {});
    return response.data;
  },

  async sendMessage(sessionId: string, content: string) {
    const response = await api.post(`/sessions/${sessionId}/messages`, { content });
    return response.data;
  },

  async submitClarification(sessionId: string, selectedValue: string) {
    const response = await api.post(`/sessions/${sessionId}/clarification`, {
      selected_value: selectedValue,
    });
    return response.data;
  },
};
