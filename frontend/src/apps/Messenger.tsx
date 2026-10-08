// Messenger: chat with the client (the person who reported the case).
//
// The client is driven by the server (backend/server/messenger.py): it picks out
// keywords in what you type, answers in its personality's voice, and keeps the
// embarrassing part back until you ask the right way or show proof from your
// evidence board. This window only draws the conversation, the mood meter and
// the reply timer, and adds a short "typing..." pause before each client message.
import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import type { ChatMessage } from '../api/types'
import { RecordView, useOpenNav } from '../records/RecordView'
import { useSession } from '../state/session'
import { MOOD_COLOR, kindLabel } from '../theme'
import { Badge, Notice, Spinner } from '../ui/widgets'
import type { AppProps } from './types'

const STARTERS = [
  'What happened?',
  'When did this happen?',
  'How did they contact you?',
  'Did you click a link or enter a password?',
  'Did you pay or send any money?',
  'Is there anything you are leaving out?',
]

function initials(name: string) {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function clock(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function typingDelay(m: ChatMessage) {
  return m.from === 'client' ? Math.min(2200, Math.max(650, 350 + m.text.length * 16)) : 0
}

export function Messenger({ active }: AppProps) {
  const s = useSession()
  const nav = useOpenNav()
  const chat = s.chat
  const msgs = chat?.messages ?? []
  const [visible, setVisible] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [showPicker, setShowPicker] = useState(false)
  const [now, setNow] = useState(Date.now())
  const fetchedAt = useRef(Date.now())
  const list = useRef<HTMLDivElement>(null)

  // first load: show the history at once; afterwards reveal new messages one at a time
  useEffect(() => {
    if (chat && visible == null) setVisible(msgs.length)
    fetchedAt.current = Date.now()
  }, [chat])
  useEffect(() => {
    setVisible(null)
  }, [s.caseId])
  useEffect(() => {
    if (visible == null || visible >= msgs.length) return
    const t = window.setTimeout(() => setVisible((v) => (v ?? 0) + 1), typingDelay(msgs[visible]))
    return () => window.clearTimeout(t)
  }, [visible, msgs])

  const shown = msgs.slice(0, visible ?? msgs.length)
  const typing = visible != null && visible < msgs.length && msgs[visible].from === 'client'

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: 'smooth' })
  }, [shown.length, typing, pending])

  useEffect(() => {
    if (active) s.markChatRead()
  }, [active, shown.length])

  // the reply timer for clients who chase you
  useEffect(() => {
    if (!chat?.client.chases || chat.client.case_status !== 'open') return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [chat?.client.chases, chat?.client.case_status])

  const evidence = s.evidence

  if (s.caseId == null) {
    return (
      <div className="app">
        <div className="app-body">
          <Notice>No case is open. Your client appears here once CaseDesk assigns you a case.</Notice>
        </div>
      </div>
    )
  }
  if (!chat) return <div className="app"><div className="app-body"><Spinner label="Connecting to the client..." /></div></div>

  const c = chat.client
  const open = c.case_status === 'open'
  const ratio = c.patience / Math.max(1, c.max_patience)
  const left = c.next_nag_in == null ? null : Math.max(0, Math.round(c.next_nag_in - (now - fetchedAt.current) / 1000))

  const send = async (text: string, evidenceId?: number) => {
    const t = text.trim()
    if (!t && evidenceId == null) return
    setPending(t || 'Shared a record from the evidence board')
    setDraft('')
    setShowPicker(false)
    await s.sendChat(t, evidenceId)
    setPending(null)
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(draft)
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send(draft)
    }
  }

  return (
    <div className="app messenger">
      <div className="chat-head">
        <div className="avatar">{initials(c.name)}</div>
        <div className="chat-who">
          <div className="chat-name">{c.name}</div>
          <div className="chat-role">{c.role} · reporting party</div>
        </div>
        <div className="chat-profile" title={c.summary}>
          <Badge color="var(--noise)">{c.label.toUpperCase()}</Badge>
          <div className="chat-summary">{c.summary}</div>
        </div>
      </div>
      <div className="mood-bar" title="The client's patience. Unclear messages, wrong evidence, wrong reports and long silences drain it.">
        <span className="mood-label">MOOD</span>
        <div className="mood-track">
          <div className="mood-fill" style={{ width: `${ratio * 100}%`, background: MOOD_COLOR[c.mood] }} />
        </div>
        <span className="mood-text" style={{ color: MOOD_COLOR[c.mood] }}>
          {c.mood.toUpperCase()} {c.patience}/{c.max_patience}
        </span>
        {open && c.chases && left != null && (
          <span className={`reply-timer${left < 20 ? ' urgent' : ''}`}>
            expects a reply in {Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
          </span>
        )}
        {!c.can_fire && <span className="dim small">won't drop the case on EASY</span>}
      </div>

      <div className="chat-list" ref={list} aria-live="polite">
        {shown.map((m) =>
          m.from === 'system' ? (
            <div key={m.id} className="chat-system">
              {m.text}
            </div>
          ) : (
            <div key={m.id} className={`bubble-row ${m.from === 'player' ? 'mine' : 'theirs'}`}>
              <div className={`bubble ${m.from === 'player' ? 'bubble-mine' : 'bubble-theirs'}`}>
                {m.evidence && <div className="bubble-evidence">shared: {m.evidence}</div>}
                <div className="bubble-text">{m.text}</div>
                {m.cards.length > 0 && (
                  <div className="bubble-cards">
                    <div className="bubble-handover">The client handed over {m.cards.length} record(s):</div>
                    {m.cards.map((r, i) => (
                      <RecordView key={i} rec={r} nav={nav} compact />
                    ))}
                  </div>
                )}
                <div className="bubble-time">{clock(m.at)}</div>
              </div>
            </div>
          ),
        )}
        {pending && (
          <div className="bubble-row mine">
            <div className="bubble bubble-mine bubble-pending">
              <div className="bubble-text">{pending}</div>
            </div>
          </div>
        )}
        {typing && (
          <div className="bubble-row theirs">
            <div className="bubble bubble-theirs typing" aria-label={`${c.name} is typing`}>
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        {!open && chat.secrets && (
          <div className="chat-debrief">
            <div className="eyebrow">WHAT THE CLIENT WAS HOLDING BACK</div>
            {chat.secrets.map((x) => (
              <div key={x.text} className={x.uncovered ? 'ok' : 'danger'}>
                {x.uncovered ? 'You found out: ' : 'You never found out: '}
                {x.text}
              </div>
            ))}
          </div>
        )}
      </div>

      {open ? (
        <>
          {s.brief?.difficulty === 'easy' && shown.filter((m) => m.from === 'player').length < 3 && (
            <div className="starters" data-tour="starters">
              {STARTERS.map((q) => (
                <button key={q} type="button" className="chip" onClick={() => void send(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}
          {showPicker && (
            <div className="evidence-picker">
              <div className="eyebrow">SHOW THE CLIENT A RECORD FROM YOUR EVIDENCE BOARD</div>
              {evidence.length === 0 ? (
                <div className="dim small">Your evidence board is empty. Pin records in your tools first.</div>
              ) : (
                evidence.map((e) => (
                  <button key={e.evidence_id} type="button" className="row" onClick={() => void send(draft, e.entity_id)}>
                    <span className="row-text">{e.label}</span>
                    <span className="row-right">{kindLabel(e.entity_kind)}</span>
                  </button>
                ))
              )}
            </div>
          )}
          <form className="chat-input" onSubmit={onSubmit} data-tour="chat-input">
            <button type="button" className={`btn${showPicker ? ' btn-primary' : ''}`} onClick={() => setShowPicker(!showPicker)}
              title="Show the client something you found">
              SHOW EVIDENCE
            </button>
            <textarea
              className="field"
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              placeholder={`Message ${c.name.split(' ')[0]}... (ask what happened, when, how they paid, what they're leaving out)`}
              aria-label="Message the client"
              maxLength={600}
            />
            <button type="submit" className="btn btn-primary" disabled={!!pending || !draft.trim()}>
              SEND
            </button>
          </form>
        </>
      ) : (
        <div className="chat-closed">This case is closed. The client is no longer answering.</div>
      )}
    </div>
  )
}
