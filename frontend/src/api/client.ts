// The only module that talks to the server. Every call is a plain fetch to a
// relative URL: in development Vite proxies it to FastAPI (vite.config.ts), and
// in production FastAPI serves this app itself, so there is no base URL to set.
// Requests about a case carry that case's key (X-Case-Key): the server only
// tells the browser that started a case, and refuses the case without it.
import type {
  Brief,
  Card,
  EvidenceItem,
  GraphEdge,
  GraphNode,
  MessengerState,
  Personality,
  ReportOptions,
  Scenario,
  StudyStatus,
  SurveyQuestion,
  Verdict,
} from './types'
import { store } from '../state/storage'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** The secret that proves this browser started case n (see backend/server/guard.py). */
const caseKey = (n: number) => store.get(`caseKey.${n}`)

async function request<T>(method: string, path: string, body?: unknown, caseId?: number): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const key = caseId == null ? null : caseKey(caseId)
  if (key) headers['X-Case-Key'] = key
  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'The game server is unreachable. Is the API running on port 8000?')
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') detail = j.detail
      else if (Array.isArray(j.detail)) detail = j.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

const get = <T>(path: string, caseId?: number) => request<T>('GET', path, undefined, caseId)
const post = <T>(path: string, body: unknown = {}, caseId?: number) => request<T>('POST', path, body, caseId)
const del = <T>(path: string, caseId?: number) => request<T>('DELETE', path, undefined, caseId)

/** Build "/path?a=1&b=2". */
export function withParams(path: string, params: Record<string, string | number>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) q.set(k, String(v))
  return `${path}?${q.toString()}`
}

export interface NewCaseOptions {
  difficulty: string
  scenario: string
  personality: string
  participant_id?: string | null
}

export const api = {
  health: () => get<{ ok: boolean; world_entities: number }>('/health'),
  scenarios: () => get<Scenario[]>('/scenarios'),
  personalities: () => get<Personality[]>('/api/personalities'),

  /** Starts a case and keeps its key; the server sends the key only this once. */
  newCase: async (o: NewCaseOptions) => {
    const b = await post<Brief>('/api/cases', o)
    if (b.case_key) store.set(`caseKey.${b.case_id}`, b.case_key)
    return b
  },
  brief: (n: number) => get<Brief>(`/api/cases/${n}`, n),
  exhibits: (n: number) => get<{ cards: Card[] }>(`/api/cases/${n}/exhibits`, n),
  hint: (n: number) => post<{ body: string; penalty_applied: number }>(`/api/cases/${n}/hint`, {}, n),

  evidence: (n: number) => get<{ items: EvidenceItem[] }>(`/api/cases/${n}/evidence`, n),
  pin: (n: number, kind: string, id: number) =>
    post<{ items: EvidenceItem[] }>(`/api/cases/${n}/evidence`, { entity_kind: kind, entity_id: id }, n),
  unpin: (n: number, id: number) => del<{ items: EvidenceItem[] }>(`/api/cases/${n}/evidence/${id}`, n),

  reportOptions: (n: number) => get<ReportOptions>(`/api/cases/${n}/report-options`, n),
  submit: (n: number, answers: Record<string, number>) => post<Verdict>(`/api/cases/${n}/submit`, { answers }, n),
  graph: (n: number) => get<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`/api/cases/${n}/graph`, n),

  /** A tool search: GET path?case_id=n&q=... */
  search: <T>(path: string, caseId: number, q: string) => get<T>(withParams(path, { case_id: caseId, q }), caseId),
  /** A record link: GET path?case_id=n&... */
  fetchRecord: <T>(path: string, caseId: number, params: Record<string, string>) =>
    get<T>(withParams(path, { ...params, case_id: caseId }), caseId),

  messenger: (n: number) => get<MessengerState>(`/api/cases/${n}/messenger`, n),
  sendMessage: (n: number, text: string, evidenceId?: number) =>
    post<MessengerState>(`/api/cases/${n}/messenger`, { text, evidence_id: evidenceId ?? null }, n),

  study: {
    /** whether the study is taking new participants (STUDY_ENABLED on the server) */
    config: () => get<{ enabled: boolean }>('/api/study/config'),
    consent: () => get<{ version: string; text: string }>('/api/study/consent'),
    join: () =>
      post<{ participant_id: string }>('/api/study/participants', {
        consent: true,
        adult: true,
        user_agent: navigator.userAgent,
      }),
    status: (pid: string) => get<StudyStatus>(`/api/study/participants/${pid}`),
    withdraw: (pid: string) => del<{ ok: boolean }>(`/api/study/participants/${pid}`),
    questions: (phase: 'pre' | 'post') =>
      get<{ phase: string; questions: SurveyQuestion[] }>(`/api/study/questions?phase=${phase}`),
    answer: (pid: string, phase: 'pre' | 'post', answers: Record<string, unknown>) =>
      post<{ ok: boolean; quiz?: { before: number; after: number; total: number } }>(
        `/api/study/participants/${pid}/answers`,
        { phase, answers },
      ),
  },
}
