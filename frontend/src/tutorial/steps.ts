// The first-case tutorial, as data. It walks a new player through a real EASY
// bulk-phishing case with the friendliest client: the briefing, the client, the
// email, the phishing domain, where it was hosted, who is behind it, and the
// report. A step with `done` ticks itself off when the player does the thing;
// a step without one waits for NEXT. `target` lists elements to point at, and
// the first one on screen gets the glowing ring.
import type { Brief, EvidenceItem, MessengerState } from '../api/types'

export interface TourCtx {
  brief: Brief | null
  evidence: EvidenceItem[]
  chat: MessengerState | null
  /** the window is open and not minimized */
  isOpen: (app: string) => boolean
}

export interface TourAction {
  label: string
  run: 'start-case' | { app: string; query?: 'entry-domain' }
}

export interface TourStep {
  id: string
  title: string
  /** paragraphs separated by a blank line; Dictionary words get underlined */
  body: (c: TourCtx) => string
  target?: string[]
  done?: (c: TourCtx) => boolean
  action?: TourAction
}

/** The case the tutorial is written for. */
export const TRAINING_CASE = { difficulty: 'easy', scenario: 'bulk_phish', personality: 'sweet' }

export const isTrainingCase = (b: Brief | null) =>
  !!b && b.difficulty === TRAINING_CASE.difficulty && b.scenario === TRAINING_CASE.scenario

const pinned = (c: TourCtx, ...kinds: string[]) => c.evidence.some((e) => kinds.includes(e.entity_kind))
const incident = (c: TourCtx) => /INCIDENT:\s+(.+)/.exec(c.brief?.briefing ?? '')?.[1]?.trim() ?? 'the incident time'
const domain = (c: TourCtx) => c.brief?.entry_domain || 'the domain'

