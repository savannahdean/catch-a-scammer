// Shapes of what the FastAPI server sends. They mirror backend/server/compat.py,
// cards.py, messenger.py and study.py; when a server response changes, change it here.

export type Tone = '' | 'ok' | 'warn' | 'danger' | 'dim'
export type Difficulty = 'easy' | 'medium' | 'hard' | 'expert'
export type CaseStatus = 'open' | 'solved' | 'failed' | 'abandoned'

// ---------------------------------------------------------------- cards
/** Open another tool and search it for `query`. */
export interface OpenAction {
  app: string
  query: string
}

/** Load one record (an API path) into a tool window. */
export interface FetchAction {
  app: string
  path: string
  params: Record<string, string>
}

export interface Row {
  text: string
  right: string
  tone: Tone
  open?: OpenAction
  fetch?: FetchAction
}

export type Block =
  | { type: 'text'; label: string; text: string }
  | { type: 'mono'; label: string; text: string }
  | { type: 'meter'; label: string; value: number; low: string; high: string; note: string }
  | { type: 'rows'; label: string; note: string; rows: Row[] }

export interface Pin {
  entity_kind: string
  entity_id: number
  label: string
}

/** A server-described record (see backend/server/cards.py). */
export interface Card {
  card: string
  kind_label: string
  title: string
  subtitle: string
  status: string
  fields: [string, string | number, Tone?][]
  blocks: Block[]
  pin: Pin | null
}

// ------------------------------------------------- the original record shapes
export interface DomainRecord {
  kind: 'domain'
  domain_id: number
  domain_name: string
  status: string
  first_seen: string
  last_seen: string
  registered: string
  registrar: string
  lookalike_of: string
  associated_ips: { ip_id: number; ip_address: string; first_seen: string; last_seen: string }[]
  delivers_malware: { malware_id: number; family_name: string }[]
}

export interface IpRecord {
  kind: 'ip'
  ip_id: number
  ip_address: string
  status: string
  asn: string
  provider_name: string
  provider_reputation: string
  abuse_email: string
  tags: string
  reverse_dns: string
  country: string
  region: string
  city: string
  related_domains: { domain_id: number; domain_name: string; status: string; first_seen: string }[]
  related_malware: { malware_id: number; family_name: string }[]
}

export interface MalwareRecord {
  kind: 'malware'
  malware_id: number
  family_name: string
  malware_type: string
  first_observed: string
  source: string
  campaigns: { campaign_id: number; name: string }[]
  infrastructure: { ip_address: string }[]
}

export interface CampaignRecord {
  kind: 'campaign'
  campaign_id: number
  name: string
  description: string
  active_since: string
  actors: { alias: string }[]
  attribution_sources: string[]
}

export interface ActorRecord {
  kind: 'actor'
  actor_id: number
  alias: string
  motivation: string
  origin_region: string
  first_attributed: string
  notes: string
  campaigns: { name: string }[]
  known_domains: { domain_name: string; status: string }[]
}

export interface PersonRecord {
  kind: 'person'
  person_id: number
  full_name: string
  city: string
  country: string
  employer: string
  job_title: string
  socials: Record<string, string>
}

export interface ArticleRecord {
  kind: 'article'
  title: string
  outlet: string
  published: string
  body: string
  reveals_alias: boolean
}

export type LegacyRecord =
  | DomainRecord
  | IpRecord
  | MalwareRecord
  | CampaignRecord
  | ActorRecord
  | PersonRecord
  | ArticleRecord

/** Anything a tool can show as one record. */
export type AnyRecord = Card | LegacyRecord

export function isCard(r: AnyRecord): r is Card {
  return (r as Card).card !== undefined
}

/** Every search answers with this envelope. */
export interface Envelope {
  query: string
  found: boolean
  message: string
  cards: Card[]
  domains?: DomainRecord[]
  ips?: IpRecord[]
  malware?: MalwareRecord[]
  campaigns?: CampaignRecord[]
  actors?: ActorRecord[]
  persons?: PersonRecord[]
  articles?: ArticleRecord[]
}

// ---------------------------------------------------------------- case
export interface ReportField {
  key: string
  label: string
  kind: string
}

export interface Brief {
  case_id: number
  case_code: string
  difficulty: Difficulty
  scenario: string
  briefing: string
  entry_domain: string
  incident_at: string
  report_fields: ReportField[]
  attempts: number
  hints_used: number
  status: CaseStatus
  score: number
  resolution_text: string
  victim_name: string
  client: { name: string; personality: string; label: string } | null
  /** only in the response that creates the case; the client stores it */
  case_key?: string
}

export interface EvidenceItem {
  evidence_id: number
  entity_kind: string
  entity_id: number
  label: string
}

export interface Scenario {
  key: string
  title: string
  category: string
  real_world_basis: string
  player_skill: string
  report_fields: ReportField[]
}

export interface Personality {
  key: string
  label: string
  summary: string
  patience: number
  disclosure: 'upfront' | 'asked' | 'pressed' | 'proof'
  nag_after_s: number | null
  difficulties: Difficulty[]
}

export interface ReportOptions {
  fields: (ReportField & { options: { entity_id: number; label: string }[] })[]
}

export interface Verdict {
  is_correct: boolean
  score: number
  attempt_no: number
  verdicts: { field: string; submitted: string; correct?: boolean }[]
  narrative: string
  notes: string[]
  correct_count: number
  total: number
}

export interface GraphNode {
  node_id: string
  entity_id: number
  kind: string
  label: string
  query: string
  sublabel: string
  status: string
  in_evidence: boolean
}

export interface GraphEdge {
  src: string
  dst: string
  label: string
  confidence: number
}

// ---------------------------------------------------------------- messenger
export type Mood = 'calm' | 'annoyed' | 'angry' | 'furious'

export interface ChatMessage {
  id: number
  from: 'client' | 'player' | 'system'
  text: string
  at: string
  evidence: string | null
  cards: AnyRecord[]
  patience: number | null
}

export interface MessengerState {
  client: {
    name: string
    role: string
    personality: string
    label: string
    summary: string
    patience: number
    max_patience: number
    mood: Mood
    can_fire: boolean
    fired: boolean
    next_nag_in: number | null
    chases: boolean
    case_status: CaseStatus
  }
  messages: ChatMessage[]
  secrets: { text: string; uncovered: boolean }[] | null
}

// ---------------------------------------------------------------- study
export interface SurveyChoice {
  value: string
  label: string
}

export interface SurveyQuestion {
  key: string
  section: string
  prompt: string
  kind: 'number' | 'text' | 'longtext' | 'choice' | 'multi' | 'likert'
  options: SurveyChoice[] | { min: number; max: number; low?: string; high?: string }
  required: boolean
  show_if: Record<string, string[]> | null
}

export interface StudyStatus {
  participant_id: string
  pre_done: boolean
  post_done: boolean
  cases_played: number
  cases_closed: number
}
