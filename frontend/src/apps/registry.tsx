// The list of windows that exist. Its order is the order of the desktop icons,
// the taskbar and the Start menu, and it follows the investigation: read the
// case and talk to the client, run down the infrastructure, work the people,
// messages and money, read the reporting, then file the report.
// Add an entry here and a new app appears everywhere.
import { CaseDesk } from './CaseDesk'
import { CaseReport } from './CaseReport'
import { EvidenceMap } from './EvidenceMap'
import { Glossary } from './Glossary'
import { LookupApp } from './LookupApp'
import { LOOKUP_TOOLS } from './lookupTools'
import { Messenger } from './Messenger'
import type { AppDef } from './types'

const lookups: AppDef[] = LOOKUP_TOOLS.map((t) => ({
  id: t.id,
  title: t.title,
  short: t.short,
  glyph: t.glyph,
  accent: t.accent,
  size: [760, 600],
  requiresCase: true,
  group: t.group,
  render: (p) => <LookupApp {...p} tool={t} />,
}))

const byId = (id: string) => lookups.find((a) => a.id === id)!

export const APPS: AppDef[] = [
  {
    id: 'casedesk', title: 'CaseDesk - Incident Queue', short: 'CaseDesk', glyph: 'CD', accent: '#10567a',
    size: [860, 640], requiresCase: false, group: 'case', render: (p) => <CaseDesk {...p} />,
  },
  {
    id: 'messenger', title: 'Messenger - Your Client', short: 'Messenger', glyph: 'MSG', accent: '#3a8f5c',
    size: [560, 640], requiresCase: false, group: 'case', render: (p) => <Messenger {...p} />,
  },
  {
    id: 'glossary', title: 'Dictionary - Plain-English Terms', short: 'Dictionary', glyph: 'A-Z', accent: '#4a6a8a',
    size: [640, 640], requiresCase: false, group: 'case', render: (p) => <Glossary {...p} />,
  },
  ...['intelsearch', 'dns', 'whois', 'certs', 'urlscan', 'malwaredb'].map(byId),
  ...['social', 'reverseimage', 'phone', 'sms', 'audiolab', 'doclab', 'payments', 'moneytrail', 'complaints', 'breach'].map(byId),
  ...['websearch', 'directory'].map(byId),
  {
    id: 'evidencemap', title: 'Evidence Map', short: 'Evidence Map', glyph: 'MAP', accent: '#187aa8',
    size: [960, 620], requiresCase: true, group: 'report', render: (p) => <EvidenceMap {...p} />,
  },
  {
    id: 'casereport', title: 'Case Report - Final Conclusion', short: 'Case Report', glyph: 'CR', accent: '#c08418',
    size: [780, 660], requiresCase: true, group: 'report', render: (p) => <CaseReport {...p} />,
  },
]

export const GROUP_LABEL: Record<AppDef['group'], string> = {
  case: 'The case',
  infra: 'Infrastructure',
  people: 'People, messages & money',
  report: 'Reporting & attribution',
}
