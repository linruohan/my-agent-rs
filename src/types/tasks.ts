export type ProjectStats = {
  total: number;
  completed: number;
  by_priority: Record<string, number>;
  by_status?: Record<string, number>;
};

export type SectionItem = {
  id: number;
  project_id: number;
  name: string;
  start_at: string;
  end_at: string;
  owner: string;
  goals: string;
  status: string;
  stats?: ProjectStats;
};

export type SectionSummary = {
  id: number;
  section_id: number;
  summary_date: string;
  progress: string;
  risks: string;
  challenges: string;
  notes: string;
};

export type ProjectDoc = {
  id: number;
  project_id: number;
  title: string;
  file_path: string;
  note: string;
  rag_ingest?: string;
};

export type ProjectItem = {
  id: number;
  name: string;
  description: string;
  status: string;
  start_at?: string;
  end_at?: string;
  due_date: string;
  owner?: string;
  is_inbox?: boolean;
  stats?: ProjectStats;
  doc_count?: number;
  remind_at?: string;
};

export type TodoItem = {
  id: number;
  title: string;
  due_date: string;
  priority: string;
  completed: boolean;
  project_id: number | null;
  section_id?: number | null;
  description: string;
  remind_at?: string;
  owner?: string;
  status?: string;
  tags?: string[];
  attachments?: Array<{ type: string; value: string }>;
};

export type LabelItem = {
  id: number;
  name: string;
  color: string;
  created_at?: string;
  updated_at?: string;
};

export type TaskReminderRow = {
  job_id: string;
  run_at: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id?: number;
};

export type TasksSnapshot = {
  inbox?: ProjectItem | null;
  projects?: ProjectItem[];
  sections?: SectionItem[];
  todos?: TodoItem[];
  reminders?: TaskReminderRow[];
  labels?: LabelItem[];
};
