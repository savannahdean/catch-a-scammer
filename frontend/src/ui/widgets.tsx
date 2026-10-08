// Small building blocks every window uses.
import type { ReactNode } from 'react'
import { GlossaryText } from '../glossary/GlossaryText'

/** Plain-text labels get their Dictionary words underlined. */
const gloss = (n: ReactNode) => (typeof n === 'string' ? <GlossaryText text={n} /> : n)

export function Badge({ children, color }: { children: ReactNode; color: string }) {
  return (
    <span className="badge" style={{ background: color }}>
      {children}
    </span>
  )
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="section-label">{gloss(children)}</div>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status" aria-live="polite">
      <span className="spinner" />
      {label && <span className="spinner-label">{label}</span>}
    </div>
  )
}

/** A yellow notice panel: empty results, errors, "open a case first". */
export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'error' }) {
  return <div className={`notice notice-${tone}`}>{children}</div>
}

/** A 0..1 bar coloured green -> amber -> red, with labels under each end. */
export function Meter({ value, low, high }: { value: number; low: string; high: string }) {
  const v = Math.max(0, Math.min(1, value))
  const color = v >= 0.6 ? 'var(--danger)' : v >= 0.35 ? 'var(--warn)' : 'var(--ok)'
  return (
    <div className="meter">
      <div className="meter-row">
        <div className="meter-track">
          <div className="meter-fill" style={{ width: `${v * 100}%`, background: color }} />
        </div>
        <span className="meter-value" style={{ color }}>
          {v.toFixed(2)}
        </span>
      </div>
      <div className="meter-ends">
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </div>
  )
}

/** A clickable list row: text on the left, the action label on the right. */
export function ActionRow({
  text,
  right,
  color,
  onClick,
  title,
}: {
  text: string
  right: string
  color?: string
  onClick?: () => void
  title?: string
}) {
  const clickable = !!onClick
  return (
    <button
      type="button"
      className={`row${clickable ? '' : ' row-static'}`}
      onClick={onClick}
      disabled={!clickable}
      title={title ?? text}
    >
      <span className="row-text" style={{ color: color ?? 'var(--text)' }}>
        {text}
      </span>
      {right && <span className="row-right">{right}</span>}
    </button>
  )
}

export function KeyValue({ k, v, color }: { k: string; v: ReactNode; color?: string }) {
  return (
    <div className="kv">
      <span className="kv-key">{gloss(k)}</span>
      <span className="kv-value" style={color ? { color } : undefined}>
        {v}
      </span>
    </div>
  )
}
