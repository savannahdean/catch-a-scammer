// Finds the Dictionary words in a piece of text, kept free of React so the
// matching rules can be tested on their own.
import { TERMS } from './terms'

export interface TermHit {
  start: number
  end: number
  id: string
}

interface Spelling {
  text: string
  id: string
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+')

/** One regex over many spellings, longest first so "passive DNS" wins over "DNS". */
function matcher(spellings: Spelling[], flags: string) {
  const sorted = [...spellings].sort((a, b) => b.text.length - a.text.length)
  // Not inside a longer word, a domain, an email or a file name ("dns-check.example"
  // has no DNS in it), with an optional plural ending.
  const re = new RegExp(
    `(?<![\\w@./-])(?:${sorted.map((s) => `(${escape(s.text)})`).join('|')})(?:e?s)?(?![\\w@])(?![./-]\\w)`,
    flags,
  )
  return (text: string): TermHit[] =>
    [...text.matchAll(re)].map((m) => ({
      start: m.index,
      end: m.index + m[0].length,
      id: sorted[m.findIndex((g, k) => k > 0 && g !== undefined) - 1].id,
    }))
}

// Acronyms, and any spelling in `also` with a capital letter, only match that
// exact case ("SAN" never matches "San Jose"); everything else ignores case.
const acronym = (s: string) => /[A-Z]{2}/.test(s) && !/[a-z]/.test(s)
const all = TERMS.flatMap((t) => [
  ...(t.match
    ? t.match.map((text) => ({ text, id: t.id, exact: true }))
    : [t.term, ...(t.also ?? [])].map((text, i) => ({ text, id: t.id, exact: acronym(text) || (i > 0 && /[A-Z]/.test(text)) }))),
  // a `not` phrase wins over the shorter word inside it, and is never underlined
  ...(t.not ?? []).map((text) => ({ text, id: '', exact: false })),
])
const exactCase = matcher(all.filter((s) => s.exact), 'g')
const anyCase = matcher(all.filter((s) => !s.exact), 'gi')

/** Every Dictionary word in the text, each term once (its first appearance). */
export function findTerms(text: string, exclude?: string): TermHit[] {
  const hits = [...exactCase(text), ...anyCase(text)].sort((a, b) => a.start - b.start || b.end - a.end)
  const seen = new Set<string>(exclude ? [exclude] : [])
  const out: TermHit[] = []
  let taken = 0
  for (const h of hits) {
    if (h.start < taken) continue // overlaps a longer word already underlined
    taken = h.end
    if (!h.id || seen.has(h.id)) continue
    seen.add(h.id)
    out.push(h)
  }
  return out
}
