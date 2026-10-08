// Lets any window move the player between full screens (title, surveys, desktop)
// without knowing how App.tsx arranges them.
import { createContext, useContext } from 'react'

export interface Screens {
  toTitle: () => void
  toPostSurvey: () => void
}

export const ScreensContext = createContext<Screens>({ toTitle: () => {}, toPostSurvey: () => {} })

export function useScreens(): Screens {
  return useContext(ScreensContext)
}
