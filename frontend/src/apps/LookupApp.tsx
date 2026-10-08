// One search tool window: a query bar over a scrolling list of records.
// Each of the 18 tools in lookupTools.ts is this component with a different
// API route. A link to a record that belongs to this tool loads here (with a
// BACK button); a link to another tool opens that tool.
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { AnyRecord, Envelope, FetchAction } from '../api/types'
import { GlossaryText } from '../glossary/GlossaryText'
import { EnvelopeView, RecordView } from '../records/RecordView'
import type { RecordNav } from '../records/RecordView'
import { useSession } from '../state/session'
import { Notice, Spinner } from '../ui/widgets'
import type { LookupTool } from './lookupTools'
import type { AppProps } from './types'

type Result = { env: Envelope } | { rec: AnyRecord } | null

function asResult(data: unknown): Result {
  const d = data as Record<string, unknown>
  if (d && 'query' in d) return { env: d as unknown as Envelope }
  if (d && ('card' in d || 'kind' in d)) return { rec: d as unknown as AnyRecord }
  return null
}

export function LookupApp({ tool, signal }: AppProps & { tool: LookupTool }) {
  const s = useSession()
  const [text, setText] = useState('')
  const [result, setResult] = useState<Result>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState('')
  const [history, setHistory] = useState<Result[]>([])
  const body = useRef<HTMLDivElement>(null)
  const caseId = s.caseId

  const failed = (e: unknown) => {
    setResult(null)
    if (e instanceof ApiError && e.status === 404)
      setError('NO RECORDS FOUND.\n\nThat identifier is not indexed for this case. Take the term from a record you already hold.')
    else setError(e instanceof Error ? e.message : String(e))
  }

  const search = async (q: string) => {
    const term = q.trim()
    if (!term || caseId == null) return
    setLoading(`Querying the index for "${term}"`)
    setError('')
    setHistory([])
    try {
      setResult(asResult(await api.search(tool.path, caseId, term)))
    } catch (e) {
      failed(e)
    } finally {
      setLoading('')
      body.current?.scrollTo(0, 0)
    }
  }

  const load = async (f: FetchAction, keep: boolean) => {
    if (caseId == null) return
    if (keep && result) setHistory((h) => [...h, result])
    setLoading('Loading record')
    setError('')
    try {
      setResult(asResult(await api.fetchRecord(f.path, caseId, f.params)))
    } catch (e) {
      failed(e)
    } finally {
      setLoading('')
      body.current?.scrollTo(0, 0)
    }
  }

  // another window asked this tool to open with a query or a record
  useEffect(() => {
    if (!signal) return
    if (signal.fetch) void load(signal.fetch, true)
    else if (signal.query) {
      setText(signal.query)
      void search(signal.query)
    }
  }, [signal?.nonce]) // only when a new request arrives, not on every render

  // a new case clears the window
  useEffect(() => {
    setResult(null)
    setHistory([])
    setError('')
  }, [caseId])

  const nav: RecordNav = {
    open: (app, query) => s.requestOpen(app, query),
    fetch: (f) => (!f.app || f.app === tool.id ? void load(f, true) : s.requestOpen(f.app, undefined, f)),
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void search(text)
  }

  const back = () => {
    setResult(history[history.length - 1] ?? null)
    setHistory(history.slice(0, -1))
  }

  return (
    <div className="app lookup">
      <form className="query-bar" onSubmit={submit}>
        {history.length > 0 && (
          <button type="button" className="btn" onClick={back}>
            &lt; BACK
          </button>
        )}
        <input
          className="field"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={tool.placeholder}
          aria-label={`${tool.short} search`}
          spellCheck={false}
        />
        <button type="submit" className="btn btn-primary" disabled={caseId == null || !!loading}>
          SEARCH
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => {
            setText('')
            setResult(null)
            setHistory([])
            setError('')
          }}
        >
          CLEAR
        </button>
      </form>
      <div className="app-body" ref={body}>
        {caseId == null ? (
          <Notice>No case is open. Open CaseDesk and request a case before querying the indexes.</Notice>
        ) : loading ? (
          <Spinner label={loading} />
        ) : error ? (
          <Notice tone="error">{error}</Notice>
        ) : result && 'rec' in result ? (
          <RecordView rec={result.rec} nav={nav} />
        ) : result && 'env' in result ? (
          result.env.found ? (
            <EnvelopeView env={result.env} nav={nav} />
          ) : (
            <Notice>{result.env.message || 'No results.'}</Notice>
          )
        ) : (
          <div className="blurb">
            <GlossaryText text={tool.blurb} />
          </div>
        )}
      </div>
    </div>
  )
}
