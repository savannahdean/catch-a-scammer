// One tooltip for every underlined Dictionary word on the desktop. It listens
// at the window, so the words themselves need no handlers: hover or focus one
// to read its short meaning, click it to open the Dictionary on that entry.
import { useEffect, useState } from 'react'
import { TERM_BY_ID } from './terms'

interface Tip {
  id: string
  x: number
  y: number
  above: boolean
}

const glossAt = (t: EventTarget | null) => (t instanceof Element ? t.closest<HTMLElement>('.gloss[data-term]') : null)

export function GlossaryTooltip({ onOpen }: { onOpen: (termId: string) => void }) {
  const [tip, setTip] = useState<Tip | null>(null)

  useEffect(() => {
    const show = (e: Event) => {
      const el = glossAt(e.target)
      if (!el) return
      const r = el.getBoundingClientRect()
      const above = r.bottom + 120 > window.innerHeight
      setTip({ id: el.dataset.term!, x: Math.min(r.left, window.innerWidth - 340), y: above ? r.top - 6 : r.bottom + 6, above })
    }
    const hide = (e: Event) => {
      if (glossAt(e.target)) setTip(null)
    }
    // capture: some windows and overlays stop clicks from bubbling
    const click = (e: MouseEvent) => {
      const el = glossAt(e.target)
      if (!el) return
      e.preventDefault()
      e.stopPropagation()
      setTip(null)
      onOpen(el.dataset.term!)
    }
    window.addEventListener('mouseover', show)
    window.addEventListener('mouseout', hide)
    window.addEventListener('focusin', show)
    window.addEventListener('focusout', hide)
    window.addEventListener('click', click, true)
    return () => {
      window.removeEventListener('mouseover', show)
      window.removeEventListener('mouseout', hide)
      window.removeEventListener('focusin', show)
      window.removeEventListener('focusout', hide)
      window.removeEventListener('click', click, true)
    }
  }, [onOpen])

  const term = tip && TERM_BY_ID[tip.id]
  if (!tip || !term) return null
  return (
    <div
      className="gloss-tip"
      role="tooltip"
      style={{ left: Math.max(8, tip.x), top: tip.y, transform: tip.above ? 'translateY(-100%)' : undefined }}
    >
      <div className="gloss-tip-term">{term.term}</div>
      <div>{term.short}</div>
      <div className="gloss-tip-more">Click for more in the Dictionary</div>
    </div>
  )
}
