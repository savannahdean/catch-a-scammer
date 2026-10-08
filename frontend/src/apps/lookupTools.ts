// The 18 search tools. They differ only in the API route they search, what
// the player is told to type, and the help text shown before the first search,
// so each one is a row here. The server describes every result.

export interface LookupTool {
  id: string
  title: string
  short: string
  glyph: string
  accent: string
  path: string
  placeholder: string
  blurb: string
  group: 'infra' | 'people' | 'report'
}

export const LOOKUP_TOOLS: LookupTool[] = [
  // --------------------------------------------------------------- infrastructure
  {
    id: 'intelsearch', title: 'IntelSearch - Threat Intelligence', short: 'IntelSearch', glyph: 'IS', accent: '#187aa8',
    path: '/api/intel', placeholder: 'domain, URL or IP address', group: 'infra',
    blurb: `IntelSearch queries the threat-intelligence index.

Paste the link from the victim's statement. A malicious domain will usually resolve to an address, and that address will usually be hosting more than one thing.

Accepted input:
    secure-account-check.example
    https://secure-account-check.example/login
    203.0.113.42

Co-hosting is not attribution. Other domains on the same address may have nothing to do with this incident.`,
  },
  {
    id: 'dns', title: 'DNS History - Passive DNS', short: 'DNS History', glyph: 'DNS', accent: '#1e6496',
    path: '/api/dns', placeholder: 'domain or IP address', group: 'infra',
    blurb: `Every resolution of a domain to an address that sensors have observed, with first-seen and last-seen dates. It works both ways: search an address to see every domain that pointed at it.

Compare the dates with the incident. After a takedown, domains often point at a sinkhole; behind a CDN they point at a shared edge server. Neither is the attacker. The origin is usually in the older history.`,
  },
  {
    id: 'whois', title: 'WHOIS History', short: 'WHOIS', glyph: 'WHO', accent: '#5a5a96',
    path: '/api/whois', placeholder: 'domain, or a registrant email', group: 'infra',
    blurb: `Every captured snapshot of a domain's registration record.

Today most records say REDACTED FOR PRIVACY. Snapshots taken in the first hours after registration sometimes caught the real registrant before privacy was switched on. An email found there can be searched in breach data.

Search a registrant email to find every domain it registered.`,
  },
  {
    id: 'certs', title: 'CertSearch - Certificate Transparency', short: 'CertSearch', glyph: 'CT', accent: '#3c826e',
    path: '/api/certs', placeholder: 'domain or part of one', group: 'infra',
    blurb: `Searches the public certificate-transparency logs. Every TLS certificate is logged, with every name it covers.

Attackers often request one certificate for several of their domains at once, which links them. A CDN's shared certificate covers thousands of unrelated customers and links nothing.`,
  },
  {
    id: 'urlscan', title: 'URL Scanner', short: 'URL Scanner', glyph: 'URL', accent: '#b45a28',
    path: '/api/urlscan', placeholder: 'URL, domain or IP address', group: 'infra',
    blurb: `Sandboxed scans of web pages: the final URL after redirects, page title, server, the IP it was served from, and fingerprints you can pivot on: analytics tracking IDs, favicon hash, JARM TLS fingerprint, and phishing-kit leftovers.

A tracking ID or JARM fingerprint shared with other pages usually means the same operator. A favicon only means the same brand was copied.`,
  },
  {
    id: 'malwaredb', title: 'MalwareDB - Family Index', short: 'MalwareDB', glyph: 'MW', accent: '#b23030',
    path: '/api/malware', placeholder: 'malware family, SHA-256, MD5 or file name', group: 'infra',
    blurb: `MalwareDB indexes malware families, the campaigns they have been seen in, and the infrastructure they beacon to. It also holds file analyses: search a SHA-256, MD5 or file name to see antivirus detections, YARA matches, strings and the extracted configuration.

Families are shared between unrelated crews, so prefer the one that was actually staged on the domain your victim visited. Strings that name a famous group are trivial to plant.`,
  },
  // -------------------------------------------------------- people, messages, money
  {
    id: 'social', title: 'Social Search - Profiles and Posts', short: 'Social', glyph: 'SOC', accent: '#c44878',
    path: '/api/social', placeholder: '@handle, name, or a phrase from a message', group: 'people',
    blurb: `Searches public profiles, posts and the direct messages in this case across every platform, including criminal forums.

Paste a phrase from a message the victim received and you get the message and the profile that sent it. Search a username and you get every account using it, on any platform.

What to check on a profile:
    - how old the account is compared to when contact started
    - whether the photos belong to someone else (Reverse Image)
    - whether the same handle exists elsewhere, and who that is

A similar handle is not the same person. Look for something that actually links two accounts.`,
  },
  {
    id: 'reverseimage', title: 'Reverse Image Search', short: 'Reverse Image', glyph: 'IMG', accent: '#9660c4',
    path: '/api/reverseimage', placeholder: 'image ID (img:...) or perceptual hash', group: 'people',
    blurb: `Finds every place a picture, or a resized or recompressed copy of it, has appeared, oldest first.

Catfish and investment scammers rarely use their own face. If a profile created last month uses a photo first posted years ago by someone else, you have found a stolen identity.

If there is no earlier copy, check the AI-face detector score. A generated face has no real owner to find.

Click REVERSE IMAGE SEARCH on any profile photo, or paste its Image ID.`,
  },
  {
    id: 'phone', title: 'Phone Lookup - Carrier and Reputation', short: 'Phone Lookup', glyph: 'TEL', accent: '#28968c',
    path: '/api/phone', placeholder: 'phone number in any format', group: 'people',
    blurb: `Carrier lookup: who issued the number, what kind of line it is, the caller-ID name on file, and how many people have reported it.

VoIP and toll-free numbers can be rented in minutes and dropped just as fast. A bank or support desk calling from one is a red flag.

Caller ID is easy to fake. The number that showed up on the victim's phone tells you little. A number the scammer told them to call back is a real lead.`,
  },
  {
    id: 'sms', title: 'Spam Text Reports', short: 'Spam Texts', glyph: 'SMS', accent: '#2e84c4',
    path: '/api/sms', placeholder: 'sending number or text from the message', group: 'people',
    blurb: `Carrier database of text messages people reported as spam (the messages forwarded to 7726).

Search the sender's number to see everything else it sent, or a phrase to find the same lure sent from other numbers. Smishing crews rotate numbers but reuse wording.`,
  },
  {
    id: 'audiolab', title: 'Audio Lab - Voice Analysis', short: 'Audio Lab', glyph: 'AUD', accent: '#c86e28',
    path: '/api/audio', placeholder: 'transcript text, speaker, caller ID or voiceprint', group: 'people',
    blurb: `Analyzes recordings: transcript, the caller ID that was displayed, STIR/SHAKEN attestation, a voiceprint (speaker fingerprint) and a synthetic-voice detector score.

Voice cloning needs a sample of the real person, usually a public talk or video. Search for public recordings of the person the caller claimed to be and compare voiceprints.

Attestation C means the call came in through a gateway and the caller ID was never verified.`,
  },
  {
    id: 'doclab', title: 'Document Lab - Metadata', short: 'Document Lab', glyph: 'DOC', accent: '#786e3c',
    path: '/api/documents', placeholder: 'file name, author, text or SHA-256', group: 'people',
    blurb: `Reads the metadata hidden inside documents: author, last editor, organization, the program that made it, and when.

Forgers polish what the page says and forget what the file says. An official certificate written last week by a private individual in a free editor did not come from an official.

Search an author's name to find their other documents.`,
  },
  {
    id: 'payments', title: 'Payment Account Lookup', short: 'Payments', glyph: 'PAY', accent: '#247846',
    path: '/api/payments', placeholder: 'account number, payment handle, provider or wallet', group: 'people',
    blurb: `Looks up bank accounts, payment-app handles, card merchants, gift-card purchases and crypto wallets.

Gift cards and crypto are what scammers ask for because the payments are hard to reverse. No real bank, government office or support desk asks to be paid in them.

Accounts receiving fraud are often money mules: real people recruited to pass the money along. Follow the money past them.`,
  },
  {
    id: 'moneytrail', title: 'Money Trail - Follow the Funds', short: 'Money Trail', glyph: '$', accent: '#146e3c',
    path: '/api/moneytrail', placeholder: 'account identifier or wallet address (or its start)', group: 'people',
    blurb: `Follows money forward from an account or wallet, one transfer at a time, to where it stopped.

Criminals move stolen funds through several wallets (layering) so the trail looks cold. It usually ends at an exchange deposit address, the point where crypto becomes cash and an identity is on file.

You can type just the first characters of an address; the tool lists the matches.`,
  },
  {
    id: 'complaints', title: 'ScamWatch - Fraud Reports', short: 'ScamWatch', glyph: 'SW', accent: '#aa3c3c',
    path: '/api/complaints', placeholder: 'phone, handle, domain, wallet or keyword', group: 'people',
    blurb: `Reports other victims filed with the ScamWatch fraud portal.

Several reports naming the same number, account or handle show you are looking at an operation, not a one-off. Reports are unverified, and similar stories often come from different crews, so match on indicators, not on the story.`,
  },
  {
    id: 'breach', title: 'Breach Lookup', short: 'Breach Lookup', glyph: 'BR', accent: '#6e4632',
    path: '/api/breach', placeholder: 'exact email address or username', group: 'people',
    blurb: `Searches leaked user tables from breached websites for an exact email address or username.

People reuse emails and usernames for years. An address found in a WHOIS record or a forum's leaked user list can lead to an old gaming or social account, and from there to a real name.

It also explains "I know your password" emails: an old breach is usually where the password came from.

Passwords are never shown, only that a record exists and what it contained.`,
  },
  // ------------------------------------------------------------- reporting
  {
    id: 'websearch', title: 'Web Search', short: 'Web Search', glyph: 'WS', accent: '#208c58',
    path: '/api/websearch', placeholder: 'campaign name, malware family, alias or indicator', group: 'report',
    blurb: `A search over public security writing: blogs, community reports and researcher notes.

This is where attribution comes from. Infrastructure tells you what happened; published reporting tells you who somebody thinks did it.

Try a campaign name. Read carefully: not every article names an actor, and some are about entirely different activity.

Searching an indicator (a handle, a phone number, an account, a wallet) finds any reporting that lists it.`,
  },
  {
    id: 'directory', title: 'Directory - People and Aliases', short: 'Directory', glyph: 'DIR', accent: '#7e6a9c',
    path: '/api/directory', placeholder: 'alias, name or employer', group: 'report',
    blurb: `Directory is a people-search index. It holds two very different kinds of record in one place:

    - threat actor aliases, with their tracked campaigns and infrastructure
    - civilian records

Search an alias you picked up from published reporting. Vendors use different names for the same group.`,
  },
]
