export interface ChatCommand {
  id: string;
  label: string;
  description: string;
  category: 'session' | 'skill';
  keywords?: string[];
}

export const SESSION_COMMANDS: ChatCommand[] = [
  { id: 'new', label: '/new', description: '开始新会话', category: 'session' },
  { id: 'save', label: '/save', description: '导出当前对话为 JSON', category: 'session' },
  { id: 'retry', label: '/retry', description: '重试上一条用户消息', category: 'session' },
  { id: 'undo', label: '/undo', description: '移除最后一轮对话', category: 'session' },
  { id: 'title', label: '/title', description: '重命名当前会话', category: 'session' },
  { id: 'clear', label: '/clear', description: '清空输入框', category: 'session' },
  { id: 'stop', label: '/stop', description: '停止当前生成', category: 'session' },
  { id: 'tsk', label: '/tsk', description: '任务：list/add/mod/del/详情', category: 'session', keywords: ['task', 'todo'] },
  { id: 'pro', label: '/pro', description: '项目：list/add/mod/del/sec/详情', category: 'session', keywords: ['project'] },
  { id: 'sec', label: '/sec', description: 'Section：list/add/mod/del/详情', category: 'session', keywords: ['section'] },
  { id: 'ocr', label: '/ocr', description: '图片 OCR 识图', category: 'session', keywords: ['ocr', '识别', '文字'] },
];

export function toolToSkill(name: string, description?: string): ChatCommand {
  return {
    id: `skill:${name}`,
    label: `@${name}`,
    description: description || `调用 ${name} 技能`,
    category: 'skill',
    keywords: [name],
  };
}

export function filterCommands(
  query: string,
  commands: ChatCommand[],
  skills: ChatCommand[]
): { session: ChatCommand[]; skills: ChatCommand[] } {
  const q = query.toLowerCase().replace(/^\//, '').trim();
  const match = (item: ChatCommand) => {
    if (!q) return true;
    const hay = `${item.label} ${item.description} ${(item.keywords || []).join(' ')}`.toLowerCase();
    return hay.includes(q);
  };
  return {
    session: commands.filter(match),
    skills: skills.filter(match),
  };
}
