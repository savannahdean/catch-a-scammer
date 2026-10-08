// The Dictionary: every technical word a player meets, in plain English.
// `short` is the hover text wherever the word is underlined; `more` is shown
// in the Dictionary window. `also` lists other spellings to underline (plurals
// are matched automatically). Acronyms, and any `also` spelling with a capital
// letter, only match with that exact capitalisation ("SAN" but not "San Jose").
// `tool` is the app the word is mostly used in; `see` links to other entries;
// `not` lists phrases where the word means something else (a university
// registrar is not a domain registrar).

export type TermCategory = 'scams' | 'web' | 'email' | 'files' | 'phones' | 'people' | 'money' | 'investigation'

export interface Term {
  id: string
  term: string
  also?: string[]
  cat: TermCategory
  short: string
  more?: string
  tool?: string
  see?: string[]
  /** phrases that contain the word but mean something else; never underlined */
  not?: string[]
  /** when set, the only spellings underlined, each in exactly this case */
  match?: string[]
}

export const CATEGORY_LABEL: Record<TermCategory, string> = {
  scams: 'Types of scams',
  web: 'Websites & the internet',
  email: 'Email',
  files: 'Files & malware',
  phones: 'Phones & voice',
  people: 'People & accounts',
  money: 'Money & crypto',
  investigation: 'Investigating',
}

