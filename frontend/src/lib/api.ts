import { supabase } from "./supabase";
import type {
  CalendarEvent,
  ErrorEntry,
  ErrorEntryInput,
  ErrorOverview,
  Label,
  Simulado,
  StudyBlock,
  Task,
  WeekView,
} from "./types";

// Remove barra(s) no final para nunca gerar URL com barra dupla (ex.: //api/...).
const API_URL = ((import.meta.env.VITE_API_URL as string) || "http://localhost:8000").replace(
  /\/+$/,
  ""
);

async function authHeader(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Erro de API que carrega o status HTTP (ex.: 403 = sem permissão).
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function doFetch<T>(path: string, init: RequestInit): Promise<T> {
  const headers = new Headers(init.headers);
  const auth = await authHeader();
  Object.entries(auth).forEach(([k, v]) => headers.set(k, v));

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, body?.detail || `Erro ${res.status}`);
  }
  return body as T;
}

// Cache leve de GETs + deduplicação de chamadas em voo. Isso evita refazer as
// mesmas requisições ao navegar entre telas (ex.: a "semana" carregada na
// Principal é reaproveitada em "Organizar semana") e junta chamadas idênticas
// disparadas ao mesmo tempo. Qualquer escrita (POST/DELETE/PATCH) limpa o cache.
const CACHE_TTL = 8000; // ms
type CacheEntry = { t: number; data: unknown };
const getCache = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<unknown>>();
let cacheEpoch = 0;

function invalidateCache() {
  getCache.clear();
  cacheEpoch++;
}

// Limpa o cache ao trocar de sessão/usuário (evita reaproveitar dados de outra conta).
export function clearApiCache() {
  invalidateCache();
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();

  if (method !== "GET") {
    const result = await doFetch<T>(path, init);
    invalidateCache(); // dados mudaram: próximos GETs buscam fresco
    return result;
  }

  const cached = getCache.get(path);
  if (cached && Date.now() - cached.t < CACHE_TTL) return cached.data as T;

  const pending = inflight.get(path);
  if (pending) return pending as Promise<T>;

  const startEpoch = cacheEpoch;
  const p = doFetch<T>(path, init)
    .then((data) => {
      // só guarda se nenhuma escrita invalidou o cache durante a requisição
      if (cacheEpoch === startEpoch) getCache.set(path, { t: Date.now(), data });
      return data;
    })
    .finally(() => {
      inflight.delete(path);
    });
  inflight.set(path, p);
  return p as Promise<T>;
}

function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const api = {
  // ---- acesso / whitelist ----
  me: () => request<{ email: string; authorized: boolean }>("/api/me"),

  // ---- caderno de erros ----
  errorOverview: () => request<ErrorOverview>("/api/errors/overview"),
  listErrorEntries: (params?: {
    subject?: string;
    error_type?: string;
    pending_redo?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params?.subject) q.set("subject", params.subject);
    if (params?.error_type) q.set("error_type", params.error_type);
    if (params?.pending_redo) q.set("pending_redo", "true");
    const qs = q.toString();
    return request<ErrorEntry[]>(`/api/errors/entries${qs ? `?${qs}` : ""}`);
  },
  createErrorEntry: (body: ErrorEntryInput) =>
    request<ErrorEntry>("/api/errors/entries", json(body)),
  setErrorRedone: (id: string, redone: boolean) =>
    request<ErrorEntry>(`/api/errors/entries/${id}/redo`, json({ redone })),
  deleteErrorEntry: (id: string) =>
    request<void>(`/api/errors/entries/${id}`, { method: "DELETE" }),

  // ---- simulados ----
  listSimulados: () => request<Simulado[]>("/api/simulados"),
  createSimulado: (body: {
    name: string;
    num_questions: number;
    num_correct: number;
    taken_on?: string | null;
  }) => request<Simulado>("/api/simulados", json(body)),
  deleteSimulado: (id: string) =>
    request<void>(`/api/simulados/${id}`, { method: "DELETE" }),

  // ---- labels ----
  listLabels: () => request<Label[]>("/api/labels"),
  createLabel: (body: { name: string; color?: string }) =>
    request<Label>("/api/labels", json(body)),
  deleteLabel: (id: string) => request<void>(`/api/labels/${id}`, { method: "DELETE" }),

  // ---- calendar ----
  calendarStatus: () => request<{ connected: boolean }>("/api/calendar/status"),
  connectCalendar: (provider_refresh_token: string) =>
    request<{ connected: boolean }>(
      "/api/calendar/connect",
      json({ provider_refresh_token })
    ),
  weekEvents: (weekStart: string) =>
    request<CalendarEvent[]>(`/api/calendar/week?week_start=${weekStart}`),

  // ---- planner ----
  listTasks: (weekStart: string) =>
    request<Task[]>(`/api/planner/tasks?week_start=${weekStart}`),
  createTask: (body: {
    label_id?: string | null;
    description: string;
    duration_min: number;
    week_start: string;
  }) => request<Task>("/api/planner/tasks", json(body)),
  deleteTask: (id: string) =>
    request<void>(`/api/planner/tasks/${id}`, { method: "DELETE" }),
  checkTask: (id: string, done: boolean) =>
    request<Task>(`/api/planner/tasks/${id}/check`, json({ done })),
  reallocateTask: (id: string, scheduledStart: string | null, scheduledEnd: string | null) =>
    request<Task>(
      `/api/planner/tasks/${id}/reallocate`,
      json({ scheduled_start: scheduledStart, scheduled_end: scheduledEnd })
    ),
  organize: (weekStart: string, taskIds?: string[]) =>
    request<{ scheduled: number; unscheduled: string[] }>(
      "/api/planner/organize",
      json({ week_start: weekStart, task_ids: taskIds ?? null })
    ),
  weekView: (weekStart: string) =>
    request<WeekView>(`/api/planner/week?week_start=${weekStart}`),
  // ---- blocos de estudo (criados no app) ----
  listStudyBlocks: () => request<StudyBlock[]>("/api/planner/study-blocks"),
  createStudyBlock: (body: {
    weekday: number;
    start: string;
    end: string;
    subject: string;
  }) => request<StudyBlock>("/api/planner/study-blocks", json(body)),
  deleteStudyBlock: (id: string) =>
    request<void>(`/api/planner/study-blocks/${id}`, { method: "DELETE" }),
};

