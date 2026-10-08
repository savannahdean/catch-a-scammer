// The Session: the one piece of state every window shares.
//
// Windows never call each other. They read and change the Session, and when a
// window wants another tool opened ("look this domain up in IntelSearch") it
// calls requestOpen(), which the Desktop listens to. Everything the server
// knows (the case, the evidence board, the client chat) is refreshed from here.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError } from '../api/client'
import type { NewCaseOptions } from '../api/client'
import type { Brief, EvidenceItem, FetchAction, MessengerState, Pin, StudyStatus } from '../api/types'
import { store } from './storage'

export interface Toast {
  id: number
  text: string
  error: boolean
  from?: string
}

/** "Open this tool": with a search query, or with one record to load. */
export interface OpenRequest {
  app: string
  query?: string
  fetch?: FetchAction
}

interface SessionValue {
  online: boolean
  caseId: number | null
  brief: Brief | null
  evidence: EvidenceItem[]
  lastHint: string
  busy: boolean
  toasts: Toast[]
  notify: (text: string, error?: boolean, from?: string) => void
  dismiss: (id: number) => void

  startNewCase: (o: Omit<NewCaseOptions, 'participant_id'>) => Promise<boolean>
  refreshBrief: () => Promise<void>
  refreshEvidence: () => Promise<void>
  pin: (p: Pin) => Promise<void>
  unpin: (entityId: number) => Promise<void>
  isPinned: (entityId: number) => boolean
  requestHint: () => Promise<void>
  closeCase: () => void

  requestOpen: (app: string, query?: string, fetch?: FetchAction) => void
  setOpenListener: (fn: ((r: OpenRequest) => void) | null) => void
  setFocusedApp: (id: string | null) => void

  chat: MessengerState | null
  refreshChat: () => Promise<void>
  sendChat: (text: string, evidenceId?: number) => Promise<boolean>
  unread: number
  markChatRead: () => void

  participantId: string | null
  studyStatus: StudyStatus | null
  /** the server is taking new participants and answers (STUDY_ENABLED) */
  studyOpen: boolean
  joinStudy: (pid: string) => void
  leaveStudy: () => Promise<void>
  refreshStudy: () => Promise<void>
}

const SessionContext = createContext<SessionValue | null>(null)

export function useSession(): SessionValue {
  const s = useContext(SessionContext)
  if (!s) throw new Error('useSession() outside <SessionProvider>')
  return s
}

const CHAT_POLL_MS = 8000
const HEALTH_POLL_MS = 15000

