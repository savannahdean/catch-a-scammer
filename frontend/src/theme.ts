// Brand strings and colour helpers. Change OS_NAME and the whole shell re-brands;
// nothing else hard-codes it. Colours themselves live in styles/theme.css.

export const brand = {
  GAME: 'Catch a Scammer',
  OS_NAME: 'SLEUTHOS',
  OS_VERSION: '7.1',
  AGENCY: 'DIGITAL INCIDENT RESPONSE UNIT',
}

/** Colour for a verdict badge ("malicious", "suspicious", "clean", ...). */
export function statusColor(status: string): string {
  switch (status) {
    case 'malicious':
      return 'var(--danger)'
    case 'suspicious':
      return 'var(--warn)'
    case 'benign':
    case 'clean':
      return 'var(--ok)'
    default:
      return 'var(--text-dim)'
  }
}

export function toneColor(tone: string | undefined, fallback = 'var(--text)'): string {
  switch (tone) {
    case 'danger':
      return 'var(--danger)'
    case 'warn':
      return 'var(--warn)'
    case 'ok':
      return 'var(--ok)'
    case 'dim':
      return 'var(--text-dim)'
    default:
      return fallback
  }
}

/** Evidence Map node colours by family: web infrastructure, people & messages, money, attribution. */
export function kindColor(k: string): string {
  if (['domain', 'url', 'url_scan'].includes(k)) return '#c84a4a'
  if (['ip', 'asn', 'nameserver'].includes(k)) return '#2b8fc4'
  if (['hosting_provider', 'registrar'].includes(k)) return '#6f8aa6'
  if (['certificate', 'whois_record', 'tracking_id'].includes(k)) return '#3f9c84'
  if (['malware_family', 'malware_sample', 'malware'].includes(k)) return '#c0602e'
  if (k === 'campaign') return '#d29a1f'
  if (['threat_actor', 'actor'].includes(k)) return '#9479c4'
  if (k === 'person') return '#3aa66e'
  if (['persona', 'social_post', 'image'].includes(k)) return '#d0558a'
  if (['email_message', 'email_address', 'sms_message', 'phone', 'audio_recording', 'document'].includes(k))
    return '#d98a3a'
  if (['payment_account', 'crypto_wallet'].includes(k)) return '#27a067'
  return '#8a96a6'
}

const KIND_LABEL: Record<string, string> = {
  ip: 'IP ADDRESS',
  hosting_provider: 'HOSTING',
  threat_actor: 'THREAT ACTOR',
  web_article: 'REPORTING',
  persona: 'PROFILE',
  social_post: 'POST / DM',
  malware_family: 'MALWARE',
  malware_sample: 'FILE',
  email_message: 'EMAIL',
  email_address: 'EMAIL ADDRESS',
  audio_recording: 'RECORDING',
  payment_account: 'ACCOUNT',
  crypto_wallet: 'WALLET',
  whois_record: 'WHOIS',
  url_scan: 'URL SCAN',
  sms_message: 'TEXT MESSAGE',
}

export function kindLabel(k: string): string {
  return KIND_LABEL[k] ?? k.replace(/_/g, ' ').toUpperCase()
}

/** The tool that best shows a record of this kind (mirrors APP_FOR_KIND in backend/server/cards.py). */
export function appForKind(k: string): string {
  const m: Record<string, string> = {
    persona: 'social',
    social_post: 'social',
    image: 'reverseimage',
    phone: 'phone',
    sms_message: 'sms',
    document: 'doclab',
    audio_recording: 'audiolab',
    payment_account: 'payments',
    crypto_wallet: 'moneytrail',
    complaint: 'complaints',
    email_message: 'breach',
    email_address: 'breach',
    url: 'urlscan',
    url_scan: 'urlscan',
    whois_record: 'whois',
    certificate: 'certs',
    campaign: 'websearch',
    malware_sample: 'malwaredb',
    malware_family: 'malwaredb',
    threat_actor: 'directory',
    person: 'directory',
    breach: 'breach',
  }
  return m[k] ?? 'intelsearch'
}

export const MOOD_COLOR: Record<string, string> = {
  calm: 'var(--ok)',
  annoyed: 'var(--warn)',
  angry: '#e0702b',
  furious: 'var(--danger)',
}
