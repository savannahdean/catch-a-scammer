// CaseDesk: where a case arrives, where hints are requested, and where the
// outcome is shown. Also the intake form for a new case (difficulty, scam type,
// and which kind of client you get).
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Card, Personality, Scenario } from '../api/types'
import { GlossaryText } from '../glossary/GlossaryText'
import { CardView, useOpenNav } from '../records/RecordView'
import { useScreens } from '../state/screens'
import { useSession } from '../state/session'
import { Badge, Notice, SectionLabel, Spinner } from '../ui/widgets'
import type { AppProps } from './types'

const DIFFICULTIES: { key: string; label: string; blurb: string }[] = [
  { key: 'easy', label: 'EASY', blurb: 'Few decoys, helpful clients, the meter never ends the case.' },
  { key: 'medium', label: 'MEDIUM', blurb: 'Unflagged infrastructure, a compromised redirector, clients who need asking.' },
  { key: 'hard', label: 'HARD', blurb: 'False flags, CDN fronting, liars and rude clients, unmask the real person.' },
  { key: 'expert', label: 'EXPERT', blurb: 'Everything above, with fewer hints and less forgiving clients.' },
]

function diffColor(d: string) {
  return d === 'hard' || d === 'expert' ? 'var(--danger)' : d === 'medium' ? 'var(--warn)' : 'var(--ok)'
}

function Intake({ onDone }: { onDone?: () => void }) {
  const s = useSession()
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [people, setPeople] = useState<Personality[]>([])
  const [scenario, setScenario] = useState('random')
  const [personality, setPersonality] = useState('random')

  useEffect(() => {
    api.scenarios().then(setScenarios).catch(() => setScenarios([]))
    api.personalities().then(setPeople).catch(() => setPeople([]))
  }, [])

  const start = async (difficulty: string) => {
    if (await s.startNewCase({ difficulty, scenario, personality })) onDone?.()
  }

  return (
    <div className="intake">
      <label className="form-label" htmlFor="scenario">
        SCAM TYPE
      </label>
      <select id="scenario" className="field" value={scenario} onChange={(e) => setScenario(e.target.value)}>
        <option value="random">Random (the queue decides)</option>
        {scenarios.map((sc) => (
          <option key={sc.key} value={sc.key}>
            {sc.title}
          </option>
        ))}
      </select>
      {scenario !== 'random' && (
        <div className="form-help">{scenarios.find((x) => x.key === scenario)?.real_world_basis}</div>
      )}
      <label className="form-label" htmlFor="client">
        CLIENT
      </label>
      <select id="client" className="field" value={personality} onChange={(e) => setPersonality(e.target.value)}>
        <option value="random">Random for the difficulty</option>
        {people.map((p) => (
          <option key={p.key} value={p.key}>
            {p.label} (usually {p.difficulties.join(', ')})
          </option>
        ))}
      </select>
      {personality !== 'random' && <div className="form-help">{people.find((x) => x.key === personality)?.summary}</div>}
      <div className="form-label">DIFFICULTY</div>
      <div className="difficulty-grid">
        {DIFFICULTIES.map((d) => (
          <button key={d.key} type="button" className="diff-btn" disabled={s.busy} onClick={() => void start(d.key)}>
            <span className="diff-name" style={{ color: diffColor(d.key) }}>
              {d.label}
            </span>
            <span className="diff-blurb">{d.blurb}</span>
          </button>
        ))}
      </div>
      {s.busy && <Spinner label="Generating the case: people, accounts, infrastructure, the crew behind it..." />}
      {!s.online && <Notice tone="error">The game server is offline. Start the API (see the README) and try again.</Notice>}
    </div>
  )
}

