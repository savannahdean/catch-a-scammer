// The title screen: start playing, optionally opting into the research study
// (only offered while the server's study is open).
import { useState } from 'react'
import { FieldManual } from '../os/FieldManual'
import { useSession } from '../state/session'
import { brand } from '../theme'

export function TitleScreen({ onStart }: { onStart: (joinStudy: boolean) => void }) {
  const s = useSession()
  const [study, setStudy] = useState(!!s.participantId)
  const [manual, setManual] = useState(false)
  const inStudy = !!s.participantId

  return (
    <main className="screen title-screen">
      <div className="radar radar-title" aria-hidden="true" />
      <div className="title-card">
        <div className="title-logo" aria-hidden="true">
          <svg viewBox="0 0 64 64" width="72" height="72">
            <circle cx="28" cy="28" r="15" fill="none" stroke="var(--accent-bright)" strokeWidth="5" />
            <line x1="39" y1="39" x2="54" y2="54" stroke="var(--accent-bright)" strokeWidth="7" strokeLinecap="round" />
            <circle cx="28" cy="28" r="4" fill="var(--gold)" />
          </svg>
        </div>
        <h1 className="game-title">{brand.GAME.toUpperCase()}</h1>
        <p className="game-tagline">An open-source intelligence investigation game</p>
        <p className="title-pitch">
          Someone has been scammed. Question your client, follow the evidence through domains, profiles, phone numbers
          and money trails, and name who is behind it, without getting fooled by decoys.
        </p>

        <div className="title-actions">
          <button type="button" className="btn btn-primary btn-hero" onClick={() => onStart(study)} disabled={!s.online}>
            {s.caseId != null ? 'CONTINUE INVESTIGATING' : 'START INVESTIGATING'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setManual(true)}>
            HOW TO PLAY
          </button>
        </div>

        {inStudy ? (
          <div className="study-opt joined">
            You're taking part in the study. Thank you! You can leave it from the Start menu at any time.
          </div>
        ) : s.studyOpen ? (
          <label className="study-opt">
            <input type="checkbox" checked={study} onChange={(e) => setStudy(e.target.checked)} />
            <span>
              <b>Take part in our research study (optional).</b> A short survey before and after you play helps us see
              what players learn about OSINT. You can play without it, and the game is the same either way.
            </span>
          </label>
        ) : null}

        {!s.online && (
          <div className="notice notice-error">
            The game server isn't answering. Start the database and the API first (see the README), then reload.
          </div>
        )}
      </div>
      <footer className="title-foot">
        Every person, company, domain, phone number and address in this game is fictional. IPs come from reserved
        documentation ranges and every domain ends in .example or .test.
      </footer>
      {manual && <FieldManual onClose={() => setManual(false)} />}
    </main>
  )
}