export function SessionProvider({ children }: { children: ReactNode }) {
  const [online, setOnline] = useState(true)
  const [caseId, setCaseId] = useState<number | null>(() => store.getNumber('caseId'))
  const [brief, setBrief] = useState<Brief | null>(null)
  const [evidence, setEvidence] = useState<EvidenceItem[]>([])
  const [lastHint, setLastHint] = useState('')
  const [busy, setBusy] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [chat, setChat] = useState<MessengerState | null>(null)
  const [chatSeen, setChatSeen] = useState(0)
  const [participantId, setParticipantId] = useState<string | null>(() => store.get('participant'))
  const [studyStatus, setStudyStatus] = useState<StudyStatus | null>(null)
  const [studyOpen, setStudyOpen] = useState(false)

  const openListener = useRef<((r: OpenRequest) => void) | null>(null)
  const focusedApp = useRef<string | null>(null)
  const toastId = useRef(1)
  const notifiedUpTo = useRef(0)

  // ------------------------------------------------------------ toasts
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const notify = useCallback(
    (text: string, error = false, from?: string) => {
      const id = toastId.current++
      setToasts((t) => [...t.slice(-4), { id, text, error, from }])
      window.setTimeout(() => dismiss(id), error ? 7000 : 5000)
    },
    [dismiss],
  )

  const fail = useCallback(
    (e: unknown, what: string) => {
      if (e instanceof ApiError && e.status === 0) setOnline(false)
      notify(`${what}: ${e instanceof Error ? e.message : String(e)}`, true)
    },
    [notify],
  )

  // ------------------------------------------------------------ case
  const refreshBrief = useCallback(async () => {
    if (caseId == null) return
    try {
      setBrief(await api.brief(caseId))
      setOnline(true)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setCaseId(null)
        store.remove('caseId')
      } else fail(e, 'Could not load the case')
    }
  }, [caseId, fail])

  const refreshEvidence = useCallback(async () => {
    if (caseId == null) return
    try {
      setEvidence((await api.evidence(caseId)).items)
    } catch (e) {
      fail(e, 'Could not load the evidence board')
    }
  }, [caseId, fail])

  const startNewCase = useCallback(
    async (o: Omit<NewCaseOptions, 'participant_id'>) => {
      setBusy(true)
      try {
        const b = await api.newCase({ ...o, participant_id: participantId })
        setBrief(b)
        setCaseId(b.case_id)
        store.setNumber('caseId', b.case_id)
        setEvidence([])
        setLastHint('')
        setChat(null)
        setChatSeen(0)
        notifiedUpTo.current = 0
        setOnline(true)
        notify(`Case ${b.case_code} assigned. Your client is waiting in the Messenger.`)
        return true
      } catch (e) {
        fail(e, 'Could not open a new case')
        return false
      } finally {
        setBusy(false)
      }
    },
    [participantId, notify, fail],
  )

  const closeCase = useCallback(() => {
    setCaseId(null)
    setBrief(null)
    setEvidence([])
    setChat(null)
    store.remove('caseId')
  }, [])

  const pin = useCallback(
    async (p: Pin) => {
      if (caseId == null) return
      try {
        setEvidence((await api.pin(caseId, p.entity_kind, p.entity_id)).items)
        notify(`Added to evidence: ${p.label}`)
        // the client may have something to say about it
        window.setTimeout(() => void refreshChatRef.current(), 400)
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) notify(e.message === 'case is closed' ? 'This case is closed.' : e.message, true)
        else fail(e, 'Could not pin that')
      }
    },
    [caseId, notify, fail],
  )

  const unpin = useCallback(
    async (entityId: number) => {
      if (caseId == null) return
      try {
        setEvidence((await api.unpin(caseId, entityId)).items)
      } catch (e) {
        fail(e, 'Could not unpin that')
      }
    },
    [caseId, fail],
  )

  const pinnedIds = useMemo(() => new Set(evidence.map((e) => e.entity_id)), [evidence])
  const isPinned = useCallback((id: number) => pinnedIds.has(id), [pinnedIds])

  const requestHint = useCallback(async () => {
    if (caseId == null) return
    try {
      const h = await api.hint(caseId)
      setLastHint(h.body)
      notify(`Hint used: -${h.penalty_applied} points when you submit.`)
      await refreshBrief()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) notify('No hints left on this difficulty.', true)
      else fail(e, 'Hint service unavailable')
    }
  }, [caseId, notify, fail, refreshBrief])

  // ------------------------------------------------------------ windows
  const requestOpen = useCallback((app: string, query?: string, fetch?: FetchAction) => {
    openListener.current?.({ app, query, fetch })
  }, [])
  const setOpenListener = useCallback((fn: ((r: OpenRequest) => void) | null) => {
    openListener.current = fn
  }, [])
  const setFocusedApp = useCallback((id: string | null) => {
    focusedApp.current = id
  }, [])

  // ------------------------------------------------------------ messenger
  const absorbChat = useCallback(
    (st: MessengerState) => {
      setChat(st)
      const fresh = st.messages.filter((m) => m.from !== 'player' && m.id > notifiedUpTo.current)
      if (notifiedUpTo.current > 0 && focusedApp.current !== 'messenger') {
        for (const m of fresh.slice(-3)) {
          notify(m.text.length > 140 ? m.text.slice(0, 137) + '...' : m.text, m.from === 'system', m.from === 'client' ? st.client.name : 'Messenger')
        }
      }
      const top = st.messages.length ? st.messages[st.messages.length - 1].id : 0
      notifiedUpTo.current = Math.max(notifiedUpTo.current, top)
      if (focusedApp.current === 'messenger') setChatSeen(top)
      if (st.client.case_status !== 'open' && brief && brief.status === 'open') void refreshBrief()
    },
    [notify, brief, refreshBrief],
  )

  const refreshChat = useCallback(async () => {
    if (caseId == null) return
    try {
      absorbChat(await api.messenger(caseId))
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 404)) setOnline(!(e instanceof ApiError && e.status === 0))
    }
  }, [caseId, absorbChat])
  const refreshChatRef = useRef(refreshChat)
  refreshChatRef.current = refreshChat

  const sendChat = useCallback(
    async (text: string, evidenceId?: number) => {
      if (caseId == null) return false
      try {
        absorbChat(await api.sendMessage(caseId, text, evidenceId))
        return true
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) notify(e.message, true)
        else fail(e, 'Message not sent')
        return false
      }
    },
    [caseId, absorbChat, notify, fail],
  )

  const unread = useMemo(() => {
    if (!chat) return 0
    return chat.messages.filter((m) => m.from === 'client' && m.id > chatSeen).length
  }, [chat, chatSeen])

  const markChatRead = useCallback(() => {
    if (!chat || !chat.messages.length) return
    const top = chat.messages[chat.messages.length - 1].id
    setChatSeen(top)
    if (caseId != null) store.setNumber(`chatSeen.${caseId}`, top)
  }, [chat, caseId])

  // ------------------------------------------------------------ study
  const refreshStudy = useCallback(async () => {
    if (!participantId) return setStudyStatus(null)
    try {
      setStudyStatus(await api.study.status(participantId))
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setParticipantId(null)
        store.remove('participant')
      }
    }
  }, [participantId])

  const joinStudy = useCallback((pid: string) => {
    setParticipantId(pid)
    store.set('participant', pid)
  }, [])

  const leaveStudy = useCallback(async () => {
    if (participantId) {
      try {
        await api.study.withdraw(participantId)
      } catch (e) {
        fail(e, 'Could not withdraw')
        return
      }
    }
    setParticipantId(null)
    setStudyStatus(null)
    store.remove('participant')
    notify('You have left the study. Your survey answers were deleted.')
  }, [participantId, fail, notify])

  // ------------------------------------------------------------ effects
  useEffect(() => {
    if (caseId == null) return
    setChatSeen(store.getNumber(`chatSeen.${caseId}`) ?? 0)
    void refreshBrief()
    void refreshEvidence()
    void refreshChat()
  }, [caseId]) // a new case id: load everything once

  useEffect(() => {
    if (caseId == null || !brief || brief.status !== 'open') return
    const t = window.setInterval(() => void refreshChatRef.current(), CHAT_POLL_MS)
    return () => window.clearInterval(t)
  }, [caseId, brief])

  useEffect(() => {
    const ping = async () => {
      try {
        await api.health()
        setOnline(true)
      } catch {
        setOnline(false)
      }
    }
    void ping()
    const t = window.setInterval(ping, HEALTH_POLL_MS)
    return () => window.clearInterval(t)
  }, [])

  useEffect(() => {
    void refreshStudy()
  }, [refreshStudy])

  // a closed study hides the opt-in and the surveys
  useEffect(() => {
    api.study
      .config()
      .then((c) => setStudyOpen(c.enabled))
      .catch(() => setStudyOpen(false))
  }, [online])

  const value: SessionValue = {
    online,
    caseId,
    brief,
    evidence,
    lastHint,
    busy,
    toasts,
    notify,
    dismiss,
    startNewCase,
    refreshBrief,
    refreshEvidence,
    pin,
    unpin,
    isPinned,
    requestHint,
    closeCase,
    requestOpen,
    setOpenListener,
    setFocusedApp,
    chat,
    refreshChat,
    sendChat,
    unread,
    markChatRead,
    participantId,
    studyStatus,
    studyOpen,
    joinStudy,
    leaveStudy,
    refreshStudy,
  }
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
