// A survey, drawn from whatever questions the server has for the phase
// (survey_questions table). Questions with show_if only appear when an earlier
// answer matches, e.g. "What is your major?" after "I'm enrolled in college".
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { SurveyChoice, SurveyQuestion } from '../api/types'
import { useSession } from '../state/session'
import { Spinner } from '../ui/widgets'

type Answer = string | number | string[]

const INTRO = {
  pre: 'A few questions about you and what you already know. The quiz at the end is not graded; guessing is fine.',
  post: 'Thanks for playing. A few questions about how it went, and the same short quiz again.',
}

function visible(q: SurveyQuestion, answers: Record<string, Answer>) {
  if (!q.show_if) return true
  return Object.entries(q.show_if).every(([k, vals]) => vals.includes(String(answers[k] ?? '')))
}

function empty(a: Answer | undefined) {
  return a === undefined || a === '' || (Array.isArray(a) && a.length === 0)
}

export function SurveyScreen({ phase, onDone, onSkip }: {
  phase: 'pre' | 'post'
  onDone: (quiz?: { before: number; after: number; total: number }) => void
  onSkip: () => void
}) {
  const s = useSession()
  const [questions, setQuestions] = useState<SurveyQuestion[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, Answer>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.study
      .questions(phase)
      .then((r) => setQuestions(r.questions))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [phase])

  const shown = useMemo(() => (questions ?? []).filter((q) => visible(q, answers)), [questions, answers])
  const sections = useMemo(() => {
    const out: { name: string; qs: SurveyQuestion[] }[] = []
    for (const q of shown) {
      const last = out[out.length - 1]
      if (last && last.name === q.section) last.qs.push(q)
      else out.push({ name: q.section, qs: [q] })
    }
    return out
  }, [shown])
  const missing = shown.filter((q) => q.required && empty(answers[q.key]))
  const done = shown.length - missing.length

  const set = (key: string, v: Answer) => setAnswers((a) => ({ ...a, [key]: v }))

  const submit = async () => {
    if (!s.participantId) return onSkip()
    if (missing.length) {
      setError(`Please answer: ${missing[0].prompt}`)
      document.getElementById(`q-${missing[0].key}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setBusy(true)
    setError('')
    const payload: Record<string, Answer> = {}
    for (const q of shown) if (!empty(answers[q.key])) payload[q.key] = answers[q.key]
    try {
      const r = await api.study.answer(s.participantId, phase, payload)
      await s.refreshStudy()
      onDone(r.quiz)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="screen form-screen">
      <div className="form-card survey">
        <div className="eyebrow">{phase === 'pre' ? 'PRE-GAME SURVEY' : 'POST-GAME SURVEY'}</div>
        <h2>{phase === 'pre' ? 'Tell us about yourself' : 'How did it go?'}</h2>
        <p className="dim">{INTRO[phase]}</p>
        {questions == null && !error && <Spinner />}
        {sections.map((sec) => (
          <fieldset key={sec.name} className="survey-section">
            <legend>{sec.name}</legend>
            {sec.qs.map((q) => (
              <Question key={q.key} q={q} value={answers[q.key]} onChange={(v) => set(q.key, v)} />
            ))}
          </fieldset>
        ))}
        {error && <div className="notice notice-error">{error}</div>}
        {questions && (
          <div className="form-actions">
            <span className="dim small">
              {done} of {shown.length} answered
            </span>
            <button type="button" className="btn" onClick={onSkip}>
              {phase === 'pre' ? 'SKIP FOR NOW' : 'NOT NOW'}
            </button>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void submit()}>
              {busy ? 'SAVING...' : 'SUBMIT'}
            </button>
          </div>
        )}
      </div>
    </main>
  )
}

function Question({ q, value, onChange }: { q: SurveyQuestion; value: Answer | undefined; onChange: (v: Answer) => void }) {
  const id = `q-${q.key}`
  const label = (
    <div className="q-prompt">
      {q.prompt}
      {!q.required && <span className="q-optional"> (optional)</span>}
    </div>
  )
  if (q.kind === 'number') {
    const o = q.options as { min: number; max: number }
    return (
      <div className="q" id={id}>
        <label htmlFor={`${id}-in`}>{label}</label>
        <input id={`${id}-in`} className="field field-short" type="number" min={o.min} max={o.max}
          value={value === undefined ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
      </div>
    )
  }
  if (q.kind === 'text' || q.kind === 'longtext') {
    return (
      <div className="q" id={id}>
        <label htmlFor={`${id}-in`}>{label}</label>
        {q.kind === 'text' ? (
          <input id={`${id}-in`} className="field" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} maxLength={200} />
        ) : (
          <textarea id={`${id}-in`} className="field" rows={3} value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} maxLength={2000} />
        )}
      </div>
    )
  }
  if (q.kind === 'likert') {
    const o = q.options as { min: number; max: number; low?: string; high?: string }
    const steps = Array.from({ length: o.max - o.min + 1 }, (_, i) => o.min + i)
    return (
      <div className="q" id={id} role="radiogroup" aria-label={q.prompt}>
        {label}
        <div className="likert">
          <span className="likert-end">{o.low}</span>
          {steps.map((n) => (
            <label key={n} className={`likert-step${value === n ? ' on' : ''}`}>
              <input type="radio" name={id} checked={value === n} onChange={() => onChange(n)} />
              {n}
            </label>
          ))}
          <span className="likert-end">{o.high}</span>
        </div>
      </div>
    )
  }
  const choices = q.options as SurveyChoice[]
  if (q.kind === 'multi') {
    const cur = Array.isArray(value) ? value : []
    return (
      <div className="q" id={id}>
        {label}
        <div className="choices">
          {choices.map((c) => (
            <label key={c.value} className="check">
              <input
                type="checkbox"
                checked={cur.includes(c.value)}
                onChange={(e) => onChange(e.target.checked ? [...cur, c.value] : cur.filter((x) => x !== c.value))}
              />
              <span>{c.label}</span>
            </label>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="q" id={id} role="radiogroup" aria-label={q.prompt}>
      {label}
      <div className="choices">
        {choices.map((c) => (
          <label key={c.value} className="check">
            <input type="radio" name={id} checked={value === c.value} onChange={() => onChange(c.value)} />
            <span>{c.label}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
