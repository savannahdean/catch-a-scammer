// The first-case tutorial: a coach panel docked above the taskbar and a glowing
// ring around whatever the player should click next. Steps come from steps.ts;
// most tick themselves off by watching the Session (a pinned record, a sent
// message, an open window), so the player learns by doing. It is offered once
// to a player with no case, remembers its place across reloads, and can be
// replayed from the Start menu.
import { useEffect, useRef, useState } from 'react'
import { GlossaryText } from '../glossary/GlossaryText'
import { useSession } from '../state/session'
import { store } from '../state/storage'
import { STEPS, TRAINING_CASE, isTrainingCase } from './steps'
import type { TourAction, TourCtx } from './steps'

type Status = 'offer' | 'active' | 'off'

interface Saved {
  status: Status
  step: number
}

function load(hasCase: boolean): Saved {
  try {
    const v = JSON.parse(store.get('tutorial') ?? 'null') as Saved | null
    if (v && typeof v.step === 'number' && v.step < STEPS.length) return v
  } catch {
    /* nothing saved */
  }
  // first visit: offer it, unless this player already has a case going
  return { status: hasCase ? 'off' : 'offer', step: 0 }
}

interface Ring {
  left: number
  top: number
  width: number
  height: number
}

/** The first target that is actually on screen, clipped to its scrolling area. */
function findTarget(selectors: string[]): { el: Element; ring: Ring } | null {
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue // in a closed or minimized window
      const clip = el.parentElement?.closest('.app-body, .window')?.getBoundingClientRect()
      const left = Math.max(r.left, clip?.left ?? r.left)
      const top = Math.max(r.top, clip?.top ?? r.top)
      const right = Math.min(r.right, clip?.right ?? r.right)
      const bottom = Math.min(r.bottom, clip?.bottom ?? r.bottom)
      if (right - left < 4 || bottom - top < 4) {
        // scrolled out of view: worth pointing at once it is scrolled in
        return { el, ring: { left: r.left, top: r.top, width: 0, height: 0 } }
      }
      return { el, ring: { left, top, width: right - left, height: bottom - top } }
    }
  }
  return null
}

const sameRing = (a: Ring | null, b: Ring | null) =>
  a === b || (!!a && !!b && a.left === b.left && a.top === b.top && a.width === b.width && a.height === b.height)

const TASKBAR_GAP = 56

/** Where the panel can sit, in order of preference: bottom left (right of the icons), bottom right, top right, top left. */
const CORNERS = ['bl', 'br', 'tr', 'tl'] as const
type Corner = (typeof CORNERS)[number]

function cornerStyle(c: Corner, left: number) {
  return {
    left: c[1] === 'l' ? left : undefined,
    right: c[1] === 'r' ? 16 : undefined,
    top: c[0] === 't' ? 16 : undefined,
    bottom: c[0] === 'b' ? TASKBAR_GAP : undefined,
  }
}

/** The first corner where a panel of this size stays clear of the ring. */
function clearCorner(ring: Ring | null, w: number, h: number, left: number): Corner {
  if (!ring) return 'bl'
  const W = window.innerWidth
  const H = window.innerHeight
  for (const c of CORNERS) {
    const x = c[1] === 'l' ? left : W - 16 - w
    const y = c[0] === 't' ? 16 : H - TASKBAR_GAP - h
    const apart =
      x + w < ring.left - 8 || ring.left + ring.width + 8 < x || y + h < ring.top - 8 || ring.top + ring.height + 8 < y
    if (apart) return c
  }
  return 'bl'
}

interface Props {
  isOpen: (app: string) => boolean
  /** left edge of the free desktop, right of the icon columns */
  left: number
  /** bumped by the Start menu's TUTORIAL button */
  restart: number
}

