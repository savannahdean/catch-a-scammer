// Case Report: the player commits to a conclusion and is graded.
// The form is built from the case: one field per conclusion the scenario asks
// for, each listing only records of that kind the player has actually found.
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ReportOptions, Verdict } from '../api/types'
import { GlossaryText } from '../glossary/GlossaryText'
import { useSession } from '../state/session'
import { kindLabel } from '../theme'
import { ActionRow, Notice, SectionLabel, Spinner } from '../ui/widgets'
import type { AppProps } from './types'

export function CaseReport({ signal }: AppProps) {
  const s = useSession()
  const [opts, setOpts] = useState<ReportOptions | null>(null)
  const [picked, setPicked] = useState<Record<string, number>>({})
  const [verdict, setVerdict] = useState<Verdict | null>(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)

  const load = async () => {
    if (s.caseId == null) return
    setLoading(true)
    try {
      const o = await api.reportOptions(s.caseId)
      setOpts(o)
      // keep each pick that is still offered
      setPicked((p) => {
        const next: Record<string, number> = {}
        for (const f of o.fields) if (p[f.key] && f.options.some((x) => x.entity_id === p[f.key])) next[f.key] = p[f.key]
        return next
      })
    } catch (e) {
      s.notify(`Could not load your findings: ${e instanceof Error ? e.message : e}`, true)
    } finally {
      setLoading(false)
    }
    void s.refreshEvidence()
  }

  useEffect(() => {
    setVerdict(null)
    setPicked({})
    setOpts(null)
    void load()
  }, [s.caseId, signal?.nonce])

  if (s.caseId == null || !s.brief) return <div className="app"><div className="app-body"><Notice>No case is open.</Notice></div></div>

  const fields = opts?.fields ?? []
  const filled = fields.filter((f) => picked[f.key]).length
  const complete = fields.length > 0 && filled === fields.length
  const closed = s.brief.status !== 'open'

  const submit = async () => {
    if (s.caseId == null) return
    setSending(true)
    try {
      const v = await api.submit(s.caseId, picked)
      setVerdict(v)
      s.notify(v.is_correct ? `Case solved. Score: ${v.score}` : `Report returned. ${v.correct_count} of ${v.total} correct.`, !v.is_correct)
      await s.refreshBrief()
      void s.refreshChat()
    } catch (e) {
      s.notify(`Submission failed: ${e instanceof Error ? e.message : e}`, true)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="app report">
      <div className="app-body">
        <h2 className="report-title">CASE #{s.brief.case_code}: CONCLUSION</h2>
        <p className="dim small">
          Each field lists only what you have surfaced in your tools. Your pinned evidence must connect the first exhibit
          to every conclusion: unsupported answers and red herrings on the board cost points, and a wrong report upsets
          your client.
        </p>
        {loading && !opts ? (
          <Spinner label="Loading your findings..." />
        ) : (
          fields.map((f) => (
            <div key={f.key} className="report-field">
              <label className="form-label" htmlFor={`f-${f.key}`}>
                {f.label.toUpperCase()}
              </label>
              <select
                id={`f-${f.key}`}
                className="field"
                value={picked[f.key] ?? ''}
                disabled={closed}
                onChange={(e) => setPicked({ ...picked, [f.key]: Number(e.target.value) })}
              >
                <option value="" disabled>
                  {f.options.length ? 'select...' : '(nothing of this kind found yet)'}
                </option>
                {f.options.map((o) => (
                  <option key={o.entity_id} value={o.entity_id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          ))
        )}

        <SectionLabel>SUPPORTING EVIDENCE</SectionLabel>
        {s.evidence.length === 0 ? (
          <p className="dim small">Nothing pinned. You can still submit, but conclusions with no supporting chain score lower.</p>
        ) : (
          s.evidence.map((it) => (
            <ActionRow
              key={it.evidence_id}
              text={it.label}
              right={`${kindLabel(it.entity_kind)}   ${closed ? '' : 'UNPIN'}`}
              color="var(--text-dim)"
              onClick={closed ? undefined : () => void s.unpin(it.entity_id)}
            />
          ))
        )}

        <div className="report-actions">
          <button type="button" className="btn btn-primary btn-large" disabled={!complete || closed || sending} onClick={() => void submit()} data-tour="submit">
            {sending ? 'SUBMITTING...' : 'SUBMIT REPORT'}
          </button>
          <button type="button" className="btn btn-large" disabled={loading} onClick={() => void load()}>
            REFRESH FINDINGS
          </button>
          {!complete && !closed && (
            <span className="dim small">
              {filled} of {fields.length} conclusions filled.
            </span>
          )}
        </div>

        {verdict && (
          <div className="verdict">
            <div className={`callout ${verdict.is_correct ? 'callout-ok' : 'callout-danger'}`}>
              <div className="verdict-head">{verdict.is_correct ? 'REPORT ACCEPTED' : 'REPORT RETURNED'}</div>
              <div className="dim small">
                attempt {verdict.attempt_no} · score {verdict.score}
              </div>
            </div>
            <table className="verdict-table">
              <tbody>
                {verdict.verdicts.map((v) => {
                  const known = typeof v.correct === 'boolean'
                  return (
                    <tr key={v.field}>
                      <td className={!known ? 'dim' : v.correct ? 'ok' : 'danger'}>{!known ? '??' : v.correct ? 'OK' : 'XX'}</td>
                      <td className="dim">{v.field}</td>
                      <td className={`mono ${known && !v.correct ? 'danger' : ''}`}>{v.submitted}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <pre className="briefing">
              <GlossaryText text={verdict.narrative} />
            </pre>
            {verdict.notes.length > 0 && (
              <>
                <SectionLabel>ANALYST FEEDBACK</SectionLabel>
                <ul className="notes">
                  {verdict.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
