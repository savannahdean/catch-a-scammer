"""The seven AI-assisted phishing variants from the project brief.

Each is a real 2025-era technique. The "2.0" twist is that the lure is tailored
with scraped/generated data, which the player can see in the evidence (scraped
posts, a cloned page's visual match, a cultural lure template, a voice-clone
source). The underlying infrastructure investigation is shared via self.site().
"""
from __future__ import annotations

from datetime import timedelta

from .. import fakes as F
from ..base import Scenario


class CredentialPhish(Scenario):
    """Bulk Phishing 2.0 — mass campaign, lure localized to the audience."""
    key = "bulk_phish"
    title = "Bulk phishing"
    category = "credential_theft"
    real_world_basis = "High-volume phishing with LLM-localized lures matching regional/cultural norms."
    player_skill = "Email header forensics; DNS-history and certificate pivoting; template reuse across locales."
    report_fields = [("primary_domain", "Primary phishing domain", "domain"),
                     ("origin_ip", "Server that hosted it at click time", "ip"),
                     ("campaign", "Campaign", "campaign"), ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Payroll Specialist", "Graduate Assistant", "Registrar's Office Clerk", "HR Coordinator"]

    def build(self):
        rng = self.rng
        s = self.site(self.brand_domain, title=f"Sign in | {self.brand}",
                      path=f"/auth/signin.php?sid={F.token(rng, 16)}")
        self.slot("primary_domain", s.primary_id)
        self.slot("origin_ip", s.origin_id)

        # localized template reuse: the same skeleton seen in several locales = mass campaign
        locales = rng.sample([("en-US", "en", None), ("pt-BR", "pt", "Pix instant-payment deadline"),
                              ("es-MX", "es", "SAT tax-refund notice"), ("en-GB", "en", "HMRC refund")], 3)
        base_tpl = F.hexstr(rng, 16)
        tpls = []
        for loc, lang, hook in locales:
            t = self.lure("account security alert", loc, lang, hook=hook, kit="OneKit v4",
                          template_hash=base_tpl, sample=f"[{loc}] verify your {self.brand} account within 24h")
            self.w.edge(s.landing_scan, t, "uses_template", source="urlscope", confidence=2)
            tpls.append(t)
        for a, b in zip(tpls, tpls[1:]):
            self.w.edge(a, b, "variant_of", source="urlscope", confidence=2)
        self.support(tpls[0], "Same lure template in several locales — hallmark of a mass campaign")

        pay_url, sample, fam = self.payload(s.siblings[0])
        self.chain(sample, f"Malware payload ({fam})")

        mdom, mip_id, mip = self.mail_domain(f"notify-{F.token(rng, 4)}.example", leak=self.p.require_person)
        self.support(mdom, "Sending domain")
        first_url = s.landing_id
        link_target = s.landing_url
        if self.p.compromised_redirector:
            first_url = self.redirector(s.landing_id, s.landing_url)
            link_target = self.value_of(first_url)
        email = self.email_msg(
            subject=f"Action required: unusual sign-in on your {self.brand} account",
            body=f"Dear customer,\n\nWe detected an unusual sign-in attempt on your {self.brand} account. "
                 f"Verify within 24 hours:\n\n    Verify now -> {link_target}\n\n{self.brand} Security Team",
            from_display=f"{self.brand} Security", from_addr=f"security@{self.brand_domain}",
            envelope=f"bounce@{self.value_of(mdom)}", sending_ip=(mip_id, mip), sent=self.at(hours=-rng.uniform(0.2, 1.5)),
            reply_to=f"support.{F.token(rng, 4)}@tempinbox.test", dkim_domain=self.value_of(mdom),
            origin_client=self.origin_client(), label=f"Phishing email to {self.victim}")
        self.w.edge(email, first_url, "contains_link", start=self.at(), source="Victim Report", confidence=1)
        self.clue(email, "The phishing email the victim received")
        self.hints = ["Open the email's raw headers. The visible From: can be spoofed. Where does the link really go?"] + self.site_hints(s)

        if first_url != s.landing_id:
            self.chain(first_url, "Link in the email: a redirect on a compromised site")
        self.chain(s.landing_id, "Credential-harvesting page the victim reached")
        self.chain(s.primary_id, "Primary phishing domain (look-alike of the brand)")
        self.chain(s.origin_id, "Origin server the domain pointed to at click time")
        self.chain(s.cert_id, "Certificate linking the primary domain to its siblings")
        self.chain(s.siblings[0][0], "Sibling domain that served the payload")
        self.chain(pay_url, "Payload URL")
        self.attribution([sample, s.primary_id, s.siblings[0][0]],
                         summary=f"{self.brand}-themed phishing with localized lures leading to {fam}.")
        self.chain(self.campaign_id, "Campaign the sample and infrastructure tie to")
        self.chain(self.actor_id, "Threat actor the campaign is attributed to")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} ({self.victim_role}, Midstate University) reports their {self.brand} account was "
                    f"accessed after they clicked a link in an email that looked like it came from {self.brand} on "
                    f"{self.local(self.at())}. Identify the malicious infrastructure and who is behind it.")
        resolution = (f"The email led {'through a compromised site ' if first_url != s.landing_id else ''}to "
                      f"{s.primary_fqdn}, served from {s.origin_ip}{' behind a CDN' if s.cdn else ''} at click time. "
                      f"Its certificate also covered the sibling that served {fam}; {self.vendor_alias} is the actor "
                      f"({self.actor_alias}). The lure template appeared in several locales — a mass campaign.")
        return briefing, resolution


