"""Classic social-engineering scams people actually run into: catfishing/romance,
advance-fee ("Nigerian prince"), tech-support, and pig-butchering crypto.

These lean on different tools than phishing: reverse image search, document
metadata, persona/handle correlation, phone and payment lookups, the money
trail. No web-hosting investigation is required, so they exercise a different
part of the schema and keep the game varied.
"""
from __future__ import annotations

from datetime import timedelta

from .. import fakes as F
from ..base import Scenario


class Romance(Scenario):
    """Catfishing / romance scam. The core move is reverse image search: the
    'person' in the photos is really someone else (often a real model/soldier)."""
    key = "romance"
    title = "Romance scam (catfishing)"
    category = "romance_fraud"
    real_world_basis = "Romance/catfishing fraud using stolen or AI-generated profile photos and a fabricated persona."
    player_skill = "Reverse image search to find the real photo owner; correlate the persona's handle across platforms; follow the money."
    report_fields = [("scam_persona", "The catfish persona", "persona"),
                     ("stolen_image", "Photo the scammer used", "image"),
                     ("payment_target", "Where money was sent", "payment_account"),
                     ("actor", "Threat actor / ring responsible", "threat_actor")]
    victim_roles = ["Community member", "Alumnus", "Staff member", "Retiree"]
    actor_motivations = ("financial",)

    def forum_bio(self):
        return "romance scripts + aged dating profiles + photo sets. bulk pricing."

    def build(self):
        rng = self.rng
        plat = rng.choice(["HeartLink (dating)", "Chirper (social)", "Pixgram (photos)"])
        handle = F.handle(rng)
        claimed_name = F.person_name(rng)
        claimed_job = rng.choice(["offshore oil engineer", "field doctor with an international aid charity", "merchant-navy captain",
                                  "contractor deployed overseas", "surgeon on a humanitarian mission"])
        claimed_loc = rng.choice(["currently in Dubai", "on assignment in Ghana", "stationed in Cyprus"])
        scammer = self.persona(handle, plat, display_name=claimed_name, verdict="malicious",
                              claimed_occupation=claimed_job, claimed_location=claimed_loc,
                              account_created=self.at(-rng.randint(20, 120)), follower_count=rng.randint(30, 400),
                              bio=f"{claimed_job}. {claimed_loc.title()}. God-fearing, looking for something real.")
        self.slot("scam_persona", scammer)

        # the photo: really belongs to someone else, posted long before
        phash = F.hexstr(rng, 8)
        synthetic = round(rng.uniform(0.05, 0.25), 3) if not self.hard() else round(rng.uniform(0.6, 0.95), 3)
        img = self.image(f"Profile photo used by @{handle}", phash=phash, synthetic=synthetic)
        self.slot("stolen_image", img)
        self.w.edge(scammer, img, "uses_image", start=self.at(-rng.randint(20, 120)), source="HeartLink", confidence=1)
        if synthetic < 0.5:
            # real owner: a legitimate account that posted the picture years earlier
            owner_handle = F.handle(rng)
            owner = self.persona(owner_handle, rng.choice(["Pixgram (photos)", "Chirper (social)"]),
                                display_name=F.person_name(rng), verdict="benign", verified=rng.random() < 0.3,
                                claimed_occupation=rng.choice(["fitness coach", "travel blogger", "army reservist"]),
                                account_created=self.at(-rng.randint(1500, 3000)), follower_count=rng.randint(2000, 90_000))
            self.w.edge(img, owner, "image_seen_at", start=self.at(-rng.randint(900, 2500)), source="reverse image engine", confidence=1)
            self.support(owner, "The real owner of the photos — a legitimate, much older account")
            owner_note = f"the photos really belong to @{owner_handle}, whose account is years older"
        else:
            self.herring(self.image("AI-face generator sample gallery", phash=phash[:6] + F.token(rng, 2)),
                         "Near-duplicate from an AI-face gallery; the face is synthetic, there is no real owner")
            owner_note = "the face is AI-generated — the reverse-image hit leads to a synthetic-face gallery"

        # several platforms, same handle (correlation), one is a decoy look-alike
        other = self.persona(handle, "Chirper (social)" if "Chirper" not in plat else "Pixgram (photos)",
                            display_name=claimed_name, verdict="suspicious", account_created=self.at(-rng.randint(10, 60)))
        self.w.edge(scammer, other, "same_username", source="Internal SOC", confidence=2, note="identical handle, same photos")
        self.support(other, "Same handle on another platform, same photos")
        self.herring(self.persona(handle + rng.choice(["x", "_", "1"]), "HeartLink (dating)", display_name=F.person_name(rng)),
                     "Similar handle, unrelated real user")

        # chat DMs: the ask
        dm1 = self.post(scammer, handle, plat, f"{self.victim_first}, talking to you is the best part of my day. "
                        f"I feel like we were meant to meet.", self.at(-rng.randint(10, 30)), dm=True)
        method = rng.choice(["gift_card", "p2p_app", "money_transfer", "crypto_exchange"])
        provider = {"gift_card": "GiftRun cards", "p2p_app": "QuickPay", "money_transfer": "WireMoov",
                    "crypto_exchange": "Coinvale Exchange"}[method]
        ident = {"gift_card": self.gift_cards(rng.randint(3, 6)), "p2p_app": f"${handle}pay",
                 "money_transfer": f"ref {F.token(rng,8).upper()}", "crypto_exchange": f"acct-{F.token(rng,6)}"}[method]
        pay = self.payment(method, provider, ident, holder=claimed_name if method != "gift_card" else None,
                          mule=method in ("p2p_app", "money_transfer"), verdict="malicious",
                          notes="Collection point for the romance scam")
        self.slot("payment_target", pay)
        dm2 = self.post(scammer, handle, plat, f"My bank froze my account while I'm overseas and customs is holding my "
                        f"equipment. I hate to ask, but could you help me cover the ${rng.randint(500,3000)} release fee? "
                        f"I'll pay you back the moment I'm home.", self.at(-rng.randint(2, 8)), dm=True, verdict="malicious")
        self.w.edge(dm2, pay, "pays_to", source="Victim Report", confidence=1)
        self.w.edge(scammer, pay, "pays_to", source="Victim Report", confidence=2, note="account controlled by the persona")
        self.clue(dm1, "Direct messages from an online partner the victim never met in person")

        # money trail to a cash-out wallet
        wallet = self.wallet("tron")
        self.w.edge(pay, wallet, "transfers_to", start=self.at(1), source="ScamWatch Portal", confidence=3)
        self.support(wallet, "Where the funds cashed out")
        self.complaints([scammer, pay], [f"Met '{claimed_name}' online, same story about customs fees, sent gift cards.",
                        "Online boyfriend claiming to be overseas, asked for money for a 'release fee'."],
                        indicators=[handle, ident], loss=(300, 8000))

        self.hints = ["Run the profile photo through reverse image search. Who posted it first, and when?",
                      "Search the handle in the Directory. Does the same name and photo appear on other platforms?",
                      "Where was the victim asked to send money? Follow it."]
        self.chain(dm1, "The romance DMs")
        self.chain(scammer, "The catfish persona")
        self.chain(img, "The profile photo (not the scammer's own)")
        self.chain(pay, "Where the victim sent money")
        self.chain(wallet, "Cash-out wallet")
        self.attribution([scammer, pay], summary="Romance/catfishing ring using stolen or AI photos and reused scripts.",
                         targeting="dating-app and social-media users")
        self.chain(self.campaign_id, "The ring / campaign")
        self.chain(self.actor_id, "Threat actor behind it")
        if self.p.require_person:
            self.unmask([])

        site = plat.split(" (")[0]
        paid_how = {"gift_card": f"I bought GiftRun gift cards and sent them photos of the codes ({ident})",
                    "p2p_app": f"I sent it on QuickPay to {ident}",
                    "money_transfer": f"I sent it with WireMoov, {ident}",
                    "crypto_exchange": f"I sent it to their Coinvale Exchange account, {ident}"}[method]
        self.fact("story", ["story"], f"I met {claimed_name} on {site} and we've talked every day for weeks. They're a "
                  f"{claimed_job}, {claimed_loc}. Now they need help paying a release fee so they can come home.")
        self.fact("when", ["when"], f"We started talking {self.said(self.when_of(dm1))}. They asked for money "
                  f"{self.said(self.when_of(dm2))}.")
        self.fact("who", ["who", "contact"], f"Their name is {claimed_name}, @{handle} on {site}. Their photos are... very "
                  f"attractive.", keywords=["photo", "photos", "picture", "pictures", "profile", "handle", "name"])
        self.fact("never_met", ["who"], "We've never video-called. Their camera is always broken or the connection is too bad.",
                  keywords=["video", "facetime", "meet", "met", "camera", "person", "in person"])
        self.fact("paid", ["money", "amount"], f"I already sent money. {paid_how}. I didn't want to admit it because I knew "
                  f"how it would look.", secret=True, lie="I haven't sent them a cent. I'm not stupid.",
                  keywords=["sent", "send", "paid", "pay", "money", "gift", "card", "cards", "already", "transfer", "fee",
                            "cash", "how much"],
                  unlocks=[pay], proof=[pay, wallet])

        briefing = (f"{self.victim} ({self.victim_role}) has been in an online relationship for weeks with someone they "
                    f"never met, who now needs money for an overseas 'release fee'. Verify the person is real, identify "
                    f"the persona and photos, trace the money, and name the ring.")
        resolution = (f"'{claimed_name}' (@{handle}) is a catfish: {owner_note}. The same handle and photos appear on "
                      f"another platform, and money went to {provider} and out to a wallet. Attributed to "
                      f"{self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution


class AdvanceFee(Scenario):
    """Advance-fee fraud — the classic 'Nigerian prince' / inheritance / lottery.
    Document metadata on the forged 'legal' papers is the OSINT giveaway."""
    key = "advance_fee"
    title = "Advance-fee fraud"
    category = "advance_fee"
    real_world_basis = "419 advance-fee fraud (inheritance/lottery/prince) with forged legal documents and upfront 'fees'."
    player_skill = "Read document metadata to expose the forger; correlate the reply address and phone; follow the fees."
    report_fields = [("sender_email", "Address the offer came from", "email_address"),
                     ("forged_document", "Forged 'official' document", "document"),
                     ("payment_target", "Where the 'fees' were sent", "payment_account"),
                     ("actor", "Threat actor / ring responsible", "threat_actor")]
    victim_roles = ["Staff member", "Retiree", "Student", "Alumnus"]

    def forum_bio(self):
        return "419 letter sets + forged bank/legal PDFs + drop accounts."

    def build(self):
        rng = self.rng
        story = rng.choice([
            ("a late client who shares your surname", "inheritance", "Barrister"),
            ("an international lottery you were entered into automatically", "lottery", "Claims Agent"),
            ("an overseas bank consolidation of dormant funds", "banking", "Bank Officer"),
        ])
        pitch, kind, role = story
        sender_name = F.person_name(rng)
        sender_dom = rng.choice(["barristers-chambers.example", "intl-claims.example", "trust-settlement.example"])
        sender_addr = f"{sender_name.split()[0].lower()}.{sender_name.split()[1].lower()}@{sender_dom}"
        sender = self.email_addr(sender_addr, verdict="malicious")
        self.slot("sender_email", sender)
        reply_addr = f"{F.token(rng, 6)}@tempinbox.test"

        amount = rng.choice(["$10.5 million USD", "£4,800,000 GBP", "$6,200,000 USD"])
        fee = rng.randint(850, 4500)
        # the forged document: metadata exposes the real author and that it was mass-produced
        forger_tool = rng.choice(["LibreOffice 7.2", "Microsoft Word 2010", "Scribus 1.5"])
        meta_author = self.operator["name"] if (self.p.require_person and self.operator) else F.person_name(rng)
        doc = self.document(f"{kind.title()}_Approval_Certificate.pdf",
                           excerpt=f"THIS IS TO CERTIFY that the sum of {amount} has been approved for release to the "
                                   f"beneficiary upon settlement of the processing fee...",
                           author=meta_author, modified_by=meta_author,
                           company=rng.choice(["Global Trust", "Apex Settlements", ""]), tool=forger_tool,
                           verdict="malicious", pages=2)
        self.slot("forged_document", doc)
        self.w.edge(doc, sender, "derived_from", source="document lab", confidence=2,
                    note="PDF metadata author matches the sender identity")

        email = self.email_msg(
            subject=rng.choice(["URGENT AND CONFIDENTIAL BUSINESS PROPOSAL", "CONGRATULATIONS - CLAIM NOTIFICATION",
                               "RE: TRANSFER OF UNCLAIMED FUNDS"]),
            body=f"Dear Friend,\n\nI am {sender_name}, {role}. I am contacting you regarding {pitch}, totaling {amount}. "
                 f"After careful consideration you have been selected as the beneficiary. To release the funds we must "
                 f"first settle a processing fee of ${fee}. Kindly find the approval certificate attached and reply to "
                 f"this message to proceed.\n\nYours faithfully,\n{sender_name}\n{role}",
            from_display=sender_name, from_addr=sender_addr, envelope=sender_addr, sending_ip=None,
            sent=self.at(hours=-rng.uniform(2, 20)), reply_to=reply_addr, origin_client=self.origin_client(),
            label="Advance-fee (419) offer", attachments=[doc])
        self.clue(email, "An unsolicited email promising a large sum after a small upfront 'fee'")

        method = rng.choice(["money_transfer", "gift_card", "crypto_exchange"])
        provider = {"money_transfer": "WireMoov", "gift_card": "GiftRun cards", "crypto_exchange": "Coinvale Exchange"}[method]
        pay = self.payment(method, provider, f"ref {F.token(rng, 8).upper()}", holder=F.person_name(rng),
                          mule=method == "money_transfer", verdict="malicious", notes="Processing-fee collection point")
        self.slot("payment_target", pay)
        self.w.edge(self.email_addr(reply_addr, disposable=True), pay, "pays_to", source="Victim Report", confidence=2)
        self.w.edge(sender, pay, "pays_to", source="Victim Report", confidence=2, note="fees collected for this sender")
        wallet = self.wallet("tron")
        self.w.edge(pay, wallet, "transfers_to", start=self.at(1), source="ScamWatch Portal", confidence=3)
        self.support(wallet, "Cash-out wallet")
        prov, ident = self.payment_details(pay)
        self.complaints([sender, pay], [f"Email said I inherited {amount}, just needed to pay a fee first.",
                        "Lottery I never entered, asked for a 'release fee' by wire."], indicators=[sender_addr, ident],
                        loss=(400, 6000))

        self.hints = ["Open the attached certificate's metadata. Who is the author, and what tool made it?",
                      "The friendly display name and the Reply-To are not the same. Track both addresses.",
                      "Where were the 'fees' sent? Follow the money."]
        self.chain(email, "The offer email")
        self.chain(sender, "The sender address")
        self.chain(doc, "The forged approval certificate")
        self.chain(pay, "Where the fees were sent")
        self.chain(wallet, "Cash-out wallet")
        self.attribution([sender, pay, doc], summary="Advance-fee fraud with forged documents and drop accounts.",
                         targeting="general public")
        self.chain(self.campaign_id, "The ring / campaign")
        self.chain(self.actor_id, "Threat actor behind it")
        if self.p.require_person:
            self.unmask([doc])   # document author -> operator identity path handled in unmask via breach/social

        self.fact("story", ["story"], f"I got an email from {sender_name}, a {role.lower()}, saying I'm the beneficiary of "
                  f"{amount}. There's an official certificate attached. I just have to pay a processing fee to release it.")
        self.fact("when", ["when"], f"It came {self.said(self.when_of(email))}.")
        self.fact("contact", ["contact", "who"], f"The email is from {sender_addr}. When I reply, it goes to a different "
                  f"address, {reply_addr}.", keywords=["reply", "address", "sender"])
        self.fact("document", ["device"], "The certificate is a PDF with stamps and signatures. It looks very official.",
                  keywords=["certificate", "pdf", "document", "attachment", "attached", "stamp"])
        self.fact("paid", ["money", "amount"], f"I already paid the first ${fee:,} fee through {prov}, {ident}. Now they want "
                  f"another fee for 'taxes' before they release the money.", secret=True,
                  lie="I haven't paid anything yet. I wanted to check with you first.",
                  keywords=["fee", "fees", "paid", "pay", "sent", "wire", "transfer", "processing", "money", "already",
                            "how much"],
                  unlocks=[pay], proof=[pay, wallet])

        briefing = (f"{self.victim} ({self.victim_role}) received an email promising {amount} after a small processing "
                    f"fee, with an official-looking certificate attached. Expose the forgery, trace the fees, and name "
                    f"the ring behind it.")
        resolution = (f"The certificate's metadata named its real author and a cheap editing tool — it was forged and "
                      f"mass-produced. The sender and Reply-To were disposable, and fees went to {provider} then out to "
                      f"a wallet. Attributed to {self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution

    def unmask(self, lead_in):
        # tie the document's metadata author to the operator before the generic chain
        if self.operator and lead_in:
            doc = lead_in[0]
            self.conn.execute("update documents set meta_author=%s, meta_last_modified_by=%s where entity_id=%s",
                              (self.operator["name"], self.operator["name"], doc))
            em = self.operator_email()
            self.w.edge(doc, em, "derived_from", source="document lab", confidence=3,
                        note="metadata author traced to this email via a reused alias")
            super().unmask([doc, em][1:])  # em already chained inside unmask; pass [] lead so it starts at email
        else:
            super().unmask([])


class TechSupport(Scenario):
    """Tech-support scam — fake 'virus' pop-up/call, remote access, gift-card payment."""
    key = "tech_support"
    title = "Tech-support scam"
    category = "tech_support_fraud"
    real_world_basis = "Fake security pop-up or cold call impersonating a tech brand, leading to remote access and gift-card payment."
    player_skill = "Pivot from the pop-up page and call-back number; recognize the gift-card payment pattern; follow it."
    report_fields = [("popup_domain", "Domain serving the fake warning", "domain"),
                     ("callback_number", "'Support' number on the warning", "phone"),
                     ("payment_target", "Where payment was sent", "payment_account"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Retiree", "Staff member", "Parent", "Student"]

    def forum_bio(self):
        return "techsupport scam pages + call-center scripts + gift-card launder."

    def build(self):
        rng = self.rng
        fake_brand = rng.choice(["OneMail Workspace", "CloudDrive Docs"])
        legit = {b: d for b, d, _ in F.BRANDS}[fake_brand]   # look-alike of the brand the warning names
        s = self.site(legit,
                      title=f"⚠ {fake_brand} Security Warning — Call Support Immediately",
                      path="/alert", cdn_allowed=False, host_type="vps", kit_pool=F.FAKE_ALERT_ARTIFACTS)
        self.slot("popup_domain", s.primary_id)
        self.slot("origin_ip", s.origin_id)   # extra supporting slot not scored unless present
        self.slots.pop("origin_ip", None)

        number = self.fict_number("888", toll_free=True)
        callback = self.phone(number, line_type="toll_free", carrier="VoIP aggregator",
                             cnam=f"{fake_brand.split()[0].upper()} SUPPORT", spam=rng.randint(5, 60), verdict="malicious")
        self.slot("callback_number", callback)
        # the pop-up scan shows the phone number baked into the page
        self.conn.execute("update url_scans set page_title=%s, kit_indicators = kit_indicators || %s where entity_id=%s",
                          (f"⚠ Your computer may be infected — call {self.pretty(number)}",
                           ["fake AV popup", f"support number {self.pretty(number)}", "disables back button"], s.landing_scan))
        self.w.edge(s.landing_id, callback, "calls_back_to", source="urlscope", confidence=2)

        method = "gift_card"
        pay = self.payment(method, "GiftRun cards", self.gift_cards(rng.randint(4, 8)), mule=False, verdict="malicious",
                          notes="Victim read gift-card codes over the phone")
        self.slot("payment_target", pay)
        self.w.edge(callback, pay, "pays_to", source="Victim Report", confidence=2, note="codes read aloud during the call")
        wallet = self.wallet("bitcoin")
        self.w.edge(pay, wallet, "transfers_to", start=self.at(hours=4), source="0xRumors", confidence=4)
        self.support(wallet, "Where resold card value cashed out")

        # the entry: a scan/complaint rather than an email
        self.clue(s.landing_scan, "A full-screen browser warning telling the victim to call a support number")
        self.complaints([callback, s.primary_id], [f"Pop-up locked my screen, called the number, they asked for gift cards.",
                        "Caller said my computer was hacked and had me buy gift cards to 'secure' it."],
                        indicators=[number, s.primary_fqdn], loss=(100, 3000))

        self.hints = ["Scan the warning page. What number does it tell the victim to call? Look that number up.",
                      "Gift cards are a red-flag payment method no real support uses. Where did the codes go?",
                      "Investigate the domain serving the warning and where it was hosted."]
        self.chain(s.landing_scan, "The fake security-warning page")
        self.chain(s.landing_id, "The warning page URL")
        self.chain(s.primary_id, "Domain serving the warning")
        self.chain(callback, "The 'support' number on the page")
        self.chain(pay, "Gift-card codes the victim was told to buy")
        self.chain(wallet, "Where the value cashed out")
        self.attribution([s.primary_id, callback], summary="Tech-support scam pages and call centers taking gift-card payment.",
                         targeting="home computer users")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        _, cards = self.payment_details(pay)
        self.fact("story", ["story"], f"A full-screen warning popped up saying my computer was infected and to call "
                  f"{fake_brand} support. I called, a technician connected to my computer and 'fixed' it, and I paid with "
                  f"gift cards.")
        self.fact("when", ["when"], f"It happened {self.said(self.at())}.")
        self.fact("number", ["phone", "contact"], f"The warning said to call {self.pretty(number)}. That's the number I called.")
        self.fact("link", ["link"], "I was just browsing and a page took over the whole screen. It played a loud alarm and I "
                  "couldn't close it.", keywords=["popup", "pop-up", "warning", "screen", "browser", "website", "alarm"])
        self.fact("device", ["device"], "The technician had me install a remote-support program and read him a code. Then he "
                  "moved my mouse around by himself.", keywords=["remote", "install", "program", "software", "access",
                                                                 "connect", "connected", "control"])
        self.fact("cards", ["money", "amount"], f"He told me to buy GiftRun cards and read him the numbers: {cards}.",
                  keywords=["gift", "card", "cards", "codes"])
        self.fact("bank", ["login", "money"], "While he was connected he asked me to log in to my online banking 'to check for "
                  "hackers', and I did. The next day they called back and I bought more cards.", secret=True,
                  lie="He only looked at the virus stuff. I never opened my bank account in front of him.",
                  keywords=["bank", "banking", "login", "logged", "online", "again", "more", "call back", "called back",
                            "next day", "password"],
                  proof=[callback, s.primary_id, s.landing_scan])

        briefing = (f"{self.victim} ({self.victim_role}) hit a full-screen 'virus' warning, called the number on it, let "
                    f"a 'technician' connect remotely, and paid with gift cards. Identify the warning domain, the number, "
                    f"the payment trail, and the actor.")
        resolution = (f"The warning page at {s.primary_fqdn} displayed the toll-free line {self.pretty(number)}; the "
                      f"'technician' had the victim pay in gift cards, which were resold and cashed out. Attributed to "
                      f"{self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution


class PigButchering(Scenario):
    """Pig-butchering (sha zhu pan) — long-con fake crypto-investment via a built
    relationship, ending at a fake trading platform and a chain of wallets."""
    key = "pig_butchering"
    title = "Pig-butchering (crypto investment)"
    category = "investment_fraud"
    real_world_basis = "Long-con investment fraud: a built relationship steers the victim to a fake trading platform; deposits vanish through wallet chains."
    player_skill = "Spot the fake exchange domain; follow a multi-hop crypto money trail to the cash-out; tie the persona to the ring."
    report_fields = [("scam_persona", "Persona who introduced the 'investment'", "persona"),
                     ("fake_platform", "Fake trading-platform domain", "domain"),
                     ("cashout_wallet", "Final cash-out wallet", "crypto_wallet"),
                     ("actor", "Threat actor / ring responsible", "threat_actor")]
    victim_roles = ["Professional", "Staff member", "Recent graduate", "Community member"]

    def forum_bio(self):
        return "sha-zhu-pan panels + aged profiles + wallet laundering. team only."

    def build(self):
        rng = self.rng
        plat = rng.choice(["Chirper (social)", "HeartLink (dating)", "Linkline (professional)"])
        handle = F.handle(rng)
        cname = F.person_name(rng)
        scammer = self.persona(handle, plat, display_name=cname, verdict="malicious",
                              claimed_occupation=rng.choice(["crypto analyst", "fund manager", "early BTC investor"]),
                              claimed_location=rng.choice(["Singapore", "London", "Vancouver"]),
                              account_created=self.at(-rng.randint(60, 300)), follower_count=rng.randint(200, 5000),
                              bio="building generational wealth. DYOR. not financial advice 😉")
        self.slot("scam_persona", scammer)
        img = self.image(f"Profile photo of @{handle}", synthetic=round(rng.uniform(0.6, 0.95), 3) if self.hard() else round(rng.uniform(0.1, 0.4), 3))
        self.w.edge(scammer, img, "uses_image", start=self.at(-rng.randint(60, 300)), source="Chirper", confidence=1)
        self.support(img, "The persona's profile photo")

        # fake trading platform (looks like a real exchange)
        s = self.site("trustpeak.example", title="TrustPeak Pro — Dashboard", path="/dashboard",
                      cdn_allowed=True, host_type="vps", kit_pool=F.FAKE_EXCHANGE_ARTIFACTS)
        # relabel so it reads like a fake exchange rather than a login clone
        self.conn.execute("update domains set is_typosquat_of=%s where entity_id=%s", ("major crypto exchange", s.primary_id))
        self.slot("fake_platform", s.primary_id)
        self.slots.pop("origin_ip", None)

        dm1 = self.post(scammer, handle, plat, f"Hi {self.victim_first}! Looks like we matched interests. I don't usually "
                        f"DM but your profile stood out.", self.at(-rng.randint(30, 70)), dm=True)
        dm2 = self.post(scammer, handle, plat, f"My uncle taught me a strategy on TrustPeak Pro — I've been pulling steady "
                        f"returns. Happy to show you. Start small, you can withdraw anytime.", self.at(-rng.randint(10, 25)), dm=True, verdict="malicious")
        self.w.edge(dm2, s.landing_id, "contains_link", source="Victim Report", confidence=1)
        self.clue(dm1, "Friendly messages from a stranger that slowly turn to a 'can't-miss' crypto platform")

        # deposit wallet -> intermediaries -> cash-out (multi-hop money trail)
        deposit = self.wallet("tron", received=round(rng.uniform(5000, 60000), 2))
        self.w.edge(s.landing_id, deposit, "pays_to", source="Victim Report", confidence=1, note="deposit address shown in the dashboard")
        prev = deposit
        hops = 2 if self.p.level == "easy" else 3 if self.p.level == "medium" else 4
        last = deposit
        for i in range(hops):
            nxt = self.wallet("tron", received=round(rng.uniform(1000, 60000), 2))
            self.w.edge(prev, nxt, "transfers_to", start=self.at(hours=6 * (i + 1)), source="0xRumors", confidence=4,
                        note="layering hop")
            self.support(nxt, f"Intermediate wallet (hop {i+1})")
            prev = nxt
            last = nxt
        self.conn.execute("update entities set verdict='suspicious', tags=array['cash-out'] where id=%s", (last,))
        self.slot("cashout_wallet", last)
        self.complaints([scammer, s.primary_id], [f"Online friend got me into 'TrustPeak Pro', couldn't withdraw anything.",
                        "Investment app showed big gains but wanted 'tax' before any withdrawal."],
                        indicators=[handle, s.primary_fqdn], loss=(2000, 80000))

        self.hints = ["The platform isn't a known exchange. Look the domain up and check when it was created.",
                      "Start at the deposit address and follow the transfers hop by hop to the cash-out wallet.",
                      "Search the persona's handle across platforms and reverse-search the photo."]
        self.chain(dm1, "The relationship-building messages")
        self.chain(scammer, "The persona who introduced the 'investment'")
        self.chain(s.landing_id, "The fake trading dashboard")
        self.chain(s.primary_id, "Fake trading-platform domain")
        self.chain(deposit, "The deposit wallet")
        self.chain(last, "The final cash-out wallet")
        self.attribution([scammer, s.primary_id, last], summary="Pig-butchering ring running fake trading platforms and wallet layering.",
                         targeting="social-media and dating-app users")
        self.chain(self.campaign_id, "The ring / campaign")
        self.chain(self.actor_id, "Threat actor behind it")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        dep_addr, dep_total = self.conn.execute("select address, total_received from crypto_wallets where entity_id=%s",
                                                (deposit,)).fetchone()
        self.fact("story", ["story"], f"{cname} messaged me out of the blue on {plat.split(' (')[0]}. We became friends and "
                  f"they showed me how they invest on TrustPeak Pro. My balance went way up, but now it won't let me "
                  f"withdraw unless I pay a 'tax'.")
        self.fact("when", ["when"], f"They first messaged me {self.said(self.when_of(dm1))}. They brought up TrustPeak "
                  f"{self.said(self.when_of(dm2))}.")
        self.fact("who", ["who", "contact"], f"Their name is {cname}, @{handle}. Very successful, always traveling.",
                  keywords=["photo", "profile", "name", "handle"])
        self.fact("link", ["link"], "The platform is TrustPeak Pro. They sent me the link in a message. The dashboard looks "
                  "like a real exchange.", keywords=["site", "website", "platform", "app", "dashboard", "trustpeak", "withdraw"])
        self.fact("deposits", ["money", "amount"], f"I've deposited about ${float(dep_total):,.0f} in total, not the few "
                  f"hundred I said. Some of it I borrowed from my retirement account. They gave me this deposit address: "
                  f"{dep_addr}.", secret=True,
                  lie="I only put in a little, a few hundred dollars. It's not a big deal.",
                  keywords=["deposit", "deposited", "invest", "invested", "total", "borrow", "borrowed", "retirement",
                            "savings", "401k", "how much", "address", "wallet"],
                  unlocks=[deposit], proof=[s.primary_id, s.landing_id, s.landing_scan])

        briefing = (f"{self.victim} ({self.victim_role}) was befriended online and steered into 'TrustPeak Pro', deposited "
                    f"crypto, saw it grow, then couldn't withdraw. Identify the persona, the fake platform, follow the "
                    f"money to its cash-out, and name the ring.")
        resolution = (f"'{cname}' (@{handle}) steered the victim to {s.primary_fqdn}, a fake exchange registered weeks "
                      f"earlier. Deposits flowed through {hops} wallets to a cash-out address. Attributed to "
                      f"{self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution
