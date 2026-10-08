// One window frame: title bar (drag to move), minimize / maximize / close, and a
// resize grip. The app inside stays mounted while the window is minimized or
// closed, so its search text and results survive, like a real desktop program.
import { useRef } from 'react'
import type { PointerEvent, ReactNode } from 'react'
import type { AppDef } from '../apps/types'

export interface WinState {
  open: boolean
  minimized: boolean
  maximized: boolean
  mounted: boolean
  x: number
  y: number
  w: number
  h: number
}

interface Props {
  def: AppDef
  win: WinState
  z: number
  active: boolean
  badge?: number
  onFocus: () => void
  onClose: () => void
  onMinimize: () => void
  onToggleMax: () => void
  onChange: (patch: Partial<WinState>) => void
  children: ReactNode
}

const MIN_W = 420
const MIN_H = 300

export function Window({ def, win, z, active, badge, onFocus, onClose, onMinimize, onToggleMax, onChange, children }: Props) {
  const grab = useRef<{ mode: 'move' | 'size'; dx: number; dy: number } | null>(null)

  const start = (mode: 'move' | 'size') => (e: PointerEvent) => {
    if (win.maximized && mode === 'move') return
    if ((e.target as HTMLElement).closest('button')) return
    e.preventDefault()
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    onFocus()
    grab.current = mode === 'move' ? { mode, dx: e.clientX - win.x, dy: e.clientY - win.y } : { mode, dx: e.clientX - win.w, dy: e.clientY - win.h }
  }
  const move = (e: PointerEvent) => {
    const g = grab.current
    if (!g) return
    if (g.mode === 'move') {
      const x = Math.min(Math.max(e.clientX - g.dx, -win.w + 120), window.innerWidth - 120)
      const y = Math.min(Math.max(e.clientY - g.dy, 0), window.innerHeight - 90)
      onChange({ x, y })
    } else {
      onChange({ w: Math.max(MIN_W, e.clientX - g.dx), h: Math.max(MIN_H, e.clientY - g.dy) })
    }
  }
  const end = () => {
    grab.current = null
  }

  const style = win.maximized
    ? { left: 0, top: 0, width: '100%', height: '100%', zIndex: z }
    : { left: win.x, top: win.y, width: win.w, height: win.h, zIndex: z }

  return (
    <section
      className={`window${active ? ' active' : ''}`}
      style={{ ...style, display: win.open && !win.minimized ? 'flex' : 'none' }}
      onPointerDownCapture={onFocus}
      aria-label={def.title}
      data-tour={`win-${def.id}`}
    >
      <header className="titlebar" onPointerDown={start('move')} onPointerMove={move} onPointerUp={end} onDoubleClick={onToggleMax}>
        <span className="title-dot" style={{ background: def.accent }} />
        <span className="title-text">{def.title}</span>
        {badge ? <span className="title-badge">{badge}</span> : null}
        <span className="title-buttons">
          <button type="button" className="tb-btn" onClick={onMinimize} aria-label="Minimize" title="Minimize">
            _
          </button>
          <button type="button" className="tb-btn" onClick={onToggleMax} aria-label="Maximize" title={win.maximized ? 'Restore' : 'Maximize'}>
            {win.maximized ? '❐' : '□'}
          </button>
          <button type="button" className="tb-btn tb-close" onClick={onClose} aria-label="Close" title="Close">
            ×
          </button>
        </span>
      </header>
      <div className="window-body">{children}</div>
      {!win.maximized && (
        <div className="grip" onPointerDown={start('size')} onPointerMove={move} onPointerUp={end} aria-hidden="true" />
      )}
    </section>
  )
}