class SpearPhish(Scenario):
    """Spear Phishing 2.0 — message built from the target's scraped social media."""
    key = "spear_phish"
    title = "Spear phishing"
    category = "credential_theft"
    real_world_basis = "Targeted phishing whose details are lifted from the victim's public social posts."
    player_skill = "Trace which scraped posts the lure reused; separate the spoofed sender from real infrastructure."
    report_fields = [("primary_domain", "Phishing domain", "domain"),
                     ("origin_ip", "Hosting server", "ip"),
                     ("scrape_source", "Public post the attacker mined", "social_post"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Grant Administrator", "Lab Manager", "Department Coordinator", "Assistant Professor"]

    def build(self):
        rng = self.rng
        # the victim's own public posts; the lure reuses a specific detail from one
        conf = rng.choice(["the DataCon workshop", "the Nashville research symposium", "the grant review in Austin"])
        vh = self.victim_first.lower() + str(rng.randint(1, 99))
        vp = self.persona(vh, "Linkline (professional)", display_name=self.victim, verdict="benign",
                          claimed_occupation=self.victim_role, claimed_location="Murfreesboro, TN", follower_count=rng.randint(80, 900))
        detail_post = self.post(vp, vh, "Linkline (professional)",
                                f"Great week at {conf}! Presenting our team's results and catching up with collaborators.",
                                self.at(-rng.randint(3, 9)), likes=rng.randint(5, 60), verdict="benign")
        for _ in range(rng.randint(2, 4)):
            self.post(vp, vh, "Linkline (professional)",
                      rng.choice(["New preprint is up — link in bio.", "Hiring a research assistant for spring.",
                                  "Office hours moved to Thursdays this semester."]),
                      self.at(-rng.randint(10, 60)), verdict="benign")
        self.support(detail_post, "Public post the attacker lifted a detail from")
        self.slot("scrape_source", detail_post)

        s = self.site(self.brand_domain, title="Shared document — sign in to view",
                      path=f"/d/{F.token(rng, 10)}", cdn_allowed=True)
        self.slot("primary_domain", s.primary_id)
        self.slot("origin_ip", s.origin_id)

        mdom, mip_id, mip = self.mail_domain(f"collab-{F.token(rng, 4)}.example", leak=self.p.require_person)
        sender = rng.choice(["Dr. Ramos", "the DataCon organizers", "Grants Office"])
        email = self.email_msg(
            subject=f"Follow-up from {conf}: shared notes",
            body=f"Hi {self.victim_first},\n\nGreat connecting at {conf}. I've shared the notes and photos from our session:\n\n"
                 f"    Open document -> {s.landing_url}\n\nYou'll need to sign in with your {self.brand} account.\n\nBest,\n{sender}",
            from_display=sender, from_addr=f"{rng.choice(['events', 'organizer', 'noreply'])}@{self.value_of(mdom)}",
            envelope=f"bounce@{self.value_of(mdom)}", sending_ip=(mip_id, mip), sent=self.at(hours=-rng.uniform(1, 6)),
            dkim_domain=self.value_of(mdom), origin_client=self.origin_client(), label=f"Spear-phish to {self.victim}")
        self.w.edge(email, s.landing_id, "contains_link", start=self.at(), source="Victim Report", confidence=1)
        self.w.edge(email, detail_post, "derived_from", source="Internal SOC", confidence=3,
                    note=f"Lure reused the victim's public mention of {conf}")
        self.clue(email, "A personalized email referencing a real event from the victim's public posts")

        self.hints = [f"The email mentions {conf}. Did the victim post about it publicly? Check the Directory for their profile.",
                      "The friendly sender name is not the sending domain. Read the headers and look up the real domain."] + self.site_hints(s)
        self.chain(s.landing_id, "The credential page")
        self.chain(s.primary_id, "Phishing domain")
        self.chain(s.origin_id, "Server it was hosted on at the time")
        self.chain(s.cert_id, "Certificate linking the operator's domains")
        self.attribution([s.primary_id, s.cert_id],
                         summary="Targeted phishing using details scraped from victims' professional profiles.",
                         targeting="university researchers")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} ({self.victim_role}) received an email referencing {conf}, which they had posted "
                    f"about publicly, and entered their {self.brand} credentials on the linked page. Find the "
                    f"infrastructure, identify which public post the attacker mined, and name the actor.")
        resolution = (f"The lure reused the victim's public post about {conf}. The link went to {s.primary_fqdn} on "
                      f"{s.origin_ip}; the certificate ties it to the operator's other domains, attributed to "
                      f"{self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution


class Whaling(Scenario):
    """Whaling 2.0 / BEC — executive impersonation with correct internal terminology."""
    key = "whaling"
    title = "Whaling / BEC"
    category = "wire_fraud"
    real_world_basis = "Business Email Compromise impersonating an executive, using accurate org terminology and a wire request."
    player_skill = "Spot look-alike sender domains and Reply-To swaps; follow the payment account, not just the email."
    report_fields = [("lookalike_domain", "Look-alike sender domain", "domain"),
                     ("mule_account", "Account the wire was directed to", "payment_account"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Accounts Payable Clerk", "Finance Assistant", "Controller's Office Staff"]

    def forum_bio(self):
        return "BEC leads + verified mule accounts (US/CA). escrow only."

    def build(self):
        rng = self.rng
        exec_name = F.person_name(rng)
        exec_title = rng.choice(["CFO", "VP of Finance", "Provost", "Director of Procurement"])
        real_dom = "midstate.example"
        look = self.new_lookalike("midstate.example")
        ldom, mip_id, mip = self.mail_domain(look, leak=self.p.require_person, typosquat_of=real_dom)
        self.slot("lookalike_domain", ldom)
        # the executive's real identity is public (staff page): that is how the attacker knew the terminology
        exec_persona = self.persona(exec_name.split()[0].lower(), "Linkline (professional)", display_name=exec_name,
                                    verdict="benign", claimed_occupation=f"{exec_title}, Midstate University")
        self.support(exec_persona, "The real executive's public profile, the source of the impersonation")

        mule = self.payment("bank_wire", rng.choice(["First Harbor Bank", "Granite Trust"]),
                            f"****{rng.randint(1000, 9999)}", holder=F.person_name(rng), mule=True,
                            notes="Opened 3 weeks before the incident; holder appears to be a recruited money mule",
                            verdict="suspicious")
        self.slot("mule_account", mule)
        wallet = None
        email = self.email_msg(
            subject="Confidential — vendor payment before EOD",
            body=f"{self.victim_first},\n\nAre you at your desk? I need a wire processed today for a new vendor "
                 f"(contract MSU-{rng.randint(2000, 9000)}) before the quarter closes. Keep this between us until "
                 f"the announcement. Reply and I'll send the banking details.\n\n{exec_name}\n{exec_title}, Midstate University\nSent from my iPhone",
            from_display=exec_name, from_addr=f"{exec_name.split()[0].lower()}.{exec_name.split()[1].lower()}@{look}",
            envelope=f"{exec_name.split()[0].lower()}@{look}", sending_ip=(mip_id, mip),
            sent=self.at(hours=-rng.uniform(1, 4)), reply_to=f"{exec_name.split()[0].lower()}@{look}",
            dkim_domain=look, origin_client=self.origin_client(), label="BEC wire-fraud email")
        # the follow-up with the account
        follow = self.email_msg(
            subject="Re: Confidential — vendor payment before EOD",
            body=f"Thanks. Please wire $48,500 to:\n\nBank: {self.conn.execute('select provider from payment_accounts where entity_id=%s',(mule,)).fetchone()[0]}\n"
                 f"Acct: {self.conn.execute('select identifier from payment_accounts where entity_id=%s',(mule,)).fetchone()[0]}\n"
                 f"Confirm once sent.\n\n{exec_name}",
            from_display=exec_name, from_addr=f"{exec_name.split()[0].lower()}@{look}", envelope=f"{exec_name.split()[0].lower()}@{look}",
            sending_ip=(mip_id, mip), sent=self.at(hours=-rng.uniform(0.2, 0.9)), dkim_domain=look,
            origin_client=self.origin_client(), label="BEC follow-up with banking details")
        self.w.edge(follow, mule, "pays_to", source="Victim Report", confidence=1, note="account given in the email")
        self.w.edge(follow, ldom, "sent_via", source="Internal SOC", confidence=1, note="follow-up sent from this domain")
        self.w.edge(email, exec_persona, "impersonates", source="Internal SOC", confidence=2)
        # the email is sent FROM the look-alike domain (envelope + From both on it)
        self.w.edge(email, ldom, "sent_via", source="Internal SOC", confidence=1,
                    note="sender and envelope are both on the look-alike domain")
        self.clue(email, "An urgent, confidential wire request appearing to come from a university executive")

        # money trail: mule -> exchange -> wallet
        exch = self.payment("crypto_exchange", "CoinGate-like exchange", f"acct-{F.token(rng, 6)}", mule=False, verdict="suspicious")
        wallet = self.wallet("tron")
        self.w.edge(mule, exch, "transfers_to", start=self.at(1), source="ScamWatch Portal", confidence=3,
                    note="funds moved out within 48h")
        self.w.edge(exch, wallet, "transfers_to", start=self.at(2), source="0xRumors", confidence=4)
        self.support(exch, "Intermediate account the money moved through")
        self.support(wallet, "Cash-out wallet at the end of the money trail")

        self.hints = ["Compare the sender's domain to the university's real one, character by character.",
                      "Follow the money. Where did the account in the email send the funds next?",
                      "The sender name is a real executive. Where could the attacker have learned the title and terminology?"]
        self.chain(ldom, "Look-alike domain the email was sent from")
        self.chain(follow, "Follow-up email giving the banking details")
        self.chain(mule, "Mule account the wire was directed to")
        self.chain(exch, "Exchange account the money moved to")
        self.attribution([ldom, mule], summary="BEC impersonating executives with a look-alike domain and mule accounts.",
                         targeting="university finance offices")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} ({self.victim_role}) nearly wired $48,500 after receiving an urgent, confidential "
                    f"request appearing to come from {exec_name}, {exec_title}. The email domain looked almost right. "
                    f"Identify the fake domain, trace the account, and name the actor.")
        resolution = (f"The email came from {look}, a look-alike of {real_dom}, not the executive. The wire account "
                      f"was a money mule; funds moved to an exchange and out to a wallet. Attributed to "
                      f"{self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution


class ClonePhish(Scenario):
    """Clone Phishing 2.0 — pixel-level clone of a real page, not just the text."""
    key = "clone_phish"
    title = "Clone phishing"
    category = "credential_theft"
    real_world_basis = "A phishing page that visually clones a legitimate site (matching perceptual hash), delivered as a 'resend'."
    player_skill = "Use the visual/perceptual-hash match to prove it's a clone; still find the real host behind it."
    report_fields = [("primary_domain", "Cloned phishing domain", "domain"),
                     ("origin_ip", "Server hosting the clone", "ip"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Staff member", "Student worker", "Adjunct instructor"]

    def build(self):
        rng = self.rng
        # the real page's fingerprint (benign), then the clone that matches it
        real_phash = F.hexstr(rng, 8)
        real_domain_id = self.conn.execute("select id from entities where value=%s and case_id is null", (self.brand_domain,)).fetchone()[0]
        real_url = f"https://{self.brand_domain}/login"
        ru = self.mk_url(real_domain_id, real_url, self.brand_domain, "benign")
        self.mk_scan(ru, real_url, self.at(-120), title=f"{self.brand} — Log in", ip="198.18.4.10", phash=real_phash)
        self.support(ru, "The genuine login page the clone copied")

        s = self.site(self.brand_domain, title=f"{self.brand} — Log in", path="/login",
                      phash=real_phash, visual_match=f"98% visual match to {real_url}",
                      sibling_title=f"{self.brand} — Log in")
        self.slot("primary_domain", s.primary_id)
        self.slot("origin_ip", s.origin_id)

        mdom, mip_id, mip = self.mail_domain(f"{self.brand_domain.split('.')[0]}-mail.example", leak=self.p.require_person)
        email = self.email_msg(
            subject=f"Re: Your recent {self.brand} statement (resending)",
            body=f"Hi,\n\nResending in case the earlier message went to spam. Please review your statement by signing in:\n\n"
                 f"    {s.landing_url}\n\n{self.brand} Customer Care",
            from_display=f"{self.brand} Customer Care", from_addr=f"care@{self.brand_domain}",
            envelope=f"bounce@{self.value_of(mdom)}", sending_ip=(mip_id, mip), sent=self.at(hours=-rng.uniform(1, 5)),
            dkim_domain=self.value_of(mdom), origin_client=self.origin_client(), label="Clone-phish 'resend' email")
        self.w.edge(email, s.landing_id, "contains_link", start=self.at(), source="Victim Report", confidence=1)
        self.clue(email, "A 'resent' email linking to a page that looks exactly like the real login")

        self.hints = ["Run the suspicious page through the URL Scanner. Compare its visual hash to the real site's.",
                      "The page looks identical, but what domain is it actually on, and where is that hosted?"] + self.site_hints(s)[1:]
        self.chain(s.landing_id, "The cloned login page (visually identical to the real one)")
        self.chain(s.primary_id, "Domain hosting the clone")
        self.chain(s.origin_id, "Server behind it at the time")
        self.chain(s.cert_id, "Certificate linking the operator's clone domains")
        self.attribution([s.primary_id, s.cert_id], summary="Pixel-accurate clones of brand login pages delivered as 'resends'.")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} ({self.victim_role}) received a 'resent' {self.brand} email and signed in on a page "
                    f"that looked exactly like the real one. Prove it was a clone, find where it was hosted, and name the actor.")
        resolution = (f"The page at {s.primary_fqdn} was a near-pixel-perfect clone (visual hash match to the real "
                      f"{self.brand} login) hosted on {s.origin_ip}. Attributed to {self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution


class AnglerPhish(Scenario):
    """Angler Phishing 2.0 — fake 'support' account hijacks a complaint on social media."""
    key = "angler_phish"
    title = "Angler phishing"
    category = "credential_theft"
    real_world_basis = "Attacker watches public complaints to a brand and replies from an impostor support account."
    player_skill = "Tell the impostor support account from the real one (handle, age, verification); follow its link."
    report_fields = [("impostor_account", "Impostor support account", "persona"),
                     ("primary_domain", "Phishing domain it linked to", "domain"),
                     ("origin_ip", "Hosting server", "ip"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Customer", "Account holder", "Student"]

    def build(self):
        rng = self.rng
        plat = "Chirper (social)"
        brand_handle = self.brand.split()[0].lower()
        real = self.persona(brand_handle, plat, display_name=f"{self.brand}", verdict="benign", verified=True,
                            follower_count=rng.randint(40_000, 400_000), account_created=self.at(-rng.randint(1500, 3000)),
                            claimed_occupation="Official account")
        self.support(real, "The real, verified brand account")
        # the victim's public complaint
        vh = self.victim_first.lower() + str(rng.randint(1, 99))
        vp = self.persona(vh, plat, display_name=self.victim, verdict="benign")
        complaint = self.post(vp, vh, plat, f"@{brand_handle} locked out of my account for 3 days and support won't answer. this is ridiculous",
                              self.at(hours=-rng.uniform(4, 10)), verdict="benign", likes=rng.randint(0, 12))
        # the impostor: near-identical handle, new, unverified
        imp_handle = rng.choice([brand_handle + "_help", brand_handle + "support", brand_handle + ".care", brand_handle + "_hq"])
        imp = self.persona(imp_handle, plat, display_name=f"{self.brand} Support", verdict="malicious", verified=False,
                          follower_count=rng.randint(10, 300), account_created=self.at(-rng.randint(2, 20)),
                          claimed_occupation="Customer Support", previous_handles=[brand_handle + str(rng.randint(100, 999))])
        self.slot("impostor_account", imp)
        s = self.site(self.brand_domain, title=f"{self.brand} account recovery", path="/recover")
        self.slot("primary_domain", s.primary_id)
        self.slot("origin_ip", s.origin_id)
        reply = self.post(imp, imp_handle, plat,
                          f"Hi {self.victim_first}, so sorry for the trouble! We can restore access right away — "
                          f"please verify here: {s.landing_url}",
                          self.at(hours=-rng.uniform(2, 4)), reply_to=(complaint, vh), verdict="malicious")
        self.w.edge(reply, s.landing_id, "contains_link", source="Victim Report", confidence=1)
        self.w.edge(imp, real, "impersonates", source="Internal SOC", confidence=2)
        self.clue(complaint, "The victim's public complaint — and the reply that answered it")

        self.hints = ["Two accounts replied. Compare their handles, join dates and verification. Which one is real?",
                      "Follow the link the support reply posted. What domain is it, and where is it hosted?"] + self.site_hints(s)[1:]
        self.chain(reply, "The impostor's reply with the phishing link")
        self.chain(imp, "The fake support account")
        self.chain(s.landing_id, "Account-recovery phishing page")
        self.chain(s.primary_id, "Phishing domain")
        self.chain(s.origin_id, "Hosting server at the time")
        self.chain(s.cert_id, "Certificate linking the operator's domains")
        self.attribution([imp, s.primary_id], summary="Impostor support accounts hijacking public complaints to brands.",
                         targeting="brand customers on social media")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} publicly complained to {self.brand} on social media and got a quick reply from what "
                    f"looked like {self.brand} support, with a recovery link. Identify the impostor account, the "
                    f"phishing site, and the actor.")
        resolution = (f"The reply came from @{imp_handle}, an unverified account created days earlier, not the real "
                      f"@{brand_handle}. Its link went to {s.primary_fqdn} on {s.origin_ip}. Attributed to "
                      f"{self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution


class Smishing(Scenario):
    """Smishing 2.0 — SMS tailored to the audience's language patterns."""
    key = "smishing"
    title = "Smishing"
    category = "credential_theft"
    real_world_basis = "SMS phishing whose wording matches the target audience's dialect/register, from a spoofed or VoIP number."
    player_skill = "Pivot from a sender number (carrier/line-type) and a shortened link to the real host."
    report_fields = [("sender_number", "Number that sent the texts", "phone"),
                     ("primary_domain", "Phishing domain behind the link", "domain"),
                     ("origin_ip", "Hosting server", "ip"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Student", "Staff member", "Parent of a student"]

    def build(self):
        rng = self.rng
        s = self.site(self.brand_domain, title=f"{self.brand} — confirm your details", path="/c")
        self.slot("primary_domain", s.primary_id)
        self.slot("origin_ip", s.origin_id)
        number = self.fict_number(rng.choice(["629", "615", "931"]))
        sender = self.phone(number, line_type="voip", carrier=rng.choice(["Bandwidth-like VoIP", "Twilio-like VoIP"]),
                           cnam=None, spam=rng.randint(3, 40), verdict="malicious")
        self.slot("sender_number", sender)
        shortlink = f"https://mdst.ly/{F.token(rng, 5)}"
        tpl = self.lure("package/redelivery SMS", "en-US", "en", kit="SmishKit", hook="informal US texting register",
                        sample="hey its midstate IT, ur mailbox is almost full-> link")
        self.w.edge(sender, s.landing_id, "contains_link", source="Victim Report", confidence=1)
        sms1 = self.sms(from_number=number, body=f"MSU IT: your email storage is almost full and will be locked. "
                        f"fix it real quick here {shortlink}", at=self.at(hours=-rng.uniform(2, 6)),
                        style="informal US campus texting")
        sms2 = self.sms(from_number=number, body=f"reminder: action needed on ur {self.brand} acct b4 today {shortlink}",
                        at=self.at(hours=-rng.uniform(0.5, 1.5)), style="informal")
        for m in (sms1, sms2):
            self.w.edge(m, sender, "sent_from_number", source="Victim Report", confidence=1)
            self.w.edge(m, s.landing_id, "contains_link", source="Victim Report", confidence=1)
            self.w.edge(m, tpl, "uses_template", source="urlscope", confidence=2)
        self.support(tpl, "Smishing template written in the audience's informal register")
        self.clue(sms1, "A text message with a shortened link, in casual campus-texting style")
        self.complaints([sender, s.primary_id], ["Got the same text about my mailbox being full, number was a 629.",
                        "Texts claiming to be campus IT, link went to a fake login."], indicators=[number, s.primary_fqdn])

        self.hints = ["Look the sender number up in the Directory. Is it a real carrier line or VoIP? How many spam reports?",
                      "The link is shortened. Scan it to see where it really lands, then investigate that domain."] + self.site_hints(s)[1:]
        self.chain(sender, "The VoIP number that sent the texts")
        self.chain(s.landing_id, "Page the shortened link resolved to")
        self.chain(s.primary_id, "Phishing domain")
        self.chain(s.origin_id, "Hosting server at the time")
        self.chain(s.cert_id, "Certificate linking the operator's domains")
        self.attribution([sender, s.primary_id], summary="SMS phishing with audience-matched wording via VoIP numbers.",
                         targeting="university students and staff")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} ({self.victim_role}) got texts in casual campus-texting style about their mailbox "
                    f"and {self.brand} account, with a shortened link, and entered their login. Identify the sending "
                    f"number, the phishing site, and the actor.")
        resolution = (f"The texts came from {self.pretty(number)}, a VoIP line with prior spam reports. The shortened "
                      f"link resolved to {s.primary_fqdn} on {s.origin_ip}. Attributed to {self.actor_alias} "
                      f"({self.vendor_alias}).")
        return briefing, resolution


class Vishing(Scenario):
    """Vishing 2.0 — voice cloned from a public recording of a real person."""
    key = "vishing"
    title = "Vishing (voice cloning)"
    category = "wire_fraud"
    real_world_basis = "Phone fraud using a voice cloned from a public talk/recording of a real executive."
    player_skill = "Match the voicemail's voiceprint to a public recording; prove it's synthetic; trace the call-back."
    report_fields = [("source_recording", "Public recording the voice was cloned from", "audio_recording"),
                     ("callback_number", "Call-back number", "phone"),
                     ("mule_account", "Account funds were requested to", "payment_account"),
                     ("actor", "Threat actor responsible", "threat_actor")]
    victim_roles = ["Executive Assistant", "Finance Assistant", "Accounts Payable Clerk"]

    def forum_bio(self):
        return "voice cloning + callback infra for sale. BEC/vishing. escrow only."

    def build(self):
        rng = self.rng
        exec_name = F.person_name(rng)
        exec_title = rng.choice(["CFO", "President", "VP of Operations"])
        # the public source recording (benign), and the cloned voicemail that matches its voiceprint
        voiceprint = F.hexstr(rng, 16)
        talk = self.audio("public_talk", speaker=exec_name, at=self.at(-rng.randint(120, 600)),
                          duration=rng.randint(900, 2400), synthetic=round(rng.uniform(0.01, 0.06), 3),
                          voiceprint=voiceprint, source_url=f"https://videos.midstate.example/convocation-{self.at().year-1}",
                          transcript=f"...thank you all for being here. As {exec_title}, I'm proud of what this community...",
                          note="Public convocation address", verdict="benign")
        self.support(talk, "Public recording of the real executive — the clone's source")
        self.slot("source_recording", talk)

        number = self.fict_number("888", toll_free=True)
        callback = self.phone(number, line_type="toll_free", carrier="VoIP aggregator", cnam=f"{self.brand} FINANCE",
                             spam=rng.randint(1, 15), verdict="malicious")
        self.slot("callback_number", callback)
        spoofed_cid = f"+1615555{rng.randint(1000, 1099)}"  # what the victim's phone showed
        vm = self.audio("voicemail", speaker=exec_name, at=self.at(hours=-rng.uniform(1, 5)), duration=rng.randint(25, 55),
                        caller_id=f"{exec_name} (mobile)", stir=rng.choice(["C", "C", "B"]),
                        synthetic=round(rng.uniform(0.82, 0.98), 3), voiceprint=voiceprint,
                        transcript=f"{self.victim_first}, it's {exec_name}. I'm going into a board meeting and can't "
                                   f"take calls. We have an urgent vendor payment that must go out today. Call our "
                                   f"finance line at {self.pretty(number)} and they'll give you the details. Thanks.",
                        note="Voiceprint matches the public convocation recording; deepfake detector flags it as synthetic",
                        verdict="malicious")
        self.w.edge(vm, talk, "voice_cloned_from", source="audio lab", confidence=2, note="matching speaker embedding")
        self.w.edge(vm, callback, "calls_back_to", source="Victim Report", confidence=1)
        self.w.edge(vm, callback, "sent_from_number", source="Internal SOC", confidence=2, note=f"caller ID spoofed as {spoofed_cid}")
        self.w.edge(vm, self.conn.execute("select id from entities where value=%s and case_id is null", (self.brand_domain,)).fetchone()[0] if False else talk, "impersonates", source="Internal SOC", confidence=1) if False else None
        self.clue(vm, "An urgent voicemail that sounds like a real executive")

        mule = self.payment("bank_wire", rng.choice(["First Harbor Bank", "Granite Trust"]), f"****{rng.randint(1000, 9999)}",
                            holder=F.person_name(rng), mule=True, verdict="suspicious",
                            notes="Account given over the phone when the victim called back")
        self.slot("mule_account", mule)
        wallet = self.wallet("tron")
        self.w.edge(callback, mule, "pays_to", source="Victim Report", confidence=2, note="account dictated on the call")
        self.w.edge(mule, wallet, "transfers_to", start=self.at(1), source="ScamWatch Portal", confidence=3)
        self.support(wallet, "Cash-out wallet")
        # we need the source-audio lab as a source
        self.complaints([callback], ["Got a voicemail that sounded exactly like our director asking for a wire.",
                        "Toll-free 'finance line' callback, they pushed for a same-day transfer."], indicators=[number])

        self.hints = ["The voicemail claims to be an executive. Is there a public recording of that person to compare against?",
                      "Check the recording's voiceprint and the synthetic-voice score. Then look up the call-back number.",
                      "Follow the money from the account you were told to pay."]
        self.chain(talk, "The public recording used to clone the voice")
        self.chain(callback, "The call-back number the voicemail gave")
        self.chain(mule, "Account the caller directed funds to")
        self.chain(wallet, "Where the money cashed out")
        self.attribution([callback, mule], summary="Voice-clone vishing impersonating executives for urgent wires.",
                         targeting="finance staff")
        self.chain(self.campaign_id, "Campaign")
        self.chain(self.actor_id, "Threat actor")
        if self.p.require_person:
            self.unmask(getattr(self, 'leak_anchor', []))

        briefing = (f"{self.victim} ({self.victim_role}) received a voicemail that sounded like {exec_name}, {exec_title}, "
                    f"urgently requesting a vendor wire and giving a finance call-back line. Prove the voice was cloned, "
                    f"find the source recording and call-back number, trace the money, and name the actor.")
        resolution = (f"The voicemail's voiceprint matched {exec_name}'s public convocation recording and scored high on "
                      f"the deepfake detector — it was cloned. The call-back line {self.pretty(number)} directed funds to "
                      f"a mule account that cashed out to a wallet. Attributed to {self.actor_alias} ({self.vendor_alias}).")
        return briefing, resolution
