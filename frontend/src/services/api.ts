import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
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