export function CaseDesk(_: AppProps) {
  const s = useSession()
  const screens = useScreens()
  const nav = useOpenNav()
  const [exhibits, setExhibits] = useState<Card[] | null>(null)
  const [showIntake, setShowIntake] = useState(false)
  const b = s.brief
  const revealed = s.chat?.messages.filter((m) => m.cards.length).length ?? 0

  // exhibits reload when the case changes, and when the client hands something over
  useEffect(() => {
    if (s.caseId == null) return setExhibits(null)
    let live = true
    api
      .exhibits(s.caseId)
      .then((x) => live && setExhibits(x.cards))
      .catch(() => live && setExhibits([]))
    return () => {
      live = false
    }
  }, [s.caseId, revealed])

  if (s.caseId == null || !b) {
    return (
      <div className="app casedesk">
        <div className="app-body">
          <div className="intake-card">
            <div className="eyebrow">INCIDENT QUEUE</div>
            <h2>No case assigned</h2>
            <p className="dim">
              Pick a difficulty and the queue hands you a fresh incident. Cases are generated when you ask, so the
              people, accounts, infrastructure and the crew behind them differ every time. Your client, the person who
              reported it, will be waiting in the Messenger.
            </p>
            <Intake />
          </div>
        </div>
      </div>
    )
  }

  const closed = b.status !== 'open'
  const studyPending = s.studyOpen && !!s.participantId && closed && s.studyStatus && !s.studyStatus.post_done
  return (
    <div className="app casedesk">
      <div className="ticket-head">
        <div className="ticket-code">CASE #{b.case_code}</div>
        <div className="ticket-badges">
          <Badge color={diffColor(b.difficulty)}>{b.difficulty.toUpperCase()}</Badge>
          <Badge color={b.status === 'solved' ? 'var(--ok)' : b.status === 'failed' ? 'var(--danger)' : 'var(--title-idle)'}>
            {b.status === 'solved' ? 'CLOSED: SOLVED' : b.status === 'failed' ? 'CLOSED: CLIENT WITHDREW' : 'OPEN'}
          </Badge>
          {b.client && <Badge color="var(--noise)">CLIENT: {b.client.label.toUpperCase()}</Badge>}
        </div>
        <div className="ticket-meta">
          attempts {b.attempts} · hints {b.hints_used}
          {b.status === 'solved' ? ` · score ${b.score}` : ''}
        </div>
      </div>
      <div className="action-strip">
        <button type="button" className="btn" disabled={!b.entry_domain} onClick={() => s.requestOpen('intelsearch', b.entry_domain)} data-tour="open-link">
          OPEN LINK IN INTELSEARCH
        </button>
        <button type="button" className="btn" onClick={() => s.requestOpen('messenger')}>
          MESSAGE CLIENT{s.unread ? ` (${s.unread})` : ''}
        </button>
        <button type="button" className="btn" disabled={closed} onClick={() => void s.requestHint()} data-tour="hint">
          REQUEST HINT
        </button>
        <button type="button" className="btn" onClick={() => s.requestOpen('casereport')}>
          FILE REPORT
        </button>
        <button type="button" className="btn" onClick={() => setShowIntake(true)}>
          NEW CASE
        </button>
      </div>
      <div className="app-body">
        {studyPending && (
          <div className="callout callout-accent">
            <div>
              <b>Thanks for playing as part of the study.</b> When you're done, the post-game survey takes about three
              minutes.
            </div>
            <button type="button" className="btn btn-primary" onClick={screens.toPostSurvey}>
              TAKE THE POST-GAME SURVEY
            </button>
          </div>
        )}
        {s.lastHint && (
          <div className="callout callout-warn">
            <div className="eyebrow">ANALYST NOTE</div>
            {s.lastHint}
          </div>
        )}
        {closed && b.resolution_text && (
          <div className={`callout ${b.status === 'solved' ? 'callout-ok' : 'callout-danger'}`}>
            <div className="eyebrow">{b.status === 'solved' ? 'CASE RESOLVED' : 'WHAT REALLY HAPPENED'}</div>
            <div className="mono-text">{b.resolution_text}</div>
          </div>
        )}
        <pre className="briefing" data-tour="briefing">
          <GlossaryText text={b.briefing} />
        </pre>
        <SectionLabel>EXHIBITS FROM THE REPORTING PARTY</SectionLabel>
        <p className="dim small">
          Everything the client handed over. Pin the exhibit that started it: your evidence chain has to connect back to
          it. Some clients hold things back; ask them in the Messenger.
        </p>
        {exhibits == null ? (
          <Spinner />
        ) : (
          <div className="record-list" data-tour="exhibits">
            {exhibits.map((c, i) => (
              <CardView key={i} card={c} nav={nav} />
            ))}
          </div>
        )}
      </div>
      {showIntake && (
        <div className="overlay" role="dialog" aria-modal="true" aria-label="Request a new case">
          <div className="overlay-card">
            <h3>Request a new case?</h3>
            <p className="dim small">The current case stays on file, but your desk switches to the new one.</p>
            <Intake onDone={() => setShowIntake(false)} />
            <div className="overlay-actions">
              <button type="button" className="btn" onClick={() => setShowIntake(false)}>
                CANCEL
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
