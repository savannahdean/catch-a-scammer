// The fake operating system: wallpaper, desktop icons, the windows, the taskbar,
// the Start menu, toasts, the Field Manual, the tutorial and the Dictionary
// tooltip. It owns window positions and z-order, and it is the only thing that
// opens windows: apps ask through session.requestOpen(), which lands in
// openApp() below.
import { useCallback, useEffect, useRef, useState } from 'react'
import { APPS } from '../apps/registry'
import type { OpenSignal } from '../apps/types'
import { useSession } from '../state/session'
import type { OpenRequest } from '../state/session'
import { GlossaryTooltip } from '../glossary/GlossaryTooltip'
import { brand } from '../theme'
import { Tutorial } from '../tutorial/Tutorial'
import { FieldManual } from './FieldManual'
import { StartMenu } from './StartMenu'
import { Taskbar } from './Taskbar'
import { Toasts } from './Toasts'
import { Window } from './Window'
import type { WinState } from './Window'

const TASKBAR_H = 44

/** Where the free desktop starts, right of the icon columns. */
function iconsRight() {
  const iconRows = Math.max(1, Math.floor((window.innerHeight - TASKBAR_H - 24) / 90))
  return 16 + Math.ceil(APPS.length / iconRows) * 92
}

function initialWins(): Record<string, WinState> {
  const out: Record<string, WinState> = {}
  const W = window.innerWidth
  const H = window.innerHeight - TASKBAR_H
  // windows cascade to the right of the icon columns; the Messenger sits on the right edge
  const left = iconsRight()
  APPS.forEach((a, i) => {
    const w = Math.min(a.size[0], W - 40)
    const h = Math.min(a.size[1], H - 30)
    let x = Math.min(left + (i % 8) * 34, Math.max(0, W - w - 10))
    let y = Math.min(16 + (i % 8) * 26, Math.max(0, H - h - 10))
    if (a.id === 'messenger') {
      x = Math.max(0, W - w - 16)
      y = 16
    }
    out[a.id] = { open: false, minimized: false, maximized: false, mounted: false, x, y, w, h }
  })
  return out
}

export function Desktop() {
  const s = useSession()
  const [wins, setWins] = useState<Record<string, WinState>>(initialWins)
  const [order, setOrder] = useState<string[]>([])
  const [signals, setSignals] = useState<Record<string, OpenSignal>>({})
  const [startOpen, setStartOpen] = useState(false)
  const [manual, setManual] = useState(false)
  const [tourRestart, setTourRestart] = useState(0)
  const nonce = useRef(1)

  const visibleTop = [...order].reverse().find((id) => wins[id]?.open && !wins[id]?.minimized) ?? null

  const raise = useCallback((id: string) => {
    setOrder((o) => [...o.filter((x) => x !== id), id])
  }, [])

  const patch = useCallback((id: string, p: Partial<WinState>) => {
    setWins((w) => ({ ...w, [id]: { ...w[id], ...p } }))
  }, [])

  const openApp = useCallback(
    (id: string, req?: Omit<OpenRequest, 'app'>) => {
      const def = APPS.find((a) => a.id === id)
      if (!def) return
      if (def.requiresCase && s.caseId == null) {
        s.notify('Open a case in CaseDesk first.', true)
        id = 'casedesk'
      }
      patch(id, { open: true, minimized: false, mounted: true })
      raise(id)
      setSignals((sg) => ({ ...sg, [id]: { nonce: nonce.current++, query: req?.query, fetch: req?.fetch } }))
      setStartOpen(false)
      setManual(false)
    },
    [s, patch, raise],
  )

  // apps ask for windows through the session
  useEffect(() => {
    s.setOpenListener((r) => openApp(r.app, r))
    return () => s.setOpenListener(null)
  }, [s, openApp])

  // the session needs to know whether the Messenger is in front (to mark messages read)
  useEffect(() => {
    s.setFocusedApp(visibleTop)
  }, [s, visibleTop])

  // first boot: CaseDesk, plus the Messenger if a case is already running
  useEffect(() => {
    openApp('casedesk')
    if (s.caseId != null) openApp('messenger')
  }, []) // once

  // a new case: bring up the client
  const lastCase = useRef(s.caseId)
  useEffect(() => {
    if (s.caseId != null && s.caseId !== lastCase.current) openApp('messenger')
    lastCase.current = s.caseId
  }, [s.caseId, openApp])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'F1') {
        e.preventDefault()
        setManual((m) => !m)
      } else if (e.key === 'F2') {
        e.preventDefault()
        openApp('glossary')
      } else if (e.key === 'Escape') {
        setManual(false)
        setStartOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openApp])

  const openTerm = useCallback((id: string) => openApp('glossary', { query: id }), [openApp])

  const taskButton = (id: string) => {
    const w = wins[id]
    if (!w.open) return openApp(id)
    if (id === visibleTop) patch(id, { minimized: true })
    else {
      patch(id, { minimized: false })
      raise(id)
    }
  }

  return (
    <div className="desktop">
      <div className="wallpaper" aria-hidden="true">
        <div className="radar" />
        <div className="watermark">
          <div>
            {brand.OS_NAME} {brand.OS_VERSION}
          </div>
          <div className="watermark-sub">{brand.AGENCY}</div>
        </div>
      </div>

      <div className="desk-area" onPointerDown={() => setStartOpen(false)}>
        <nav className="icons" aria-label="Applications">
          {APPS.map((a) => (
            <button key={a.id} type="button" className="icon" onClick={() => openApp(a.id)} title={a.title} data-tour={`icon-${a.id}`}>
              <span className="icon-tile" style={{ borderColor: a.accent }}>
                <span className="icon-cap" style={{ background: a.accent }} />
                <span className="icon-glyph">{a.glyph}</span>
                {a.id === 'messenger' && s.unread > 0 && <span className="icon-badge">{s.unread}</span>}
              </span>
              <span className="icon-label">{a.short}</span>
            </button>
          ))}
        </nav>

        {APPS.filter((a) => wins[a.id].mounted).map((a) => (
          <Window
            key={a.id}
            def={a}
            win={wins[a.id]}
            z={10 + order.indexOf(a.id)}
            active={a.id === visibleTop}
            badge={a.id === 'messenger' ? s.unread : undefined}
            onFocus={() => visibleTop !== a.id && raise(a.id)}
            onClose={() => patch(a.id, { open: false })}
            onMinimize={() => patch(a.id, { minimized: true })}
            onToggleMax={() => patch(a.id, { maximized: !wins[a.id].maximized })}
            onChange={(p) => patch(a.id, p)}
          >
            {a.render({ signal: signals[a.id] ?? null, active: a.id === visibleTop })}
          </Window>
        ))}
      </div>

      {startOpen && (
        <StartMenu
          onOpen={openApp}
          onManual={() => { setManual(true); setStartOpen(false) }}
          onTutorial={() => { setTourRestart((n) => n + 1); setStartOpen(false) }}
          onClose={() => setStartOpen(false)}
        />
      )}
      <Toasts />
      <Taskbar wins={wins} top={visibleTop} startOpen={startOpen} onStart={() => setStartOpen(!startOpen)} onButton={taskButton} />
      {manual && <FieldManual onClose={() => setManual(false)} />}
      <Tutorial isOpen={(id) => !!wins[id]?.open && !wins[id]?.minimized} left={iconsRight()} restart={tourRestart} />
      <GlossaryTooltip onOpen={openTerm} />
    </div>
  )
}
