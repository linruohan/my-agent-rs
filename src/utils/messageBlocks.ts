import type { Message } from '@/types';

export interface UserMessageBlock {
  kind: 'user';
  message: Message;
}

export interface AssistantTurnBlock {
  kind: 'assistant-turn';
  id: string;
  tools: Message[];
  assistant: Message | null;
}

export type MessageBlock = UserMessageBlock | AssistantTurnBlock;

export function buildMessageBlocks(messages: Message[]): MessageBlock[] {
  const blocks: MessageBlock[] = [];
  let i = 0;

  while (i < messages.length) {
    const msg = messages[i];

    if (msg.role === 'user') {
      blocks.push({ kind: 'user', message: msg });
      i++;
      continue;
    }

    if (msg.role === 'tool') {
      const tools: Message[] = [];
      while (i < messages.length && messages[i].role === 'tool') {
        tools.push(messages[i]);
        i++;
      }
      let assistant: Message | null = null;
      if (i < messages.length && messages[i].role === 'assistant') {
        assistant = messages[i];
        i++;
      }
      const id = assistant?.id ?? tools[0]?.id ?? `turn-${blocks.length}`;
      blocks.push({ kind: 'assistant-turn', id, tools, assistant });
      continue;
    }

    if (msg.role === 'assistant') {
      blocks.push({
        kind: 'assistant-turn',
        id: msg.id,
        tools: [],
        assistant: msg,
      });
      i++;
      continue;
    }

    i++;
  }

  return blocks;
}
