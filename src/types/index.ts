import type { ChatAttachment } from '@/utils/attachments';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  toolName?: string;
  category?: string;
  citations?: Array<{ title: string; url: string }>;
  durationMs?: number;
  attachments?: ChatAttachment[];
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  category?: string;
  result?: string;
  status: 'running' | 'done' | 'error';
  citations?: Array<{ title: string; url: string }>;
}

export interface InterruptEvent {
  thread_id: string;
  action: string;
  preview: string;
  args?: Record<string, unknown>;
}

export type { SidecarWsServerMessage, SidecarWsMessage } from '@/types/wsEvents.generated';

export interface Session {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at?: string;
}