export const STEPS: TourStep[] = [
  {
    id: 'welcome',
    title: 'Welcome, analyst',
    body: () =>
      'You investigate online scams the way real analysts do: start from the one thing the victim saw, and follow ' +
      'the clues until you know where it was run from and who is behind it.\n\n' +
      'This tutorial walks you through one easy case, step by step, in about 10 to 15 minutes. Every step ' +
      'ticks itself off when you do it. A glowing ring shows you where to click.',
  },
  {
    id: 'start',
    title: 'Get your first case',
    body: () =>
      'Cases arrive in CaseDesk. Your training case is a phishing email: the most common scam there is.\n\n' +
      'Press START TRAINING CASE below. The game builds a fresh case for you: a victim, the email they got, and ' +
      'the crew behind it.',
    target: ['[data-tour="win-casedesk"]', '[data-tour="icon-casedesk"]'],
    action: { label: 'START TRAINING CASE', run: 'start-case' },
    done: (c) => isTrainingCase(c.brief) && c.brief!.status === 'open',
  },
  {
    id: 'briefing',
    title: 'Read the briefing',
    body: (c) =>
      'The briefing in CaseDesk says who reported the scam, what happened, and when.\n\n' +
      `Note the INCIDENT time (${incident(c)}). Scam websites move around, so later you will need to know ` +
      'where things were at that exact moment.',
    target: ['[data-tour="briefing"]', '[data-tour="win-casedesk"]', '[data-tour="icon-casedesk"]'],
  },
  {
    id: 'client',
    title: 'Talk to your client',
    body: () =>
      'The person who reported the scam is your client, and they are waiting in the Messenger. Clients know things ' +
      'that are not in the briefing, and some only tell you if you ask.\n\n' +
      'Ask them something. Click a suggested question like "What happened?" or type your own and press Enter.\n\n' +
      'Watch the MOOD bar: confusing messages and wrong accusations wear their patience down. On harder ' +
      'difficulties an unhappy client drops the case.',
    target: ['[data-tour="starters"]', '[data-tour="chat-input"]', '[data-tour="win-messenger"]', '[data-tour="icon-messenger"]'],
    action: { label: 'OPEN MESSENGER', run: { app: 'messenger' } },
    done: (c) => !!c.chat?.messages.some((m) => m.from === 'player'),
  },
  {
    id: 'exhibit',
    title: 'Look at the email',
    body: () =>
      'Back in CaseDesk, scroll down to the EXHIBITS: what the client handed over. Here it is the phishing email.\n\n' +
      'Read its RAW HEADERS. The From line can be faked, but the Return-Path and Reply-To show where the email ' +
      'really came from, and a DMARC "fail" means the sender was not who it claimed to be.\n\n' +
      'Your evidence has to start from this email, so press ADD TO EVIDENCE on it.',
    target: ['[data-tour="exhibits"] [data-tour="pin"]', '[data-tour="exhibits"]', '[data-tour="win-casedesk"]', '[data-tour="icon-casedesk"]'],
    done: (c) => c.evidence.length > 0,
  },
  {
    id: 'follow-link',
    title: 'Follow the link',
    body: (c) =>
      `The email's "verify now" button pointed at ${domain(c)}. Let's find out what that is.\n\n` +
      'Press OPEN LINK IN INTELSEARCH at the top of CaseDesk. IntelSearch is the threat-intelligence search: ' +
      'paste a domain or IP address and it tells you what is known about it.',
    target: ['[data-tour="open-link"]', '[data-tour="win-casedesk"]'],
    action: { label: 'OPEN INTELSEARCH', run: { app: 'intelsearch', query: 'entry-domain' } },
    done: (c) => c.isOpen('intelsearch'),
  },
  {
    id: 'pin-domain',
    title: 'Pin the phishing domain',
    body: () =>
      'This record is the fake website the victim logged in to. Its name imitates a real brand (a look-alike ' +
      'domain). Compare when it was first seen with the incident time.\n\n' +
      'Stuck on a word? Anything with a dotted underline is in the Dictionary: hover it for a quick meaning, or ' +
      'click it for more. F2 opens the Dictionary any time.\n\n' +
      'Press ADD TO EVIDENCE on the domain.',
    target: ['[data-tour="win-intelsearch"] [data-tour="pin"]', '[data-tour="win-intelsearch"]', '[data-tour="icon-intelsearch"]'],
    done: (c) => pinned(c, 'domain'),
  },
  {
    id: 'dns',
    title: 'Where was it hosted?',
    body: () =>
      'A domain is only a name. The website itself ran on a server with an IP address, and that is the next clue.\n\n' +
      'Under INVESTIGATE FURTHER, press DNS HISTORY. It lists every address the domain has pointed to, with dates.',
    target: ['[data-tour="win-intelsearch"] [data-tour="pivot-dns"]', '[data-tour="win-intelsearch"]', '[data-tour="icon-dns"]'],
    action: { label: 'OPEN DNS HISTORY', run: { app: 'dns', query: 'entry-domain' } },
    done: (c) => c.isOpen('dns'),
  },
  {
    id: 'pin-ip',
    title: 'Find the server at the time of the attack',
    body: (c) =>
      `Compare each row's dates with the incident time (${incident(c)}). The newest row is often a sinkhole: ` +
      'after a takedown the domain is pointed at a defender\'s server, and that is not the attacker.\n\n' +
      'Click the row whose dates cover the incident. It opens that IP address in IntelSearch. Press ADD TO ' +
      'EVIDENCE on it.',
    target: ['[data-tour="win-dns"]', '[data-tour="icon-dns"]'],
    done: (c) => pinned(c, 'ip'),
  },
  {
    id: 'campaign',
    title: 'Who is behind it?',
    body: () =>
      'Servers tell you what happened. Published reporting tells you who security researchers think did it.\n\n' +
      'Search the phishing domain in Web Search. A report that mentions it names the campaign this attack ' +
      'belongs to. Open the campaign record and press ADD TO EVIDENCE.\n\n' +
      'Check each source\'s reliability grade: A to C is trustworthy, D and E are rumours.',
    target: ['[data-tour="win-websearch"] [data-tour="pin"]', '[data-tour="win-websearch"]', '[data-tour="icon-websearch"]'],
    action: { label: 'SEARCH THE WEB FOR THE DOMAIN', run: { app: 'websearch', query: 'entry-domain' } },
    done: (c) => pinned(c, 'campaign'),
  },
  {
    id: 'actor',
    title: 'Name the crew',
    body: () =>
      'The campaign record lists who it is ATTRIBUTED TO. Security companies each give the same crew a different ' +
      'name, so click the name (OPEN PROFILE) to look it up in the Directory, which matches the aliases.\n\n' +
      'Press ADD TO EVIDENCE on the threat actor.\n\n' +
      'Stuck at any point? REQUEST HINT in CaseDesk gives you a nudge, but costs points.',
    target: ['[data-tour="win-directory"] [data-tour="pin"]', '[data-tour="win-directory"]', '[data-tour="win-websearch"]', '[data-tour="icon-directory"]'],
    done: (c) => pinned(c, 'threat_actor'),
  },
  {
    id: 'map',
    title: 'See how it connects',
    body: () =>
      'Your evidence now runs from the email, to the website, to its server, to the campaign and the crew behind it. ' +
      'That chain is what makes a conclusion believable.\n\n' +
      'The Evidence Map draws it. Open it if you like, then press NEXT.',
    target: ['[data-tour="win-evidencemap"]', '[data-tour="icon-evidencemap"]'],
    action: { label: 'OPEN EVIDENCE MAP', run: { app: 'evidencemap' } },
  },
  {
    id: 'report',
    title: 'File your report',
    body: () =>
      'Open the Case Report. Each question has a dropdown of things you have found: pick the phishing domain, the ' +
      'IP address it was on at the time, the campaign and the threat actor. Then SUBMIT REPORT.\n\n' +
      'If something is wrong the report comes back marked, so you can fix it and send it again. Every returned ' +
      'report costs points.',
    target: ['[data-tour="win-casereport"] [data-tour="submit"]', '[data-tour="win-casereport"]', '[data-tour="icon-casereport"]'],
    action: { label: 'OPEN CASE REPORT', run: { app: 'casereport' } },
    done: (c) => c.brief?.status === 'solved',
  },
  {
    id: 'finish',
    title: 'Case closed',
    body: () =>
      'Well done: you traced a phishing email to its website, its server, its campaign and its crew. That is a real ' +
      'investigation. CaseDesk now shows what really happened.\n\n' +
      'Next, try a MEDIUM case: the infrastructure is not labelled for you, the link hides behind a hacked website, ' +
      'and clients need asking. Try other scam types too: romance scams, fake support calls, sextortion and more.\n\n' +
      'F1 opens the Field Manual and F2 the Dictionary. You can replay this tutorial from the Start menu.',
  },
]
