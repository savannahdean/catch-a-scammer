// Underlines every Dictionary word in a piece of text. Each underlined word is
// a `.gloss` button carrying its term id; the Desktop shows the hover tooltip
// and opens the Dictionary on click (see GlossaryTooltip), so this component
// has no handlers and works anywhere.
import type { ReactNode } from 'react'
import { findTerms } from './match'

export function GlossaryText({ text, exclude }: { text: string; exclude?: string }) {
  const out: ReactNode[] = []
  let last = 0
  for (const h of findTerms(text, exclude)) {
    if (h.start > last) out.push(text.slice(last, h.start))
    out.push(
      <button key={h.start} type="button" className="gloss" data-term={h.id}>
        {text.slice(h.start, h.end)}
      </button>,
    )
    last = h.end
  }
  if (last < text.length) out.push(text.slice(last))
  return <>{out}</>
}