export function Tutorial({ isOpen, left, restart }: Props) {
  const s = useSession()
  const [saved, setSaved] = useState<Saved>(() => load(s.caseId != null))
  const [collapsed, setCollapsed] = useState(false)
  const [cheer, setCheer] = useState(false)
  const [ring, setRing] = useState<Ring | null>(null)
  const [corner, setCorner] = useState<Corner>('bl')
  const panel = useRef<HTMLElement>(null)
  const scrolledFor = useRef('')

  const step = STEPS[saved.step]
  const active = saved.status === 'active'
  const ctx: TourCtx = { brief: s.brief, evidence: s.evidence, chat: s.chat, isOpen }

  useEffect(() => store.set('tutorial', JSON.stringify(saved)), [saved])

  useEffect(() => {
    if (restart > 0) {
      setSaved({ status: 'active', step: 1 })
      setCollapsed(false)
    }
  }, [restart])

  // tick off every step the player has already done
  useEffect(() => {
    if (!active) return
    let i = saved.step
    while (i < STEPS.length - 1 && STEPS[i].done?.(ctx)) i++
    if (i === saved.step) return
    setSaved({ status: 'active', step: i })
    setCheer(true)
    setCollapsed(false)
  })

  useEffect(() => {
    if (!cheer) return
    const t = window.setTimeout(() => setCheer(false), 2500)
    return () => window.clearTimeout(t)
  }, [cheer, saved.step])

  // keep the ring on the target as windows move, open, close and scroll
  useEffect(() => {
    if (!active || collapsed || !step.target) return setRing(null)
    const tick = () => {
      const found = findTarget(step.target!)
      if (found && scrolledFor.current !== step.id) {
        // once per step: bring its window to the front and its target into view
        scrolledFor.current = step.id
        const win = found.el.closest<HTMLElement>('[data-tour^="win-"]')?.dataset.tour?.slice(4)
        if (win) s.requestOpen(win)
        found.el.scrollIntoView({ block: 'center', behavior: 'smooth' })
      }
      const next = found && found.ring.width > 0 ? found.ring : null
      setRing((prev) => (sameRing(prev, next) ? prev : next))
      // move out of the way of what the player has to click
      const p = panel.current
      if (p) setCorner(clearCorner(next, p.offsetWidth, p.offsetHeight, left))
    }
    tick()
    const t = window.setInterval(tick, 300)
    return () => window.clearInterval(t)
  }, [active, collapsed, step.id, left])

  if (saved.status === 'off') return null

  const run = (a: TourAction) => {
    if (a.run === 'start-case') {
      s.requestOpen('casedesk')
      void s.startNewCase(TRAINING_CASE)
    } else s.requestOpen(a.run.app, a.run.query === 'entry-domain' ? s.brief?.entry_domain || undefined : undefined)
  }
  const go = (i: number) => setSaved({ status: 'active', step: Math.min(i, STEPS.length - 1) })
  const stop = () => {
    setSaved({ status: 'off', step: saved.step })
    if (saved.step < STEPS.length - 1) s.notify('Tutorial closed. Replay it any time from the Start menu.')
  }

  const last = saved.step === STEPS.length - 1
  const offCase = active && saved.step > 1 && !last && s.brief && !isTrainingCase(s.brief)

  if (collapsed)
    return (
      <button type="button" className="tour-pill" style={cornerStyle('bl', left)} onClick={() => setCollapsed(false)}>
        TUTORIAL · {saved.step} / {STEPS.length - 1}: {step.title}
      </button>
    )

  return (
    <>
      {ring && (
        <div
          className="tour-ring"
          aria-hidden="true"
          style={{ left: ring.left - 5, top: ring.top - 5, width: ring.width + 10, height: ring.height + 10 }}
        />
      )}
      <aside ref={panel} className="tour" data-corner={corner} style={cornerStyle(corner, left)} aria-label="Tutorial" aria-live="polite">
        <header className="tour-head">
          <span className="tour-eyebrow">
            {saved.status === 'offer' ? 'NEW HERE?' : `TUTORIAL · STEP ${saved.step} OF ${STEPS.length - 1}`}
          </span>
          {active && (
            <button type="button" className="tour-x" onClick={() => setCollapsed(true)} aria-label="Hide the tutorial" title="Hide">
              _
            </button>
          )}
          <button type="button" className="tour-x" onClick={stop} aria-label="Close the tutorial" title="Close">
            ×
          </button>
        </header>
        {active && (
          <div className="tour-progress">
            <div style={{ width: `${(saved.step / (STEPS.length - 1)) * 100}%` }} />
          </div>
        )}
        {cheer && <div className="tour-cheer">✓ Done. Next step:</div>}
        <h3 className="tour-title">{step.title}</h3>
        {offCase && (
          <div className="tour-warn">
            Your desk has a different case open. These steps are written for the training case.
          </div>
        )}
        {step
          .body(ctx)
          .split('\n\n')
          .map((p, i) => (
            <p key={i} className="tour-text">
              <GlossaryText text={p} />
            </p>
          ))}
        <div className="tour-actions">
          {saved.status === 'offer' ? (
            <>
              <button type="button" className="btn btn-primary" onClick={() => go(1)}>
                START THE TUTORIAL
              </button>
              <button type="button" className="btn" onClick={stop}>
                NO THANKS
              </button>
            </>
          ) : (
            <>
              {step.action && (
                <button type="button" className="btn btn-primary" disabled={s.busy} onClick={() => run(step.action!)}>
                  {step.action.label}
                </button>
              )}
              {last ? (
                <button type="button" className="btn btn-primary" onClick={() => setSaved({ status: 'off', step: 0 })}>
                  FINISH
                </button>
              ) : !step.done ? (
                <button type="button" className="btn btn-primary" onClick={() => go(saved.step + 1)}>
                  NEXT
                </button>
              ) : (
                <button type="button" className="link-btn tour-skip" onClick={() => go(saved.step + 1)}>
                  skip this step
                </button>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}
