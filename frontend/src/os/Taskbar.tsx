// The bar along the bottom: Start, one button per open window, and on the
// right the client's mood, the case number, the server connection and a clock.
import { useEffect, useState } from 'react'
import { APPS } from '../apps/registry'
import { useSession } from '../state/session'
import { MOOD_COLOR, brand } from '../theme'
import type { WinState } from './Window'

interface Props {
  wins: Record<string, WinState>
  top: string | null
  startOpen: boolean
  onStart: () => void
  onButton: (id: string) => void
}

export function Taskbar({ wins, top, startOpen, onStart, onButton }: Props) {
  const s = useSession()
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 15000)
    return () => window.clearInterval(t)
  }, [])

  const mood = s.chat?.client
  return (
    <footer className="taskbar">
      <button type="button" className={`start-btn${startOpen ? ' open' : ''}`} onClick={onStart} aria-expanded={startOpen}>
        {brand.OS_NAME}
      </button>
      <div className="task-buttons">
        {APPS.filter((a) => wins[a.id]?.open).map((a) => {
          const w = wins[a.id]
          const isTop = a.id === top && !w.minimized
          const badge = a.id === 'messenger' ? s.unread : 0
          return (
            <button key={a.id} type="button" className={`task-btn${isTop ? ' active' : ''}`} onClick={() => onButton(a.id)}
              style={{ borderBottomColor: a.accent }} title={a.title}>
              <span className="task-label">{a.short}</span>
              {badge > 0 && <span className="task-badge">{badge}</span>}
            </button>
          )
        })}
      </div>
      <div className="tray">
        {mood && mood.case_status === 'open' && (
          <button type="button" className="tray-mood" onClick={() => onButton('messenger')} title={`${mood.name} is ${mood.mood}`}>
            <span className="dot" style={{ background: MOOD_COLOR[mood.mood] }} />
            client {mood.mood}
            {s.unread > 0 && <span className="task-badge">{s.unread}</span>}
          </button>
        )}
        <span className="tray-case mono">{s.brief ? `CASE #${s.brief.case_code}` : 'NO CASE'}</span>
        <span className="tray-net">
          <span className="dot" style={{ background: s.online ? 'var(--ok)' : 'var(--danger)' }} />
          {s.online ? 'connected' : 'offline'}
        </span>
        <span className="tray-clock">
          <span>{now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
          <span className="tray-date">{now.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })}</span>
        </span>
      </div>
    </footer>
  )
}
