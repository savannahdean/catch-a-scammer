// What every window (app) gets from the Desktop.
import type { ReactNode } from 'react'
import type { FetchAction } from '../api/types'

/** Sent when another window asks this one to open: a search, or one record to load. */
export interface OpenSignal {
  nonce: number
  query?: string
  fetch?: FetchAction
}

export interface AppProps {
  signal: OpenSignal | null
  /** this window is the focused (top) one */
  active: boolean
}

export interface AppDef {
  id: string
  title: string
  /** name on the desktop icon and taskbar */
  short: string
  glyph: string
  accent: string
  size: [number, number]
  requiresCase: boolean
  group: 'case' | 'infra' | 'people' | 'report'
  render: (p: AppProps) => ReactNode
}
