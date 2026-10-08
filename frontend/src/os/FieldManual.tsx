// F1: how to play, in one screen.
import { GlossaryText } from '../glossary/GlossaryText'

// paragraphs whose Dictionary words get underlined
const TOOLS =
  'follow every lead. Each record links to the next tool (a domain to its DNS history, a profile to a reverse image search).'
const HARD =
  'Not everything you find belongs to your case. Shared hosting puts unrelated sites on one address, CDNs hide the ' +
  'real server, sinkholes replace it after a takedown, and low-reliability blogs blame the wrong group. On HARD ' +
  'and EXPERT you must also unmask the real person behind the operation.'
const SCORING =
  "Hints and returned reports cost points. Conclusions your pinned evidence doesn't connect to, and red herrings " +
  'on the board, cost points too.'

export function FieldManual({ onClose }: { onClose: () => void }) {
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="Field Manual" onClick={onClose}>
      <div className="manual" onClick={(e) => e.stopPropagation()}>
        <header className="manual-head">Field Manual</header>
        <div className="manual-body">
          <p>
            You are an analyst in the incident response unit. A case arrives with one usable clue: the message, profile or
            page the victim saw. Everything else you have to earn.
          </p>
          <p className="dim">First time? Start menu → TUTORIAL walks you through a whole case.</p>
          <h4>THE LOOP</h4>
          <ol>
            <li><b>CaseDesk</b>: read the brief and the exhibits the client handed over.</li>
            <li><b>Messenger</b>: question the client. Ask what happened, when, how they were contacted, whether they paid or clicked anything.</li>
            <li><b>The tools</b>: <GlossaryText text={TOOLS} /></li>
            <li><b>ADD TO EVIDENCE</b>: pin the records that connect the first exhibit to your conclusions.</li>
            <li><b>Case Report</b>: name what the case asks for. You can only pick what you have found.</li>
          </ol>
          <h4>YOUR CLIENT</h4>
          <p>
            Clients have personalities. Some tell you everything; some leave out the embarrassing part until you ask
            directly or ask again; a liar only admits it when you SHOW them proof from your evidence board. Keep an eye on
            the mood meter: unclear messages, pinning things they know are wrong, wrong reports and leaving a demanding
            client waiting all drain it. From MEDIUM up, a client at zero withdraws the case.
          </p>
          <h4>DON'T KNOW A WORD?</h4>
          <p>
            Words with a <span className="gloss">dotted underline</span> are in the <b>Dictionary</b>. Hover one for a
            quick meaning, click it for the full entry, or open the Dictionary from the desktop (F2) and search it.
          </p>
          <h4>WHAT MAKES IT HARD</h4>
          <p>
            <GlossaryText text={HARD} />
          </p>
          <h4>SCORING</h4>
          <p>
            <GlossaryText text={SCORING} />
          </p>
          <p className="dim">F1 toggles this manual. F2 opens the Dictionary. ESC closes menus and overlays.</p>
        </div>
        <footer className="manual-foot">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            CLOSE
          </button>
        </footer>
      </div>
    </div>
  )
}
