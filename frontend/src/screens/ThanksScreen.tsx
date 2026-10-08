// After the post-game survey: the player's own quiz score before and after.
export function ThanksScreen({ quiz, onBack, onTitle }: {
  quiz?: { before: number; after: number; total: number }
  onBack: () => void
  onTitle: () => void
}) {
  return (
    <main className="screen form-screen">
      <div className="form-card thanks">
        <div className="eyebrow">STUDY COMPLETE</div>
        <h2>Thank you!</h2>
        <p>Your answers are saved under a random ID. They help us see what players learn about open-source investigation.</p>
        {quiz && quiz.total > 0 && (
          <div className="quiz-result">
            <div>
              <div className="quiz-num">{quiz.before}/{quiz.total}</div>
              <div className="dim small">quiz before playing</div>
            </div>
            <div className="quiz-arrow" aria-hidden="true">→</div>
            <div>
              <div className="quiz-num">{quiz.after}/{quiz.total}</div>
              <div className="dim small">quiz after playing</div>
            </div>
          </div>
        )}
        <div className="form-actions">
          <button type="button" className="btn" onClick={onTitle}>
            TITLE SCREEN
          </button>
          <button type="button" className="btn btn-primary" onClick={onBack}>
            KEEP PLAYING
          </button>
        </div>
      </div>
    </main>
  )
}
