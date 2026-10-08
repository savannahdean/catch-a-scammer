# Catch a Scammer: Game Wiki & Answer Key

> **Spoilers.** This page explains how every case is built and how to solve it. It's meant for the team, instructors and playtesters. Don't hand it to a study participant before they play.

Everything in the game is fictional: people, companies, domains (`.example` / `.test` only), IP addresses (reserved documentation ranges) and phone numbers (the 555‑01xx fiction block).

**Contents**

1. [How a case works](#1-how-a-case-works)
2. [The tools](#2-the-tools)
3. [Your client: the Messenger and personalities](#3-your-client-the-messenger-and-personalities)
4. [Difficulty](#4-difficulty)
5. [Scoring](#5-scoring)
6. [Types of scams (player-facing overview)](#6-types-of-scams)
7. [Answer key: every scenario](#7-answer-key-every-scenario)
8. [Unmasking the real person (HARD and EXPERT)](#8-unmasking-the-real-person-hard-and-expert)
9. [Traps that appear in every case](#9-traps-that-appear-in-every-case)

---

## 1. How a case works

New players are offered a **tutorial** the first time they reach the desktop (replay it from Start menu → TUTORIAL). It walks them through one real EASY bulk-phishing case with the Super sweet client, step by step, ticking each step off as they do it: briefing → client → email → domain → DNS History → IP at incident time → campaign → threat actor → Evidence Map → report.

1. **CaseDesk** hands you a case: a briefing, plus the **exhibits** the client gave you (the email, text, profile, voicemail or page they saw, and sometimes payment details).
2. **Messenger**: the client (the person who reported it) is a chat contact. Question them. Some hold back the embarrassing part.
3. **Tools**: every record links to the next tool (a domain to DNS history, a profile to reverse image search, an account to the money trail). Each case is generated fresh, so names, accounts and infrastructure differ every time.
4. **Evidence**: press **ADD TO EVIDENCE** on the records that connect the first exhibit to your conclusions. The **Evidence Map** draws them and their neighbours.
5. **Case Report**: one dropdown per conclusion the scenario asks for. A dropdown only lists records of that kind **you have actually found**, so you can't guess from a list.

A case ends when your report is accepted (**SOLVED**) or when your client runs out of patience and withdraws it (**FAILED**, MEDIUM and up). Either way CaseDesk then shows what really happened, and the Messenger lists what the client was hiding and whether you found it.

---

## 2. The tools

| Window | What it searches | What a real analyst uses it for |
|---|---|---|
| **CaseDesk** | the case | the briefing, the client's exhibits, hints, a new case |
| **Messenger** | the client | what happened, when, what they clicked, what they paid, what they're leaving out |
| **Dictionary** (F2) | technical words | plain-English meanings. Any word with a dotted underline is in it: hover for the short meaning, click for the entry |
| **IntelSearch** | domains, URLs, IPs, malware names | a domain's IPs and staged payloads; an IP's hosting, reputation and co-hosted domains |
| **DNS History** | passive DNS | where a domain pointed *at the time of the incident* (not today) |
| **WHOIS History** | registration snapshots, registrant emails | early snapshots that leaked the registrant before privacy was switched on |
| **CertSearch** | certificate transparency | certificates covering several of the attacker's domains at once |
| **URL Scanner** | page scans | redirects, page title, kit leftovers, tracking ID / favicon / JARM pivots |
| **MalwareDB** | families, hashes, file names | detections, YARA, strings (where false flags hide), C2 config |
| **Social Search** | profiles, posts, DMs | account age, handle reuse across platforms, who wrote a message |
| **Reverse Image** | image ID or perceptual hash | the oldest copy of a photo (its real owner) and the AI-face score |
| **Phone Lookup** | phone numbers | carrier, VoIP vs mobile, caller-ID name, spam reports |
| **Spam Texts** | reported SMS | everything a number sent; the same lure from other numbers |
| **Audio Lab** | recordings | transcript, STIR/SHAKEN, voiceprint, synthetic-voice score |
| **Document Lab** | documents | exiftool-style metadata (author, tool, dates) that exposes forgers |
| **Payments** | accounts, handles, gift cards, merchants, wallets | mule flags, account age, the name on the account |
| **Money Trail** | an account or wallet | transfers hop by hop to the cash-out (a recursive SQL query) |
| **ScamWatch** | other victims' reports | corroboration, and indicators other victims listed |
| **Breach Lookup** | exact email or username | old breaches: reused usernames, and where "I know your password" comes from |
| **Web Search** | vendor reports, blogs, news | attribution: which group a vendor *says* is behind a campaign |
| **Directory** | actor aliases, people | the same actor under different vendor names; the real person on HARD |
| **Evidence Map** | your pinned evidence | the relationship graph of what you pinned and its neighbours |
| **Case Report** | your findings | the final answer |

---

## 3. Your client: the Messenger and personalities

### How the client understands you

The client is a keyword engine, not an AI chatbot (see `backend/server/messenger.py`). It recognizes **intents** in what you type:

| Intent | Example words |
|---|---|
| story | what happened, tell me, explain, walk me through |
| when | when, what time, date, yesterday |
| contact | email, text, message, DM, reply |
| link | link, click, website, page, popup |
| login | password, login, signed in, code |
| money | pay, paid, money, wire, gift card, bitcoin, charge, deposit |
| amount | how much, amount, total |
| device | download, install, file, remote, computer, webcam |
| who | who, name, profile, photo, boyfriend |
| phone | phone, number, call, voicemail |
| **pressure** | anything else, leaving out, be honest, truth, lying, whole story |
| social | hi, thanks, sorry, I'm working on it (reassure), you should... (advice), who do you think did it (theory) |

Each scenario also gives its facts their own keywords ("zip", "gift cards", "deposit address"). A message that hits a fact's own keyword is a **direct** question; one that only hits the topic is a **vague** one.

- An understood question with no matching fact gets "No, nothing like that." at no cost.
- A message the engine can't place at all gets the personality's confused reply. The rude client says **"what the hell are you saying"**, and it costs patience.
- **SHOW EVIDENCE** sends the client a record from your evidence board. They confirm records they recognize ("that's the one"), reject the ones they know are wrong, and a **liar admits the truth when you show proof**.

### The secret

Every scenario has one thing the client may hide (listed per scenario below). How it comes out depends on personality:

| Rule | Personalities | How to get it |
|---|---|---|
| **upfront** | Super sweet, Way too honest | Touch the topic once. |
| **asked** | Not tech-savvy, Anxious, Busy executive, Know-it-all | Ask directly (use the fact's words), or ask "is there anything else?", or ask about the topic twice. |
| **pressed** | Embarrassed, Extremely rude | They dodge the first time. Ask again **directly** or **push** ("are you leaving something out?") and it comes out. |
| **proof** | Liar | Asking gets the lie, again and again. Pushing makes them deny it and costs patience. **Show them a record that proves it** (the scenario's proof list). |

When a secret comes out, the client often **hands over records** (an account, a deposit address, a URL). Those were held back from the CaseDesk exhibits until then.

### The personalities

Numbers come from the `client_profiles` table (migration 008), so you can retune them with an `UPDATE`.

| Personality | Patience | Unclear msg | Wrong pin | Wrong report | Chases you? | Rule | Opening | Dealt on |
|---|---|---|---|---|---|---|---|---|
| Super sweet | 100 | -1 | -2 | -5 | never | upfront | tells the whole story | easy |
| Way too honest | 90 | -2 | -3 | -8 | never | upfront | whole story **plus irrelevant details** (noise) | easy, medium |
| Not tech-savvy | 90 | -2 | -3 | -8 | after 10 min, -2 | asked | short story, confuses computer words | easy, medium |
| Anxious | 70 | -4 | -6 | -15 | after 2.5 min, 2 messages, -2 | asked | whole story, panicky | medium, hard |
| Busy executive | 60 | -6 | -8 | -20 | after 3 min, -4 | asked | terse, wants status updates | medium, hard |
| Know-it-all | 65 | -5 | -4 | -20 | after 5 min, -3 | asked | pushes a **wrong theory** (a decoy actor or look-alike account) | medium, hard, expert |
| Embarrassed | 70 | -4 | -6 | -15 | after ~7 min, -3 | pressed | short story, awkward | medium, hard, expert |
| Liar | 60 | -5 | -8 | -20 | after 5 min, -3 | proof | short story, "it's straightforward" | hard, expert |
| Extremely rude | 35 | -8 | -10 | -25 | after **75 s**, **3 messages**, -5 | pressed | no story, gives you a time limit | hard, expert |

You can pick the client on the new-case screen, or leave it on "Random for the difficulty".

### The mood meter

| Event | Effect |
|---|---|
| A message the client can't understand | − unclear-message cost |
| Insulting the client | − at least 3 |
| Pinning a record the client **knows** is wrong (a red-herring profile, number, message or account) | − wrong-pin cost, and they message you about it ("why is that in my case file?") |
| A returned (wrong) Case Report | − wrong-report cost |
| Leaving a client who chases you without a reply | each chase − its cost (at most 3 chases are applied at once) |
| Pushing a liar, or pushing the rude client before they're ready | − pressure cost |
| Learning something new | +1 per new fact, +3 when they tell their secret, +2 when proof makes them admit it |
| "I'm working on it" (reassure) | +2 (not for the rude client), at most once a minute; it also resets the chase timer |
| Apologizing | +1 |

At 30% they warn you. **At 0, from MEDIUM up, the client withdraws the case** and it closes as FAILED. On EASY the meter can reach zero but the client never leaves.

Clients who chase you show a countdown in the Messenger ("expects a reply in 0:42"). Any message to them resets it. Chases are computed lazily by the server whenever the chat is read, so they keep counting even while the Messenger is closed.

---

## 4. Difficulty

From the `difficulty_profiles` table (change it with SQL, no code needed):

| Knob | Easy | Medium | Hard | Expert |
|---|---|---|---|---|
| Sibling (extra) attacker domains | 1 | 2 | 3 | 4 |
| Benign co-hosted domains per IP | 2 | 5 | 10 | 18 |
| Chance the domain hides behind a CDN | 0 | 0.2 | 0.5 | 0.8 |
| Chance WHOIS privacy is on | 0.3 | 0.6 | 0.8 | 1.0 |
| Stale-DNS trap domains | 0 | 1 | 2 | 3 |
| Compromised redirector in the link (bulk phishing) | no | yes | yes | yes |
| Commodity malware (shared by many actors) | no | no | yes | yes |
| False flags (planted strings, YARA, a blamed decoy actor) | no | no | yes | yes |
| Low-reliability blogs blaming a decoy actor | 0 | 1 | 2 | 3 |
| Unmask the real person | no | no | **yes** | **yes** |
| Hints available | 5 | 4 | 3 | 2 |
| Base score | 1000 | 1500 | 2500 | 4000 |
| Client can withdraw the case | no | yes | yes | yes |

Also by difficulty: fresh attacker infrastructure is labelled *malicious* on EASY, *suspicious* on MEDIUM and *unknown* on HARD/EXPERT, because real threat feeds rarely flag new infrastructure in time. On HARD and EXPERT a wrong report only says **how many** fields were right, not which. In pig-butchering the wallet chain is 2, 3 or 4 hops long.

---

## 5. Scoring

From `backend/server/scoring.py`:

- Each correct conclusion earns its share of the base score. The actor is worth 30%, the real person 20% (HARD+), and the other fields split the rest.
- **−10% of base** for each correct conclusion your pinned evidence doesn't connect to. The grader walks your evidence from the initial clue with a recursive SQL query; DNS links only count if they were live within ±2 days of the incident.
- **−5% of base** per red herring or false flag on your board (counts at most 6).
- **−15% of base** per earlier wrong submission.
- Hints cost 50, 100, 150... points (hint *n* costs 50·n).
- The score never goes below 0.

After a solved case, the analyst feedback lists misleading evidence on your board, unsupported conclusions, disconnected records, hint costs, and **anything the client never told you**.

---

## 6. Types of scams

A player-safe overview of the twelve scenarios: what the scam is and the red flags to watch for.

| Scam | What it is | Red flags in real life |
|---|---|---|
| **Bulk phishing** | One lure sent to thousands, often machine-translated into many languages | Urgency ("verify within 24h"), a sender name that doesn't match the address, links to look-alike domains |
| **Spear phishing** | A message tailored with details from your own public posts | It mentions something real about you, but arrives from an address you don't know |
| **Whaling / BEC** | An "executive" asks finance staff for a confidential urgent wire | Secrecy, urgency, new bank details, a domain one letter off |
| **Clone phishing** | A pixel-perfect copy of a real email or login page, "resent" | A resend you didn't ask for; the page looks right but the address bar doesn't |
| **Angler phishing** | A fake support account answers your public complaint | The "support" account is new, unverified, and asks you to log in through its link or DM a code |
| **Smishing** | Phishing by text message | Casual texts from an unknown number with a shortened link |
| **Vishing (voice cloning)** | A phone call or voicemail in a cloned voice of someone you trust | Urgency, a call-back number you've never seen, a payment request by phone |
| **Romance / catfishing** | A fake partner built from someone else's photos | Never video-calls, always abroad, eventually needs money |
| **Advance-fee ("prince")** | Promise of a fortune after a small fee | Unsolicited windfall, official-looking documents, fee after fee |
| **Tech-support** | A fake virus warning sends you to a fake help line | A pop-up that won't close, a phone number to call, payment in gift cards |
| **Pig-butchering** | A slow-built friendship leads to a fake investment platform | Big "returns" you can't withdraw, a "tax" to unlock them, crypto deposits |
| **Adult-site ad & sextortion** | An ad on an adult site leads to a fake age check that takes your card; later a threatening email claims a webcam recording | An old password in the email (from a breach), Bitcoin demand, "sent from your own address", charges from an unknown merchant |

---

## 7. Answer key: every scenario

Notation: **→** means "click through to" or "search in". *Client secret* is what the client may hide. *Proof* is any record that makes a liar admit it. Every scenario on HARD/EXPERT also needs **the real person** (see [section 8](#8-unmasking-the-real-person-hard-and-expert)) and has a **campaign** field.

### 7.1 Bulk phishing (`bulk_phish`)

**Story.** A university staff member got an email "from {Brand} Security" about an unusual sign-in, clicked **Verify now** and logged in. The next day their account had been accessed.

**Case Report fields:** primary phishing domain · server that hosted it at click time (IP) · campaign · threat actor.

**Walkthrough.**
1. Exhibit A, the email: read **RAW HEADERS**. The From line shows the brand's real domain, but Return-Path is `bounce@notify-xxxx.example`, Reply-To is a `tempinbox.test` throwaway, and DMARC fails for the brand.
2. The link → **URL Scanner**. On MEDIUM+ the link is on a **hacked legitimate small-business site** (`/wp-content/uploads/...`) that 302-redirects to the phishing page. That site is a victim, not the attacker.
3. The final URL's host is the **primary domain** (a look-alike of the brand: combosquat, typo, hyphen or `.test` variant) → **IntelSearch** → **DNS History**. Pick the IP the domain pointed to **at the incident time**: not the sinkhole `203.0.113.250` (after takedown), and on HARD+ not the **CDN edge IP** (look further back for the origin). That is the **origin IP**.
4. **CertSearch** on the domain: its certificate also covers sibling domains. One sibling serves a payload (`.../Invoice_12345.zip`) → **MalwareDB** shows the sample and family.
5. **Web Search** the domain, sample or campaign: a vendor report (reliability B/C) names the **campaign** and the actor under a vendor alias → **Directory** resolves the alias to the **threat actor**.
6. (Database only, not shown in any tool yet: the generator also records the lure template in several locales, en-US, pt-BR, es-MX and en-GB, the hallmark of a mass campaign. It's in `lure_templates` for research queries.)

*Client secret:* after logging in, a zip downloaded and they **opened the file** inside. *Liar says:* "I didn't download anything." *Unlocks:* the payload URL. *Proof:* the payload URL, the malware sample, or its family.

**Traps:** compromised redirector site, sinkhole, CDN edge IP and its shared certificate, old phishing domains that used the same IP months earlier, a different actor's site on the same bulletproof IP (MEDIUM+), commodity malware and planted YARA/strings naming a decoy actor (HARD+), low-reliability blogs blaming the decoy.

### 7.2 Spear phishing (`spear_phish`)

**Story.** An email from "someone you met at {conference}" shared notes; the victim signed in to read them.

**Fields:** phishing domain · hosting server (IP) · **public post the attacker mined** (a social post) · threat actor.

**Walkthrough.** Read the email headers: the sender is on a `collab-xxxx.example` domain, not a real colleague. Follow the "Open document" link → URL Scanner → domain → DNS History for the IP at click time (CDN possible) → CertSearch for siblings → Web Search for the vendor report → Directory. For the mined post: CaseDesk's victim card has **"Search social media for {victim}"** → their Linkline profile → the public post about the conference the lure quoted.

*Client secret:* they **posted about the conference publicly** and thought their profile was private. *Liar says:* "I never post about work online." *Unlocks:* their profile and the post. *Proof:* the post or their profile.

### 7.3 Whaling / BEC (`whaling`)

**Story.** An urgent, confidential wire request ($48,500) "from" a university executive. The briefing says the victim *nearly* wired it.

**Fields:** look-alike sender domain · account the wire was directed to (mule) · threat actor.

**Walkthrough.** Compare the sender domain with `midstate.example` character by character: that's the **look-alike domain**. The executive is real (public Linkline profile), which is how the attacker knew names and titles. The **mule account** is a bank account (First Harbor Bank / Granite Trust, `****1234`) opened weeks earlier, flagged for mule activity. Money Trail: mule → Coinvale Exchange account → TRON wallet (cash-out).

*Client secret:* they **did reply and sent the wire**. *Liar says:* "I didn't send anything, I stopped." *Unlocks:* the follow-up email with the banking details, and the mule account. *Proof:* the mule account, the exchange account, or the look-alike domain. Without the client, the mule account is also listed in the vendor report (Web Search the look-alike domain) → Payments.

### 7.4 Clone phishing (`clone_phish`)

**Story.** A "resent" brand email linked to a login page identical to the real one.

**Fields:** cloned phishing domain · server hosting the clone (IP) · threat actor.

**Walkthrough.** URL Scanner on the link: **Screenshot similarity: 98% visual match** to the real login, and the same perceptual hash as the genuine page's scan. It's a clone, so find where it lived: domain → DNS History → origin IP → CertSearch → Web Search → Directory.

*Client secret (information only):* when it said "wrong password" they **tried their other passwords** (bank, university). *Proof:* the scan, the landing URL, or the domain.

### 7.5 Angler phishing (`angler_phish`)

**Story.** The victim complained publicly to the brand on Chirper and a "support" account replied with a recovery link.

**Fields:** impostor support account · phishing domain it linked to · hosting server · threat actor.

**Walkthrough.** Exhibits show the complaint and the replies. Compare the two brand accounts: the real one is verified, years old, with many followers; the **impostor** (`@brand_help`, `@brandsupport`, `@brand.care` or `@brand_hq`) is unverified, days old, with a previous handle. Its reply's link → URL Scanner → domain → DNS → CT → reporting → Directory.

*Client secret (information only):* they **DM'd the impostor the 6-digit code** texted to them. *Proof:* the impostor account, its reply, or the domain.

### 7.6 Smishing (`smishing`)

**Story.** Casual texts said the victim's campus mailbox was full; they tapped a short link and logged in.

**Fields:** number that sent the texts · phishing domain behind the link · hosting server · threat actor.

**Walkthrough.** Phone Lookup on the sender: a **VoIP** line with spam reports, the **sender number**. Spam Texts shows both texts; their "Writing style" field notes the informal campus-texting register the lure imitates. URL Scanner on the `mdst.ly` short link reveals the real host → DNS → CT → reporting. ScamWatch has other victims' reports listing the number.

*Client secret (information only):* they **entered a debit card** for a "$1.99 storage upgrade". *Proof:* the landing page, its scan, or the domain.

### 7.7 Vishing / voice cloning (`vishing`)

**Story.** A voicemail that sounded like a university executive asked for an urgent payment and gave a "finance line" to call back.

**Fields:** public recording the voice was cloned from · call-back number · account funds were requested to · threat actor.

**Walkthrough.** Audio Lab on the voicemail: synthetic-voice score 0.82–0.98 and STIR/SHAKEN C or B (unverified caller ID). Search Audio Lab for the executive's name, or for the voicemail's **voiceprint**: the public convocation talk has the **same voiceprint**. That's the **source recording**. The transcript's number → Phone Lookup: a toll-free VoIP **call-back number**. The **mule account** is a bank account; Money Trail → TRON wallet.

*Client secret:* they **called the number and started the transfer**. *Liar says:* "I never called back." *Unlocks:* the mule account. *Proof:* the call-back number, the mule account, or the cash-out wallet. Without the client, the vendor report lists the mule account (Web Search the call-back number).

### 7.8 Romance / catfishing (`romance`)

**Story.** Weeks of messages with a partner the victim never met, who now needs a "release fee".

**Fields:** the catfish persona · photo the scammer used · where money was sent · threat actor.

**Walkthrough.** The DM exhibits → the persona (`@handle` on HeartLink, Chirper or Pixgram, created weeks earlier). **Reverse Image** on the profile photo:
- EASY/MEDIUM: the photo first appeared **years earlier** on a different, legitimate account. That's the real owner, and the photo was stolen.
- HARD/EXPERT: the AI-face detector scores 0.6–0.95 and the only "match" is an AI-face gallery: the face is synthetic and there is no real owner.

Social Search the handle: the same handle and photos on a second platform (linked), plus a **look-alike handle** (`handle_`, `handlex`, `handle1`) that belongs to an unrelated person (a trap). The **payment** is GiftRun gift cards, a QuickPay handle (a mule), WireMoov, or a Coinvale account; Money Trail → TRON wallet.

*Client secret:* they **already sent money**. *Liar says:* "I haven't sent them a cent." *Unlocks:* the payment account. *Proof:* the payment account or the cash-out wallet. Without the client: ScamWatch reports list the payment identifier → Payments.

### 7.9 Advance-fee fraud (`advance_fee`)

**Story.** An email promised an inheritance, lottery win or dormant funds after a processing fee, with an official certificate attached.

**Fields:** address the offer came from · forged "official" document · where the fees were sent · threat actor.

**Walkthrough.** The email's From is the **sender address**; Reply-To is a different, disposable `tempinbox.test` address. **Document Lab** on the attached PDF: the metadata shows a private individual as author, a cheap or free editor (LibreOffice, Word 2010, Scribus) and a creation date days before the email. That's the **forged document**. On HARD+ the author is the real operator (see section 8). Fees went to WireMoov (a mule), GiftRun cards or Coinvale; Money Trail → wallet.

*Client secret:* they **already paid the first fee**. *Liar says:* "I haven't paid anything yet." *Unlocks:* the payment account. *Proof:* the payment account or wallet. Without the client: ScamWatch reports list the payment reference → Payments.

### 7.10 Tech-support scam (`tech_support`)

**Story.** A full-screen "virus" warning, a call to "support", a remote-control session, payment in gift cards.

**Fields:** domain serving the fake warning · "support" number on the warning · where payment was sent · threat actor.

**Walkthrough.** The exhibit is the URL scan of the warning page: title "Your computer may be infected: call (888) 555-01xx", page artifacts (alarm audio, disabled back button, keyboard capture). The host is the **pop-up domain** (a OneMail/CloudDrive look-alike). The number → Phone Lookup: toll-free VoIP with a brand-like caller-ID name and many spam reports: the **call-back number**. Payment: **GiftRun gift cards** (card numbers the victim read out); Money Trail → Bitcoin wallet.

*Client secret (information only):* while connected, the "technician" had them **log into online banking**, and they bought more cards the next day. *Proof:* the call-back number, the domain, or the warning-page scan.

### 7.11 Pig-butchering (`pig_butchering`)

**Story.** A stranger befriended the victim, introduced "TrustPeak Pro", the balance grew, and withdrawals were blocked until a "tax" was paid.

**Fields:** persona who introduced the "investment" · fake trading-platform domain · final cash-out wallet · threat actor.

**Walkthrough.** DMs → the **persona**. The second DM links the platform → URL Scanner: page artifacts (balance computed in JavaScript, withdraw disabled until a tax is paid, deposit address hard-coded) → the **fake platform domain** (a TrustPeak look-alike registered days earlier). The **deposit wallet** → Money Trail follows 2/3/4 layering hops (by difficulty) to a wallet tagged **cash-out**: that is the answer.

*Client secret:* they've deposited **far more** than they said (some borrowed from retirement), and they give you the **deposit address**. *Liar says:* "only a few hundred dollars." *Unlocks:* the deposit wallet. *Proof:* the platform domain, its landing page, or its scan. The deposit wallet is otherwise only reachable through the client, though the cash-out wallet is also named in the vendor report.

### 7.12 Adult-site ad & sextortion (`adult_ad`)

**Story.** A threatening email says the victim's webcam was hacked while they watched adult videos, quotes one of their real passwords, appears to come **from their own address**, and demands $1,450–$2,200 in Bitcoin within 48 hours.

**Fields:** Bitcoin wallet in the email · breach the quoted password came from · fake age-verification domain · merchant account that charged the card · threat actor.

**Walkthrough.**
1. **Is it real?** Breach Lookup the client's own email (the CaseDesk victim card has the button): it's in **ShopLane 2021**. That's where the password came from, so the threat is a bluff. The From line was **spoofed** to the victim's own address (Return-Path is the attacker's mailer domain; DMARC fails).
2. The **Bitcoin wallet** is in the email (CRYPTO ADDRESSES row → Money Trail): it consolidates into a cash-out wallet. ScamWatch shows other victims who got the same email with the same address.
3. The "preview" link → URL Scanner: a countdown page with no video, on a sibling domain sharing a **tracking ID**, **JARM** and **certificate** with the **age-verification domain** (`ageverify-...example`, look-alike of an age-check service).
4. That page's scan shows a card form posting to `/api/charge.php` with a pre-ticked $39.99/month box. The **merchant** is "Lumen Billing Ltd", statement descriptor `AVS*VERIFYNOW (888) 555-01xx`. ScamWatch reports list the descriptor → Payments.
5. Money Trail from the merchant: settlement → Coinvale Exchange → **the same cash-out wallet** as the extortion payments. One crew runs both.

*Client secret:* days earlier they were **on an adult video site** (`nightreel.example`, `velvetstream.example` or `afterdark-tube.example`), clicked an **ad** ("verify you're 18"), and entered their **email and card** on the age-check page. That's how the crew got their address. *Liar says:* "I have no idea how they got my email, and I definitely wasn't on any sites like that." *Unlocks:* the adult site, the ad-network click URL, and the merchant account. *Proof:* the age-check domain, its landing page or scan, the ad click URL or its scan, or the merchant account.

**Traps:** the adult site and the ad network (`popverse-ads.example`) are businesses that were **abused**, not the operators. The usual infrastructure traps also apply.

---

## 8. Unmasking the real person (HARD and EXPERT)

Every scenario at HARD or EXPERT adds the field **"Real person operating the scheme"**. The chain is the same everywhere; only the first step differs.

1. **Find the operator's email.**
   - *Through registration:* the attacker domain's **earliest WHOIS snapshot** (captured hours after registration, before privacy was on) lists the registrant email. On EXPERT the registrant name says "Domain Admin", but the email still leaks. Search WHOIS History for the domain and open the oldest snapshot.
   - *Through a forum ad:* if no domain leaked it, a criminal-forum post advertises "aged profiles", "callback lines", "drop accounts" or a "cashout service" and **names an indicator from this case** (the persona, number, account or wallet). Search that indicator in Social Search or Web Search to find the ad.
2. **Breach Lookup the email:** it appears in the *Darkmarket.test forum 2023* breach with the operator's handle, and in *GamerHub 2019* with the handle plus a digit.
3. **Social Search the handle:** the forum persona (selling services matching the scam), and the **same handle on a personal platform** (GitNest, Chirper, Pixgram, Linkline or Steamy) whose bio gives a first name and city.
4. That profile **links a personal page** → **Directory** → the **person**.

**Trap:** a look-alike handle (`handle_`) on Pixgram belongs to **someone else**. It's linked to a different person, not to the forum account. Some people in the Directory share names.

---

## 9. Traps that appear in every case

| Trap | Why it fools people | How to see through it |
|---|---|---|
| Sinkhole IP `203.0.113.250` | It's what the domain points to *today* | Use the DNS record live at the incident |
| CDN edge IP + shared certificate | Hundreds of unrelated sites share them | Look further back in DNS history for the origin |
| Previous tenants of the IP | Old benign domains resolved there months earlier | Check the dates |
| Stale phishing domains | Real phishing, but months before this incident | Check the dates |
| Another actor's site on the same IP | Shared bulletproof hosting | Co-location isn't attribution |
| Compromised redirector | The first link is on a real, hacked business site | Follow the redirect |
| Commodity malware | Sold to many crews | Malware alone doesn't attribute |
| Planted YARA hits and strings | "built by {famous group}" in the sample | Weigh against infrastructure and money overlap |
| D/E-reliability blogs | Confidently blame a famous group | A lead, not proof; look for overlap |
| Vendor naming chaos | One actor has three names | Resolve aliases in the Directory |
| Look-alike handles | One character off | Look for a real link (same photos, same email, same bio) |
| Complaint noise | Similar stories from other crews | Match on indicators, not on the story |
| The know-it-all's theory | The client is sure it's someone else | Their theory points at a decoy |
