// The Dictionary: every technical word in the game, in plain English, grouped
// by topic. Clicking an underlined word anywhere opens this window on that
// entry (the signal's query is the term id); typing searches names and meanings.
import { useEffect, useRef, useState } from 'react'
import { GlossaryText } from '../glossary/GlossaryText'
import { CATEGORY_LABEL, TERM_BY_ID, TERMS } from '../glossary/terms'
import type { Term, TermCategory } from '../glossary/terms'
import { useSession } from '../state/session'
import { Notice } from '../ui/widgets'
import { LOOKUP_TOOLS } from './lookupTools'
import type { AppProps } from './types'

const CATEGORIES = Object.keys(CATEGORY_LABEL) as TermCategory[]
const byName = (a: Term, b: Term) => a.term.localeCompare(b.term)

/** Name matches first, then matches anywhere in the meaning. */
function search(q: string): Term[] {
  const needle = q.trim().toLowerCase()
  const named = (t: Term) => [t.term, ...(t.also ?? [])].some((s) => s.toLowerCase().includes(needle))
  const meant = (t: Term) => `${t.short} ${t.more ?? ''}`.toLowerCase().includes(needle)
  return [...TERMS.filter(named).sort(byName), ...TERMS.filter((t) => !named(t) && meant(t)).sort(byName)]
}

function Entry({ t, focused, onSee }: { t: Term; focused: boolean; onSee: (id: string) => void }) {
  const s = useSession()
  const tool = t.tool && LOOKUP_TOOLS.find((x) => x.id === t.tool)
  return (
    <article className={`gloss-entry${focused ? ' gloss-entry-focus' : ''}`} data-entry={t.id}>
      <h3 className="gloss-name">{t.term}</h3>
      <p className="gloss-short">
        <GlossaryText text={t.short} exclude={t.id} />
      </p>
      {t.more && (
        <p className="gloss-more">
          <GlossaryText text={t.more} exclude={t.id} />
        </p>
      )}
      {(tool || t.see?.length) && (
        <div className="gloss-actions">
          {tool && (
            <button type="button" className="btn btn-small" onClick={() => s.requestOpen(tool.id)}>
              OPEN {tool.short.toUpperCase()}
            </button>
          )}
          {t.see?.length ? <span className="dim small">See also:</span> : null}
          {t.see?.map((id) => (
            <button key={id} type="button" className="link-btn" onClick={() => onSee(id)}>
              {TERM_BY_ID[id]?.term ?? id}
            </button>
          ))}
        </div>
      )}
    </article>
  )
}

export function Glossary({ signal }: AppProps) {
  const [query, setQuery] = useState('')
  const [cat, setCat] = useState<TermCategory | 'all'>('all')
  const [focus, setFocus] = useState<string | null>(null)
  const body = useRef<HTMLDivElement>(null)

  const show = (id: string) => {
    if (!TERM_BY_ID[id]) return
    setQuery('')
    setCat('all')
    setFocus(id)
  }

  // an underlined word somewhere was clicked
  useEffect(() => {
    if (signal?.query) show(signal.query)
  }, [signal?.nonce]) // only when a new request arrives

  useEffect(() => {
    if (focus) body.current?.querySelector(`[data-entry="${focus}"]`)?.scrollIntoView({ block: 'start' })
  }, [focus, signal?.nonce])

  const entry = (t: Term) => <Entry key={t.id} t={t} focused={t.id === focus} onSee={show} />
  const searching = query.trim() !== ''
  const results = searching ? search(query).filter((t) => cat === 'all' || t.cat === cat) : []

  return (
    <div className="app glossary">
      <div className="query-bar">
        <input
          className="field"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setFocus(null)
          }}
          placeholder="Look up a word, e.g. DNS, sinkhole, money mule"
          aria-label="Search the Dictionary"
          spellCheck={false}
        />
        <select
          className="field gloss-filter"
          value={cat}
          onChange={(e) => {
            setCat(e.target.value as TermCategory | 'all')
            setFocus(null)
          }}
          aria-label="Topic"
        >
          <option value="all">All topics</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c]}
            </option>
          ))}
        </select>
      </div>
      <div className="app-body" ref={body}>
        {searching ? (
          results.length ? results.map(entry) : <Notice>No word matches "{query.trim()}". Try a shorter search.</Notice>
        ) : (
          <>
            <p className="dim gloss-intro">
              Every technical word in {TERMS.length} plain-English entries. Words with a dotted underline anywhere on
              the desktop are in here: hover one for a quick meaning, click it to jump to its entry.
            </p>
            {CATEGORIES.filter((c) => cat === 'all' || c === cat).map((c) => (
              <section key={c}>
                <h4 className="gloss-topic">{CATEGORY_LABEL[c]}</h4>
                {TERMS.filter((t) => t.cat === c).sort(byName).map(entry)}
              </section>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
