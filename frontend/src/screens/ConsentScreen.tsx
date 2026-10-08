// Study consent. Nothing is stored until the player agrees; "No thanks" goes
// straight to the game.
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useSession } from '../state/session'
import { Spinner } from '../ui/widgets'

export function ConsentScreen({ onJoined, onDecline }: { onJoined: () => void; onDecline: () => void }) {
  const s = useSession()
  const [text, setText] = useState<string | null>(null)
  const [adult, setAdult] = useState(false)
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.study
      .consent()
      .then((c) => setText(c.text))
      .catch(() => setText('The consent text could not be loaded. You can still play without joining the study.'))
  }, [])

  const join = async () => {
    setBusy(true)
    setError('')
    try {
      const r = await api.study.join()
      s.joinStudy(r.participant_id)
      onJoined()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="screen form-screen">
      <div className="form-card">
        <div className="eyebrow">RESEARCH STUDY</div>
        <h2>Before you start</h2>
        {text == null ? <Spinner /> : <div className="consent-text">{text}</div>}
        <label className="check">
          <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
          <span>I am 18 or older.</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>I have read the above and agree to take part.</span>
        </label>
        {error && <div className="notice notice-error">{error}</div>}
        <div className="form-actions">
          <button type="button" className="btn" onClick={onDecline}>
            NO THANKS, JUST PLAY
          </button>
          <button type="button" className="btn btn-primary" disabled={!adult || !agree || busy} onClick={() => void join()}>
            JOIN AND CONTINUE
          </button>
        </div>
      </div>
    </main>
  )
}
