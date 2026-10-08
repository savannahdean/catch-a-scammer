// Pop-up notifications in the bottom-right corner. Messages from the client
// show as chat notifications; click one to open the Messenger.
import { useSession } from '../state/session'

export function Toasts() {
  const s = useSession()
  return (
    <div className="toasts" aria-live="polite">
      {s.toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`toast${t.error ? ' toast-error' : ''}${t.from ? ' toast-chat' : ''}`}
          onClick={() => {
            if (t.from) s.requestOpen('messenger')
            s.dismiss(t.id)
          }}
        >
          {t.from && <span className="toast-from">{t.from}</span>}
          <span>{t.text}</span>
        </button>
      ))}
    </div>
  )
}
