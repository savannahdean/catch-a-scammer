// The Start menu: every app, grouped the way an investigation runs, plus the
// Field Manual, the tutorial, the study (post-game survey, leaving the study) and the way out.
import { APPS, GROUP_LABEL } from '../apps/registry'
import type { AppDef } from '../apps/types'
import { useScreens } from '../state/screens'
import { useSession } from '../state/session'
import { brand } from '../theme'

interface Props {
  onOpen: (id: string) => void
  onManual: () => void
  onTutorial: () => void
  onClose: () => void
}

export function StartMenu({ onOpen, onManual, onTutorial, onClose }: Props) {
  const s = useSession()
  const screens = useScreens()
  const groups = Object.keys(GROUP_LABEL) as AppDef['group'][]
  const inStudy = !!s.participantId

  return (
    <div className="start-menu" role="menu">
      <div className="start-head">
        <div className="start-title">
          {brand.OS_NAME} {brand.OS_VERSION}
        </div>
        <div className="start-sub">{inStudy ? 'Study participant' : 'Analyst workstation'}</div>
      </div>
      <div className="start-apps">
        {groups.map((g) => (
          <div key={g} className="start-group">
            <div className="start-group-label">{GROUP_LABEL[g]}</div>
            {APPS.filter((a) => a.group === g).map((a) => (
              <button key={a.id} type="button" role="menuitem" className="start-item" onClick={() => onOpen(a.id)}>
                <span className="start-dot" style={{ background: a.accent }} />
                {a.title}
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="start-foot">
        <button type="button" className="btn" onClick={onManual}>
          FIELD MANUAL (F1)
        </button>
        <button type="button" className="btn" onClick={onTutorial}>
          TUTORIAL: YOUR FIRST CASE
        </button>
        {inStudy && s.studyOpen && s.studyStatus?.pre_done && !s.studyStatus.post_done && (
          <button type="button" className="btn btn-primary" onClick={() => { onClose(); screens.toPostSurvey() }}>
            POST-GAME SURVEY
          </button>
        )}
        {inStudy && (
          <button
            type="button"
            className="btn"
            onClick={() => {
              if (window.confirm('Leave the study? Your survey answers will be deleted. You can keep playing.')) void s.leaveStudy()
            }}
          >
            LEAVE THE STUDY
          </button>
        )}
        <button type="button" className="btn" onClick={() => { onClose(); screens.toTitle() }}>
          BACK TO TITLE SCREEN
        </button>
      </div>
    </div>
  )
}
