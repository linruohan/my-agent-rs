export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  toolName?: string;
  category?: string;
  citations?: Array<{ title: string; url: string }>;
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  category?: string;
  result?: string;
  status: 'running' | 'done' | 'error';
}

export interface InterruptEvent {
  thread_id: string;
  action: string;
  preview: string;
}

export interface Session {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at?: string;
}
