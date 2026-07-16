// ---------- Caderno de erros ----------
export type ErrorType = "conteudo" | "atencao" | "interpretacao";

export interface ErrorEntry {
  id: string;
  exam: string | null;
  error_date: string | null;
  question: number | null;
  area: string | null;
  subject: string;
  topic: string;
  error_type: ErrorType;
  redone: boolean;
  redo_on: string | null;
  created_at: string;
}

export interface TypeStat {
  type: ErrorType;
  count: number;
  share: number;
}

export interface TopTopic {
  topic: string;
  count: number;
}

export interface SubjectStat {
  subject: string;
  count: number;
  share: number;
  top_topic: TopTopic | null;
  top_type: ErrorType | null;
}

export interface EvolutionBucket {
  week_start: string;
  count: number;
}

export interface ErrorOverview {
  total: number;
  pending_redo: number;
  by_type: TypeStat[];
  by_subject: SubjectStat[];
  worst_subject: string | null;
  worst_topic_overall: TopTopic | null;
  evolution: EvolutionBucket[];
}

export interface ErrorEntryInput {
  exam?: string | null;
  error_date?: string | null;
  question?: number | null;
  area?: string | null;
  subject: string;
  topic: string;
  error_type: ErrorType;
  redo_on?: string | null;
}

export interface Simulado {
  id: string;
  name: string;
  num_questions: number;
  num_correct: number;
  percent: number;
  taken_on: string | null;
  created_at: string;
}

export interface Label {
  id: string;
  name: string;
  color: string;
}

export type EffectiveStatus = "pending" | "done" | "atrasado";

export interface Task {
  id: string;
  label_id: string | null;
  description: string;
  duration_min: number;
  week_start: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  status: string;
  is_late: boolean;
  effective_status: EffectiveStatus;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  kind: "aula" | "estudo" | "simulado" | "outro" | "pendencias";
  subject: string | null;
}

// Tipos que o usuário pode escolher no popup (override).
export type OverrideKind = "estudo" | "aula" | "outro";

export interface WeekView {
  week_start: string;
  events: CalendarEvent[];
  tasks: Task[];
  server_now: string;
}

export interface StudyBlock {
  id: string;
  weekday: number; // 0 = segunda ... 6 = domingo
  start: string;   // "HH:MM"
  end: string;     // "HH:MM"
  subject: string;
  kind: OverrideKind; // estudo | aula | outro
}

export interface WeekView {
  has_study_time: boolean;
}
