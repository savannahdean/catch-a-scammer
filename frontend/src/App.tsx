// Which full screen is showing:
//
//   title ──► (study opt-in) consent ──► pre-game survey ──► boot ──► desktop
//                                                                       │
//                                       thanks ◄── post-game survey ◄───┘
//
// Players who don't opt in go title ──► boot ──► desktop and never see a survey.
import { useCallback, useMemo, useState } from 'react'
import { Desktop } from './os/Desktop'
import { BootScreen } from './screens/BootScreen'
import { ConsentScreen } from './screens/ConsentScreen'
import { SurveyScreen } from './screens/SurveyScreen'
import { ThanksScreen } from './screens/ThanksScreen'
import { TitleScreen } from './screens/TitleScreen'
import { ScreensContext } from './state/screens'
import { SessionProvider, useSession } from './state/session'

type Screen = 'title' | 'consent' | 'pre' | 'boot' | 'desktop' | 'post' | 'thanks'

function Screens() {
  const s = useSession()
  const [screen, setScreen] = useState<Screen>('title')
  const [quiz, setQuiz] = useState<{ before: number; after: number; total: number }>()
  const [booted, setBooted] = useState(false)

  const toDesktop = useCallback(() => setScreen(booted ? 'desktop' : 'boot'), [booted])
  const finishBoot = useCallback(() => {
    setBooted(true)
    setScreen('desktop')
  }, [])

  const start = (joinStudy: boolean) => {
    if (joinStudy && s.studyOpen && !s.participantId) return setScreen('consent')
    if (s.studyOpen && s.participantId && s.studyStatus && !s.studyStatus.pre_done) return setScreen('pre')
    toDesktop()
  }

  const nav = useMemo(() => ({ toTitle: () => setScreen('title'), toPostSurvey: () => setScreen('post') }), [])

  return (
    <ScreensContext.Provider value={nav}>
      {screen === 'title' && <TitleScreen onStart={start} />}
      {screen === 'consent' && <ConsentScreen onJoined={() => setScreen('pre')} onDecline={toDesktop} />}
      {screen === 'pre' && <SurveyScreen phase="pre" onDone={toDesktop} onSkip={toDesktop} />}
      {screen === 'boot' && <BootScreen onDone={finishBoot} />}
      {screen === 'post' && (
        <SurveyScreen
          phase="post"
          onDone={(q) => {
            setQuiz(q)
            setScreen('thanks')
          }}
          onSkip={() => setScreen('desktop')}
        />
      )}
      {screen === 'thanks' && <ThanksScreen quiz={quiz} onBack={() => setScreen('desktop')} onTitle={() => setScreen('title')} />}
      {/* the desktop stays mounted once booted, so windows survive a trip to a survey */}
      {booted && (
        <div style={{ display: screen === 'desktop' ? 'contents' : 'none' }}>
          <Desktop />
        </div>
      )}
    </ScreensContext.Provider>
  )
}

export default function App() {
  return (
    <SessionProvider>
      <Screens />
    </SessionProvider>
  )
}