export const TERMS: Term[] = [
  // ------------------------------------------------------------- types of scams
  {
    id: 'phishing', term: 'Phishing', cat: 'scams',
    short: 'A fake message that tricks you into clicking a link, logging in, or handing over information.',
    more: 'The name comes from "fishing": the scammer casts out bait and waits for someone to bite. Most phishing sends you to a fake login page that records whatever you type into it.',
    see: ['lure', 'spear-phishing', 'lookalike-domain', 'phishing-kit'],
  },
  {
    id: 'lure', term: 'Lure', cat: 'scams',
    short: 'The bait in a scam: the message, ad or story written to make you act.',
    more: 'Lures lean on urgency ("within 24 hours"), fear ("your account is locked"), greed ("you have won") or love. Crews reuse the same wording again and again, so a phrase from one lure often finds others.',
    tool: 'sms', see: ['phishing'],
  },
  {
    id: 'spear-phishing', term: 'Spear phishing', also: ['spear-phishing'], cat: 'scams',
    short: 'Phishing aimed at one particular person, using real details about them.',
    more: 'Instead of one message to thousands, the scammer studies the target (often through their public posts) and writes something only they would find believable.',
    see: ['phishing', 'whaling'],
  },
  {
    id: 'whaling', term: 'Whaling', cat: 'scams',
    short: 'Spear phishing that targets, or pretends to be, a company boss.',
    more: 'Usually an "executive" asks someone in finance to send an urgent, confidential payment. The "whale" is the big fish at the top of the company.',
    see: ['bec', 'spear-phishing'],
  },
  {
    id: 'bec', term: 'BEC', also: ['business email compromise'], cat: 'scams',
    short: 'Business Email Compromise: a scammer poses as a boss or supplier by email to get a payment sent to them.',
    more: 'Typical signs: secrecy, urgency, "new bank details", and a sender domain that is one letter off the real company.',
    see: ['whaling', 'lookalike-domain', 'wire-transfer'],
  },
  {
    id: 'clone-phishing', term: 'Clone phishing', cat: 'scams',
    short: 'A copy of a real email or login page you have seen before, "resent" with a bad link swapped in.',
    see: ['phishing', 'favicon'],
  },
  {
    id: 'angler-phishing', term: 'Angler phishing', cat: 'scams',
    short: 'A fake customer-support account replies to your public complaint and asks you to log in or send a code.',
    more: 'Check the account: brand-new, not verified, and a handle slightly different from the real company\'s.',
    tool: 'social', see: ['verified-badge', 'one-time-code', 'handle'],
  },
  {
    id: 'smishing', term: 'Smishing', cat: 'scams',
    short: 'Phishing by text message (SMS + phishing).',
    tool: 'sms', see: ['sms', 'url-shortener', '7726'],
  },
  {
    id: 'vishing', term: 'Vishing', cat: 'scams',
    short: 'Phishing by phone call or voicemail (voice + phishing).',
    tool: 'audiolab', see: ['voice-cloning', 'caller-id-spoofing'],
  },
  {
    id: 'voice-cloning', term: 'Voice cloning', also: ['cloned voice', 'synthetic voice', 'synthetic-voice'], cat: 'scams',
    short: 'Using AI to make a fake recording that sounds like a real person.',
    more: 'It needs a sample of the real voice, usually from a public video or talk. The Audio Lab gives a "synthetic-voice detector" score: closer to 1 means more likely fake.',
    tool: 'audiolab', see: ['voiceprint', 'deepfake', 'vishing'],
  },
  {
    id: 'deepfake', term: 'Deepfake', cat: 'scams',
    short: 'A fake photo, video or voice made with AI to look or sound like a real person.',
    see: ['voice-cloning', 'ai-face'],
  },
  {
    id: 'romance-scam', term: 'Romance scam', also: ['romance scams'], cat: 'scams',
    short: 'A scammer builds a fake relationship online, then starts asking for money.',
    more: 'They never video-call, are always "abroad", and eventually have an emergency only money can fix.',
    tool: 'social', see: ['catfish', 'reverse-image-search', 'pig-butchering'],
  },
  {
    id: 'catfish', term: 'Catfish', also: ['catfishing', 'catfished'], cat: 'scams',
    short: 'Someone pretending to be a different person online, usually with stolen photos.',
    tool: 'reverseimage', see: ['stolen-identity', 'reverse-image-search'],
  },
  {
    id: 'advance-fee', term: 'Advance-fee fraud', also: ['advance-fee', 'advance fee'], cat: 'scams',
    short: 'You are promised a fortune, but first you must pay a "small" fee. Then another. The fortune never exists.',
    more: 'The classic version is the "Nigerian prince" email. Official-looking documents are part of the act; check their metadata.',
    tool: 'doclab', see: ['metadata'],
  },
  {
    id: 'tech-support-scam', term: 'Tech-support scam', also: ['tech support scam', 'tech-support'], cat: 'scams',
    short: 'A fake virus warning tells you to call a "help line", where a scammer takes control or takes payment.',
    more: 'Real companies do not put phone numbers in pop-ups, and never ask to be paid in gift cards.',
    tool: 'phone', see: ['gift-card', 'toll-free'],
  },
  {
    id: 'pig-butchering', term: 'Pig-butchering', also: ['pig butchering'], cat: 'scams',
    short: 'A long, friendly chat that ends with you "investing" in a fake trading site that keeps your money.',
    more: 'The name is the scammers\' own: they "fatten the pig" with weeks of friendship before the "slaughter". The fake site shows huge profits, then demands a "tax" before you can withdraw.',
    tool: 'moneytrail', see: ['crypto-wallet', 'stablecoin'],
  },
  {
    id: 'sextortion', term: 'Sextortion', cat: 'scams',
    short: 'Threatening to share sexual images or a "webcam recording" unless the victim pays.',
    more: 'Mass sextortion emails usually have no recording at all. They quote an old password from a data breach to seem convincing.',
    tool: 'breach', see: ['breach', 'bitcoin'],
  },
  {
    id: 'social-engineering', term: 'Social engineering', cat: 'scams',
    short: 'Manipulating people, not computers: getting someone to hand over access or money by tricking them.',
  },
  {
    id: 'llm', term: 'LLM', also: ['large language model', 'AI chatbot'], cat: 'scams',
    short: 'Large Language Model: AI that writes text, like a chatbot. Scammers use it to write fluent lures in any language.',
    see: ['lure'],
  },
  {
    id: 'one-time-code', term: 'One-time code', also: ['2FA', 'two-factor', 'verification code', 'one-time codes'], cat: 'scams',
    short: 'The short code a site texts you to prove it is really you logging in. Never share it with anyone.',
    more: 'Scammers who already have your password ask for this code so they can get past the second lock.',
  },

  // ------------------------------------------------------ websites & the internet
  {
    id: 'domain', term: 'Domain', also: ['domain name'], cat: 'web',
    short: 'A website\'s name, like example.com. Anyone can buy (register) one for a few dollars.',
    tool: 'intelsearch', see: ['registrar', 'ip-address', 'dns', 'lookalike-domain'],
  },
  {
    id: 'url', term: 'URL', cat: 'web',
    short: 'A full web address, like https://example.com/login. The domain is the part between "//" and the next "/".',
    tool: 'urlscan', see: ['domain', 'redirect'],
  },
  {
    id: 'ip-address', term: 'IP address', also: ['IP', 'IP addresses'], cat: 'web',
    short: 'The number that identifies a computer on the internet, like 203.0.113.42. Domains point at IP addresses.',
    more: 'One IP address can host hundreds of unrelated websites, so sharing an address does not mean sharing an owner.',
    tool: 'intelsearch', see: ['dns', 'co-hosting', 'asn'],
  },
  {
    id: 'dns', term: 'DNS', also: ['Domain Name System'], cat: 'web',
    short: 'The internet\'s phone book: it turns a domain name into the IP address of the server behind it.',
    tool: 'dns', see: ['resolve', 'passive-dns', 'reverse-dns'],
  },
  {
    id: 'resolve', term: 'Resolve', also: ['resolves', 'resolved', 'resolution', 'resolutions', 'resolving'], cat: 'web',
    short: 'When a domain "resolves to" an address, DNS says that is where the website lives.',
    tool: 'dns', see: ['dns'],
  },
  {
    id: 'passive-dns', term: 'Passive DNS', cat: 'web',
    short: 'A history of every address a domain has pointed to, recorded over time, with first-seen and last-seen dates.',
    more: 'Domains move. What a domain points at today may not be where it pointed during the scam, so always compare the dates with the incident.',
    tool: 'dns', see: ['first-seen', 'sinkhole'],
  },
  {
    id: 'reverse-dns', term: 'Reverse DNS', cat: 'web',
    short: 'Asking DNS the other way round: given an IP address, what name does its owner give it?',
    more: 'It often reveals the hosting company or a hint like "edge" or "sinkhole".',
  },
  {
    id: 'nameserver', term: 'Nameserver', also: ['name server', 'nameservers'], cat: 'web',
    short: 'The server that answers DNS questions for a domain. Domains sharing an unusual nameserver may share an owner.',
    tool: 'dns', see: ['dns'],
  },
  {
    id: 'first-seen', term: 'First seen', also: ['first-seen', 'last seen', 'last-seen'], cat: 'investigation',
    short: 'The earliest and latest dates something was observed. Use them to check whether it was active during the scam.',
    see: ['passive-dns', 'timeline'],
  },
  {
    id: 'registrar', term: 'Registrar', cat: 'web',
    short: 'The company that sells and manages domain names (like a shop for website names).',
    tool: 'whois', see: ['registrant', 'whois'],
    not: ["Registrar's Office", 'Office of the Registrar', 'University Registrar'],
  },
  {
    id: 'registrant', term: 'Registrant', also: ['registrant email'], cat: 'web',
    short: 'The person or company who bought (registered) a domain.',
    tool: 'whois', see: ['whois', 'privacy-service'],
  },
  {
    id: 'whois', term: 'WHOIS', cat: 'web',
    short: 'The public record of who registered a domain, when, and through which registrar.',
    more: 'Today most WHOIS records are hidden by a privacy service, but old snapshots sometimes caught the real owner before privacy was switched on.',
    tool: 'whois', see: ['registrant', 'privacy-service'],
  },
  {
    id: 'privacy-service', term: 'Privacy service', also: ['REDACTED FOR PRIVACY', 'WHOIS privacy'], cat: 'web',
    short: 'A service that replaces the domain owner\'s name and email in WHOIS with placeholder text.',
    tool: 'whois', see: ['whois'],
  },
  {
    id: 'lookalike-domain', term: 'Look-alike domain', also: ['lookalike domain', 'look-alike', 'lookalike', 'typosquatting', 'typosquat'], cat: 'web',
    short: 'A domain made to look like a real one at a glance: paypa1.com, micros0ft-support.com, secure-bank-login.com.',
    tool: 'intelsearch', see: ['domain', 'phishing'],
  },
  {
    id: 'hosting', term: 'Hosting', also: ['hosted', 'web host', 'hosting provider', 'Host'], cat: 'web',
    short: 'Renting space on a company\'s servers so your website is online.',
    see: ['co-hosting', 'bulletproof-hosting', 'server'],
  },
  {
    id: 'server', term: 'Server', also: ['servers', 'Server'], cat: 'web',
    short: 'The computer that sends you a website (or receives stolen data). In a scan, "Server" is the software it says it runs.',
    see: ['hosting', 'origin-server'],
  },
  {
    id: 'co-hosting', term: 'Co-hosting', also: ['shared hosting', 'co-hosted', 'co-location', 'co-located', 'shared address'], cat: 'web',
    short: 'Many unrelated websites living on the same IP address. Very common, and NOT proof they share an owner.',
    tool: 'intelsearch', see: ['ip-address', 'attribution', 'red-herring'],
  },
  {
    id: 'bulletproof-hosting', term: 'Bulletproof hosting', also: ['bulletproof'], cat: 'web',
    short: 'A hosting company that ignores abuse complaints and police requests, so criminals favour it.',
    more: 'Different criminal crews rent from the same bulletproof host, so a neighbour on the same address can belong to someone else.',
    see: ['co-hosting', 'abuse-contact'],
  },
  {
    id: 'cdn', term: 'CDN', also: ['content delivery network', 'Content Delivery Network'], cat: 'web',
    short: 'A company that sits in front of millions of websites to make them faster. It hides the real server behind its own addresses.',
    more: 'A CDN address or certificate is shared by thousands of unrelated customers, so it links nothing. Look further back in DNS history for the origin server.',
    tool: 'dns', see: ['edge-server', 'origin-server'],
  },
  {
    id: 'edge-server', term: 'Edge server', cat: 'web',
    short: 'One of a CDN\'s shared front-door servers. Not the attacker\'s machine.',
    see: ['cdn', 'origin-server'],
  },
  {
    id: 'origin-server', term: 'Origin server', also: ['origin IP'], cat: 'web',
    short: 'The real server behind a CDN, where the website actually lives. Usually found in older DNS history.',
    tool: 'dns', see: ['cdn', 'passive-dns'],
  },
  {
    id: 'takedown', term: 'Takedown', also: ['taken down'], cat: 'web',
    short: 'When a scam website is shut down, usually by the registrar or hosting company after a report.',
    see: ['sinkhole'],
  },
  {
    id: 'sinkhole', term: 'Sinkhole', also: ['sinkholed'], cat: 'web',
    short: 'After a takedown, defenders point the scam domain at their own server. That address is NOT the attacker.',
    more: 'A sinkhole is what the domain points to today. To find the attacker, look at what it pointed to during the incident.',
    tool: 'dns', see: ['takedown', 'passive-dns'],
  },
  {
    id: 'asn', term: 'ASN', also: ['autonomous system'], cat: 'web',
    short: 'Autonomous System Number: an ID for the network (usually a company) that owns a block of IP addresses.',
    more: 'It tells you which provider runs an address, which tells you who to send an abuse report to.',
    see: ['ip-address', 'abuse-contact'],
  },
  {
    id: 'abuse-contact', term: 'Abuse contact', cat: 'web',
    short: 'The email address a hosting company publishes for reporting crimes on its network.',
    see: ['bulletproof-hosting'],
  },
  {
    id: 'redirect', term: 'Redirect', also: ['redirects', 'redirected', 'redirection', 'Final URL'], cat: 'web',
    short: 'When one link automatically sends you on to another page. The "final URL" is where you really ended up.',
    tool: 'urlscan', see: ['redirector', 'url-shortener'],
  },
  {
    id: 'redirector', term: 'Compromised redirector', also: ['redirector', 'compromised site'], cat: 'web',
    short: 'A real, innocent website that criminals hacked to bounce visitors on to their scam page.',
    more: 'The first link in the message may point at a genuine small business. That business is a victim too; follow the redirect.',
    tool: 'urlscan', see: ['redirect'],
  },
  {
    id: 'url-shortener', term: 'Shortened link', also: ['link shortener', 'URL shortener', 'short link'], cat: 'web',
    short: 'A short link (like bit.ly/abc) that hides where it really goes until you click it.',
    see: ['redirect', 'smishing'],
  },
  {
    id: 'http-status', term: 'HTTP status', also: ['status code'], cat: 'web',
    short: 'A number a website answers with: 200 = page loaded, 301/302 = redirected elsewhere, 404 = not found.',
    tool: 'urlscan',
  },
  {
    id: 'tls-certificate', term: 'TLS certificate', also: ['TLS', 'SSL', 'HTTPS', 'SSL certificate'], cat: 'web',
    short: 'The digital ID card behind the padlock in your browser. It proves the site owns its name, not that it is honest.',
    more: 'Scam sites have padlocks too. A certificate lists every domain it covers, so one certificate for several domains links them.',
    tool: 'certs', see: ['certificate-transparency', 'certificate-authority'],
  },
  {
    id: 'certificate-transparency', term: 'Certificate transparency', also: ['certificate-transparency', 'CT logs'], cat: 'web',
    short: 'Public logs of every certificate ever issued, so anyone can search which names a certificate covers.',
    tool: 'certs', see: ['tls-certificate'],
  },
  {
    id: 'san', term: 'Subject Alternative Name', also: ['SAN', 'SAN list', 'SANs'], cat: 'web',
    short: 'Subject Alternative Names: the list of every domain one TLS certificate covers.',
    more: 'If one certificate covers several scam domains, the same person almost certainly requested it.',
    tool: 'certs', see: ['tls-certificate'],
  },
  {
    id: 'certificate-authority', term: 'Certificate authority', also: ['Issuer', 'issuer'], cat: 'web',
    short: 'The organisation that issued a certificate (the "Issuer"). Free ones like Let\'s Encrypt take seconds to get.',
    tool: 'certs', see: ['self-signed'],
  },
  {
    id: 'self-signed', term: 'Self-signed', cat: 'web',
    short: 'A certificate the server made for itself instead of getting one from a trusted authority. Browsers warn about it.',
    see: ['certificate-authority'],
  },
  {
    id: 'sandbox', term: 'Sandbox', also: ['sandboxed', 'Sandbox verdict'], cat: 'web',
    short: 'A sealed-off test computer where a link or file is opened safely to see what it does.',
    tool: 'urlscan', see: ['malware'],
  },
  {
    id: 'phishing-kit', term: 'Phishing kit', also: ['phishing kits', 'phishing-kit'], cat: 'web',
    short: 'A ready-made fake login page sold to scammers. Its leftover files can include the crook\'s own email or chat ID.',
    tool: 'urlscan', see: ['phishing'],
  },
  {
    id: 'tracking-id', term: 'Tracking ID', also: ['analytics tracking ID', 'analytics ID', 'tracking IDs'], cat: 'web',
    short: 'A code from a visitor-counting service, pasted into a site. The same ID on two sites usually means the same owner.',
    tool: 'urlscan', see: ['pivot'],
  },
  {
    id: 'favicon', term: 'Favicon', also: ['favicon hash'], cat: 'web',
    short: 'The tiny icon on a browser tab. A shared favicon only means the same brand was copied, not the same scammer.',
    tool: 'urlscan',
  },
  {
    id: 'jarm', term: 'JARM', also: ['JARM fingerprint'], cat: 'web',
    short: 'A fingerprint of how a server sets up secure connections. Matching JARMs suggest the same server setup, and often the same operator.',
    tool: 'urlscan', see: ['fingerprint'],
  },
  {
    id: 'fingerprint', term: 'Fingerprint', also: ['fingerprints'], cat: 'investigation',
    short: 'A detail that is unusual enough to identify one thing (a server, a file, a voice) and spot it again elsewhere.',
    see: ['hash', 'jarm', 'voiceprint'],
  },

  // ------------------------------------------------------------------- email
  {
    id: 'email-headers', term: 'Email headers', also: ['headers', 'raw headers', 'header'], cat: 'email',
    short: 'The hidden "envelope" of an email: which servers handled it, the real sender, and the security checks it passed or failed.',
    see: ['spf', 'dkim', 'dmarc', 'return-path'],
  },
  {
    id: 'display-name', term: 'Display name', also: ['From (display)'], cat: 'email',
    short: 'The friendly name shown on an email ("PayPal Support"). Anyone can type anything here; check the address behind it.',
    see: ['spoofing'],
  },
  {
    id: 'reply-to', term: 'Reply-To', cat: 'email',
    short: 'Where your reply actually goes. Scammers set it to their own address even when "From" looks real.',
    see: ['email-headers'],
  },
  {
    id: 'return-path', term: 'Return-Path', cat: 'email',
    short: 'The address bounced emails go back to. It often reveals the real sending service.',
    see: ['email-headers'],
  },
  {
    id: 'message-id', term: 'Message-ID', cat: 'email',
    short: 'A unique tag the sending system stamps on every email. The part after the @ often names the real system that sent it.',
  },
  {
    id: 'x-mailer', term: 'X-Mailer', cat: 'email',
    short: 'The program that sent the email. Bulk-mailing tools here are a hint it was a mass campaign.',
  },
  {
    id: 'spf', term: 'SPF', cat: 'email',
    short: 'A check of whether the server that sent an email is allowed to send for that domain. "fail" is a red flag.',
    see: ['dkim', 'dmarc'],
  },
  {
    id: 'dkim', term: 'DKIM', cat: 'email',
    short: 'A digital signature on an email proving it really came from the domain it claims and was not changed on the way.',
    see: ['spf', 'dmarc'],
  },
  {
    id: 'dmarc', term: 'DMARC', cat: 'email',
    short: 'The domain owner\'s rule for what to do when SPF and DKIM fail (let it through, send to spam, or reject).',
    see: ['spf', 'dkim'],
  },
  {
    id: 'spoofing', term: 'Spoofing', also: ['spoofed', 'spoof'], cat: 'email',
    short: 'Faking where a message or call comes from, so it looks like someone you trust.',
    see: ['display-name', 'caller-id-spoofing'],
  },
  {
    id: 'disposable-inbox', term: 'Disposable inbox', also: ['disposable email', 'burner email'], cat: 'email',
    short: 'A free throwaway email address that needs no identity. Real businesses do not use them.',
  },
  {
    id: 'pgp-key', term: 'PGP key', cat: 'email',
    short: 'A key for sending encrypted messages. Criminals post theirs on forums, and the same key in two places links two accounts.',
    see: ['pivot'],
  },

  // ---------------------------------------------------------- files & malware
  {
    id: 'malware', term: 'Malware', cat: 'files',
    short: 'Malicious software: any program built to harm you, spy on you, or steal from you.',
    tool: 'malwaredb', see: ['malware-family', 'payload'],
  },
  {
    id: 'malware-family', term: 'Malware family', also: ['families'], cat: 'files',
    short: 'A group of malware samples that are versions of the same program, with one name (like "RavenSteal").',
    tool: 'malwaredb', see: ['commodity-malware'],
  },
  {
    id: 'commodity-malware', term: 'Commodity malware', also: ['malware-as-a-service', 'ransomware-as-a-service'], cat: 'files',
    short: 'Malware sold or rented to anyone who pays. Many unrelated crews use it, so it does not tell you who attacked.',
    tool: 'malwaredb', see: ['attribution'],
  },
  {
    id: 'infostealer', term: 'Information stealer', also: ['infostealer', 'stealer'], cat: 'files',
    short: 'Malware that grabs saved passwords, browser cookies and crypto wallets from a computer and sends them to the criminal.',
  },
  {
    id: 'loader', term: 'Loader', also: ['downloader', 'dropper'], cat: 'files',
    short: 'Small malware whose only job is to get in and then download more malware.',
  },
  {
    id: 'rat', term: 'Remote access trojan', also: ['RAT'], cat: 'files',
    short: 'Malware that lets a criminal control your computer from far away, as if sitting in front of it.',
  },
  {
    id: 'trojan', term: 'Trojan', also: ['banking trojan'], cat: 'files',
    short: 'Malware disguised as something harmless. A banking trojan secretly alters your bank\'s pages to steal logins or money.',
  },
  {
    id: 'ransomware', term: 'Ransomware', cat: 'files',
    short: 'Malware that locks up your files and demands payment to unlock them.',
  },
  {
    id: 'keylogger', term: 'Keylogger', cat: 'files',
    short: 'Malware that records every key you press, including passwords.',
  },
  {
    id: 'payload', term: 'Payload', also: ['payloads', 'staged'], cat: 'files',
    short: 'The harmful file a scam delivers. "Staged" on a domain means it was placed there, ready to download.',
    tool: 'malwaredb', see: ['malware'],
  },
  {
    id: 'beacon', term: 'Beacon', also: ['beacons', 'beaconing'], cat: 'files',
    // "Beacon" is also a word in generated campaign names ("Operation Gilded Beacon")
    match: ['beacon', 'beacons', 'beaconing', 'BEACONING'],
    short: 'When malware on an infected computer "phones home" to the criminal\'s server to report in and get orders.',
    see: ['c2'],
  },
  {
    id: 'c2', term: 'C2', also: ['command and control', 'command-and-control', 'C&C'], cat: 'files',
    short: 'Command and control: the criminal\'s server that infected computers report to and take orders from.',
    see: ['beacon', 'extracted-config'],
  },
  {
    id: 'hash', term: 'Hash', also: ['hashes', 'file hash'], cat: 'files',
    short: 'A file\'s unique fingerprint: a long code calculated from its contents. Change one byte and the hash changes completely.',
    more: 'Searching a hash finds the exact same file anywhere else it was seen.',
    tool: 'malwaredb', see: ['sha256', 'md5', 'perceptual-hash'],
  },
  {
    id: 'sha256', term: 'SHA-256', also: ['SHA256'], cat: 'files',
    short: 'The most common kind of file hash: 64 letters and digits.',
    tool: 'malwaredb', see: ['hash'],
  },
  {
    id: 'md5', term: 'MD5', cat: 'files',
    short: 'An older, shorter kind of file hash (32 characters). Still widely used to look files up.',
    tool: 'malwaredb', see: ['hash'],
  },
  {
    id: 'imphash', term: 'Import hash', also: ['imphash'], cat: 'files',
    short: 'A hash of the list of system functions a program uses. Different builds from the same toolkit often share one.',
    tool: 'malwaredb', see: ['hash'],
  },
  {
    id: 'antivirus', term: 'Antivirus detections', also: ['antivirus', 'detections'], cat: 'files',
    short: 'How many security products flag the file as harmful, and what name each one gives it.',
    tool: 'malwaredb',
  },
  {
    id: 'yara', term: 'YARA', also: ['YARA rule', 'YARA rules', 'YARA match', 'YARA matches'], cat: 'files',
    short: 'Search patterns researchers write to recognise a malware family. A match says "this looks like X".',
    more: 'Matches can be faked: anyone can plant text that a famous group\'s YARA rule looks for.',
    tool: 'malwaredb', see: ['strings', 'false-flag'],
  },
  {
    id: 'strings', term: 'Strings', also: ['strings of interest'], cat: 'files',
    short: 'Readable text found inside a program file: web addresses, error messages, sometimes a name the author left behind.',
    more: 'A string naming a famous hacking group is trivial to plant, and proves nothing on its own.',
    tool: 'malwaredb', see: ['false-flag'],
  },
  {
    id: 'extracted-config', term: 'Extracted configuration', also: ['configuration'], cat: 'files',
    short: 'Settings pulled out of a malware file, such as the C2 address it reports to. Often the best lead in the file.',
    tool: 'malwaredb', see: ['c2'],
  },
  {
    id: 'metadata', term: 'Metadata', cat: 'files',
    short: 'Hidden information stored inside a file: who made it, with what program, and when.',
    more: 'Forgers polish what the page says and forget what the file says.',
    tool: 'doclab', see: ['exif', 'exiftool'],
  },
  {
    id: 'exif', term: 'EXIF', cat: 'files',
    short: 'Metadata cameras and phones add to photos: camera model, date taken, sometimes GPS location.',
    tool: 'doclab', see: ['metadata'],
  },
  {
    id: 'exiftool', term: 'exiftool', cat: 'files',
    short: 'A free program investigators use to read the metadata inside files.',
    tool: 'doclab', see: ['metadata'],
  },
  {
    id: 'creator-tool', term: 'Creator Tool', also: ['Last Modified By'], cat: 'files',
    short: 'Metadata naming the program (and person) that made or last edited a document.',
    tool: 'doclab', see: ['metadata'],
  },

  // ----------------------------------------------------------- phones & voice
  {
    id: 'carrier', term: 'Carrier', cat: 'phones',
    short: 'The phone company that issued a number.',
    tool: 'phone', see: ['line-type'],
  },
  {
    id: 'line-type', term: 'Line type', cat: 'phones',
    short: 'What kind of number it is: mobile, landline, VoIP (internet phone), toll-free, or a short code.',
    tool: 'phone', see: ['voip', 'toll-free', 'short-code'],
  },
  {
    id: 'voip', term: 'VoIP', also: ['Voice over IP'], cat: 'phones',
    short: 'A phone number that runs over the internet. It can be rented in minutes, from anywhere, and dropped just as fast.',
    tool: 'phone', see: ['line-type'],
  },
  {
    id: 'toll-free', term: 'Toll-free', also: ['toll free', 'toll_free'], cat: 'phones',
    short: 'A number that is free for the caller (like 1-800). Easy to rent, and loved by fake "support desks".',
    tool: 'phone',
  },
  {
    id: 'short-code', term: 'Short code', also: ['SMS short code', 'short_code'], cat: 'phones',
    short: 'A 5- or 6-digit number companies use to send texts. Real ones are registered and vetted.',
    tool: 'sms',
  },
  {
    id: 'caller-id', term: 'Caller ID', also: ['caller-ID', 'Caller ID displayed'], cat: 'phones',
    short: 'The number (and name) that appears on your phone when someone calls. It is easy to fake.',
    tool: 'phone', see: ['caller-id-spoofing', 'cnam', 'stir-shaken'],
  },
  {
    id: 'caller-id-spoofing', term: 'Caller-ID spoofing', also: ['caller ID spoofing'], cat: 'phones',
    short: 'Faking the number that shows on the victim\'s phone. A number the scammer told them to call back is a far better lead.',
    tool: 'phone', see: ['caller-id', 'spoofing'],
  },
  {
    id: 'cnam', term: 'CNAM', also: ['Caller-ID name'], cat: 'phones',
    short: 'Caller ID Name: the name on file for a number, shown on some phones when it calls.',
    tool: 'phone', see: ['caller-id'],
  },
  {
    id: 'stir-shaken', term: 'STIR/SHAKEN', also: ['attestation', 'Attestation'], cat: 'phones',
    short: 'A system phone companies use to vouch for caller ID. A = verified, B = caller known but not the number, C = not verified at all.',
    more: 'Attestation C means the call came in through a gateway from another network and nobody checked the number it claimed.',
    tool: 'audiolab', see: ['caller-id', 'gateway'],
  },
  {
    id: 'gateway', term: 'Gateway', cat: 'phones',
    short: 'Where a call enters a phone network from somewhere else (often overseas or the internet), so its caller ID cannot be checked.',
    see: ['stir-shaken'],
  },
  {
    id: 'sms', term: 'SMS', cat: 'phones',
    short: 'An ordinary text message.',
    tool: 'sms', see: ['smishing'],
  },
  {
    id: '7726', term: '7726', cat: 'phones',
    short: 'The number you forward spam texts to in many countries. It spells SPAM on a phone keypad.',
    tool: 'sms',
  },
  {
    id: 'voiceprint', term: 'Voiceprint', also: ['voice print'], cat: 'phones',
    short: 'A fingerprint of someone\'s voice. Two recordings with matching voiceprints are the same speaker, or a clone of them.',
    tool: 'audiolab', see: ['voice-cloning', 'fingerprint'],
  },

  // -------------------------------------------------------- people & accounts
  {
    id: 'handle', term: 'Handle', also: ['username', 'usernames', '@handle'], cat: 'people',
    short: 'The name someone uses online, like @night_owl. People reuse the same one for years across many sites.',
    tool: 'social', see: ['lookalike-handle', 'breach'],
  },
  {
    id: 'lookalike-handle', term: 'Look-alike handle', also: ['similar handle'], cat: 'people',
    short: 'A username one character off another (night_owl vs night_owl_). Usually a different person.',
    more: 'Look for a real link between two accounts: the same photo, the same email, the same bio link.',
    tool: 'social', see: ['handle', 'red-herring'],
  },
  {
    id: 'persona', term: 'Persona', also: ['personas'], cat: 'people',
    short: 'A made-up identity a scammer plays, with a name, photos, job and backstory.',
    see: ['catfish', 'stolen-identity'],
  },
  {
    id: 'alias', term: 'Alias', also: ['aliases', 'a.k.a.'], cat: 'people',
    short: 'Another name for the same person or group. Security companies often give one hacking group different names.',
    tool: 'directory', see: ['vendor-naming', 'threat-actor'],
  },
  {
    id: 'stolen-identity', term: 'Stolen identity', also: ['stolen photos', 'stolen photo'], cat: 'people',
    short: 'Using a real person\'s photos or details for a fake account. The real person is a victim too.',
    tool: 'reverseimage', see: ['reverse-image-search', 'catfish'],
  },
  {
    id: 'reverse-image-search', term: 'Reverse image search', also: ['Reverse Image'], cat: 'people',
    short: 'Searching with a picture instead of words, to find everywhere else it has appeared online, oldest first.',
    tool: 'reverseimage', see: ['perceptual-hash', 'stolen-identity'],
  },
  {
    id: 'perceptual-hash', term: 'Perceptual hash', also: ['phash'], cat: 'people',
    short: 'A fingerprint of what an image looks like. It still matches after the picture is resized, cropped a little or recompressed.',
    tool: 'reverseimage', see: ['hash', 'reverse-image-search'],
  },
  {
    id: 'ai-face', term: 'AI-generated face', also: ['AI-face detector', 'AI-generated', 'generated face', 'AI-face'], cat: 'people',
    short: 'A photo of a person who does not exist, made by AI. It has no earlier copies to find. The detector score near 1 means likely fake.',
    tool: 'reverseimage', see: ['deepfake'],
  },
  {
    id: 'account-age', term: 'Account age', also: ['Account created', 'account created'], cat: 'people',
    short: 'How long an account has existed. A profile created days before it contacted the victim is a red flag.',
    tool: 'social',
  },
  {
    id: 'verified-badge', term: 'Verified badge', also: ['Verified'], cat: 'people',
    short: 'The tick a platform puts on accounts it has checked belong to who they say. Fake support accounts don\'t have it.',
    tool: 'social', see: ['angler-phishing'],
  },
  {
    id: 'dm', term: 'DM', also: ['direct message', 'direct messages', 'DMs'], cat: 'people',
    short: 'A direct message: a private chat on a social platform, rather than a public post.',
    tool: 'social',
  },
  {
    id: 'criminal-forum', term: 'Criminal forum', also: ['criminal forums', 'forum', 'forums', 'darknet market'], cat: 'people',
    short: 'A website where criminals buy and sell tools, stolen data and services, and advertise under their handles.',
    tool: 'social', see: ['aged-profiles', 'handle'],
  },
  {
    id: 'aged-profiles', term: 'Aged profiles', also: ['aged accounts'], cat: 'people',
    short: 'Old social-media accounts sold to scammers, because an old account looks more trustworthy than a new one.',
    tool: 'social', see: ['account-age', 'criminal-forum'],
  },
  {
    id: 'breach', term: 'Data breach', also: ['breach', 'breaches', 'breached', 'breach data'], cat: 'people',
    short: 'When a website is hacked and its user list (emails, usernames, sometimes passwords) leaks online.',
    more: 'Old breaches are how sextortion emails "know your password", and how an investigator links an email to an old account.',
    tool: 'breach', see: ['credential-reuse', 'sextortion'],
  },
  {
    id: 'credential-reuse', term: 'Password reuse', also: ['credential reuse', 'credential stuffing'], cat: 'people',
    short: 'Using the same password (or email and username) on many sites, so one breach unlocks or links them all.',
    tool: 'breach', see: ['breach'],
  },
  {
    id: 'utc', term: 'UTC', also: ['Active hours suggest', 'time zone'], cat: 'people',
    short: 'The world\'s reference clock. "UTC+3" means three hours ahead of it, a hint at where someone lives from when they are online.',
  },

  // ----------------------------------------------------------- money & crypto
  {
    id: 'money-mule', term: 'Money mule', also: ['mule', 'mules', 'mule account', 'money-mule'], cat: 'money',
    short: 'A real person, often tricked or paid, who receives stolen money into their own account and passes it on.',
    more: 'The mule is not the boss. Follow the money past them.',
    tool: 'payments', see: ['drop-account', 'layering'],
  },
  {
    id: 'drop-account', term: 'Drop account', also: ['drop accounts'], cat: 'money',
    short: 'A bank account criminals use to receive stolen money, often opened by a mule or with a stolen identity.',
    tool: 'payments', see: ['money-mule'],
  },
  {
    id: 'cashout', term: 'Cash-out', also: ['cashout', 'cash out', 'cashout service', 'cash-out point'], cat: 'money',
    short: 'Turning stolen money or crypto into cash the criminal can spend. Usually the riskiest step for them.',
    tool: 'moneytrail', see: ['exchange'],
  },
  {
    id: 'wire-transfer', term: 'Wire transfer', cat: 'money',
    short: 'A direct bank-to-bank payment. Fast and very hard to reverse once sent.',
    tool: 'payments',
  },
  {
    id: 'gift-card', term: 'Gift card', also: ['gift cards', 'gift-card'], cat: 'money',
    short: 'Scammers ask for gift-card codes because they spend like cash and cannot be traced back. No real business asks to be paid in them.',
    tool: 'payments',
  },
  {
    id: 'merchant', term: 'Merchant', also: ['card merchant', 'merchant account'], cat: 'money',
    short: 'The business name that appears on a card statement when you pay. A fake "age check" often charges through an unknown merchant.',
    tool: 'payments',
  },
  {
    id: 'crypto', term: 'Cryptocurrency', also: ['crypto'], cat: 'money',
    short: 'Digital money like Bitcoin. Payments cannot be reversed, which is why scammers love it.',
    tool: 'moneytrail', see: ['crypto-wallet', 'blockchain'],
  },
  {
    id: 'bitcoin', term: 'Bitcoin', also: ['BTC'], cat: 'money',
    short: 'The best-known cryptocurrency.',
    tool: 'moneytrail', see: ['crypto'],
  },
  {
    id: 'stablecoin', term: 'Stablecoin', also: ['USDT', 'Tether', 'TRC-20', 'Tron'], cat: 'money',
    short: 'A cryptocurrency pegged to a normal currency (1 USDT is about 1 US dollar). USDT on the Tron network is popular with scammers.',
    tool: 'moneytrail', see: ['crypto'],
  },
  {
    id: 'crypto-wallet', term: 'Crypto wallet', also: ['wallet', 'wallets', 'wallet address', 'crypto address', 'crypto addresses'], cat: 'money',
    short: 'An account for holding crypto, identified by a long address. Anyone can make one, without giving a name.',
    tool: 'moneytrail', see: ['blockchain', 'exchange'],
  },
  {
    id: 'blockchain', term: 'Blockchain', also: ['Chain'], cat: 'money',
    short: 'The public record of every crypto transfer ever made. Names are hidden, but anyone can follow the money from wallet to wallet.',
    tool: 'moneytrail', see: ['crypto-wallet'],
  },
  {
    id: 'layering', term: 'Layering', cat: 'money',
    short: 'Moving stolen money through many accounts or wallets to make the trail hard to follow.',
    tool: 'moneytrail', see: ['money-mule', 'exchange'],
  },
  {
    id: 'exchange', term: 'Crypto exchange', also: ['exchange deposit address', 'deposit address', 'exchanges'], cat: 'money',
    short: 'A company that swaps crypto for normal money. It must check customers\' ID, so the trail often ends at a real name on file.',
    tool: 'moneytrail', see: ['kyc', 'cashout'],
  },
  {
    id: 'kyc', term: 'KYC', also: ['know your customer', 'identity on file'], cat: 'money',
    short: '"Know Your Customer": the ID checks banks and exchanges must do. It is why police can ask them who owns an account.',
    see: ['exchange'],
  },
  {
    id: 'escrow', term: 'Escrow', cat: 'money',
    short: 'A middleman who holds the payment until both sides are happy. Criminal forums use it so crooks can trade without trusting each other.',
    see: ['criminal-forum'],
  },
  {
    id: 'cluster', term: 'Cluster', also: ['Cluster label', 'clustered'], cat: 'money',
    short: 'A group of wallets that analysis shows are controlled by the same owner, such as one exchange.',
    tool: 'moneytrail', see: ['exchange'],
  },

  // ----------------------------------------------------------- investigating
  {
    id: 'osint', term: 'OSINT', also: ['open-source intelligence', 'open source intelligence'], cat: 'investigation',
    short: 'Open-Source INTelligence: investigating using information anyone can legally find, like public records and posts.',
  },
  {
    id: 'indicator', term: 'Indicator', also: ['indicators', 'IOC', 'IOCs', 'indicator of compromise'], cat: 'investigation',
    short: 'A specific, searchable clue: a domain, IP address, phone number, email, wallet or file hash.',
    more: 'Match cases on indicators, not on stories. Many scams sound alike; few share the same phone number.',
    see: ['pivot'],
  },
  {
    id: 'pivot', term: 'Pivot', also: ['pivots', 'pivoting', 'pivoted'], cat: 'investigation',
    short: 'Taking one clue and searching it somewhere else to find the next clue. Domain → its address → other sites there, and so on.',
    see: ['indicator'],
  },
  {
    id: 'threat-intelligence', term: 'Threat intelligence', also: ['threat-intelligence', 'threat intel'], cat: 'investigation',
    short: 'Collected knowledge about attackers: their tools, addresses and habits, gathered so defenders can spot them.',
    tool: 'intelsearch',
  },
  {
    id: 'threat-actor', term: 'Threat actor', also: ['threat actors', 'actor', 'actors', 'crew', 'crews'], cat: 'investigation',
    short: 'The person or group behind an attack. Security companies give groups code names like GLASS HERON.',
    tool: 'directory', see: ['alias', 'campaign', 'attribution'],
  },
  {
    id: 'campaign', term: 'Campaign', also: ['campaigns'], cat: 'investigation',
    short: 'A run of attacks by the same group, with the same goal, over a period of time.',
    tool: 'websearch', see: ['threat-actor'],
  },
  {
    id: 'attribution', term: 'Attribution', also: ['attribute', 'attributed', 'attributes'], cat: 'investigation',
    short: 'Deciding who is behind an attack. It needs several independent links, not one coincidence.',
    more: 'Shared hosting, commodity malware and planted strings are not attribution. Overlapping infrastructure, money and accounts are.',
    tool: 'websearch', see: ['co-hosting', 'false-flag', 'source-reliability'],
  },
  {
    id: 'vendor-naming', term: 'Vendor naming', also: ['vendor', 'vendors'], cat: 'investigation',
    short: 'Each security company ("vendor") gives the same hacking group its own name, so one group can have three names.',
    tool: 'directory', see: ['alias'],
  },
  {
    id: 'source-reliability', term: 'Source reliability', also: ['reliability', 'low-reliability'], cat: 'investigation',
    short: 'A grade for how trustworthy a source has been: A completely reliable, B usually, C fairly, D not usually, E unreliable, F cannot judge.',
    more: 'A D- or E-rated blog that confidently blames a famous group is a lead to check, not proof.',
    tool: 'websearch', see: ['attribution'],
  },
  {
    id: 'false-flag', term: 'False flag', also: ['planted', 'decoy', 'decoys'], cat: 'investigation',
    short: 'Clues deliberately left to blame someone else, like text in malware naming a famous hacking group.',
    see: ['red-herring', 'attribution'],
  },
  {
    id: 'red-herring', term: 'Red herring', also: ['red herrings'], cat: 'investigation',
    short: 'Something that looks like a clue but belongs to a different case or nobody at all. Pinning one costs points.',
    see: ['false-flag', 'co-hosting'],
  },
  {
    id: 'infrastructure', term: 'Infrastructure', cat: 'investigation',
    short: 'The domains, servers, phone numbers and accounts a scam runs on.',
    see: ['indicator', 'attribution'],
  },
  {
    id: 'timeline', term: 'Timeline', cat: 'investigation',
    short: 'When things happened. The single best test of whether a clue belongs to your case: was it active at the time of the incident?',
    see: ['first-seen', 'passive-dns'],
  },
]

export const TERM_BY_ID: Record<string, Term> = Object.fromEntries(TERMS.map((t) => [t.id, t]))
